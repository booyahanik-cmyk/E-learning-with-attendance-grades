import csv
from datetime import timedelta
from functools import wraps
from zoneinfo import ZoneInfo

from django.conf import settings
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.contrib.auth.views import LoginView
from django.core.exceptions import PermissionDenied
from django.db import transaction
from django.db.models import Q
from django.http import Http404, HttpResponse, JsonResponse
from django.shortcuts import redirect, render, get_object_or_404
from django.urls import reverse
from django.utils import timezone
from django.utils.dateparse import parse_date, parse_datetime
from django.views.decorators.http import require_POST

from . import stats
from .forms import StudentRegistrationForm
from .models import (
    User, Course, ClassSession, Attendance, AttendanceCorrectionBatch,
    AttendanceCorrectionRequest, AttendanceAuditLog, StudentNotification,
    AttendanceCorrectionWindowExtension
)
from .notifications import verify_token


def home_url_for(user):
    """The page an account belongs on after signing in."""
    if user.role == User.Role.FACULTY:
        return reverse('faculty_dashboard')
    if user.role == User.Role.ADMIN or user.is_superuser:
        return reverse('admin:index')
    return reverse('student_home')


def role_required(*roles):
    """Restrict a view to the given roles. Admin accounts pass every gate."""
    def decorator(view):
        @wraps(view)
        def wrapper(request, *args, **kwargs):
            user = request.user
            if user.role not in roles and user.role != User.Role.ADMIN and not user.is_superuser:
                raise PermissionDenied('This page is not available for your account type.')
            return view(request, *args, **kwargs)
        return login_required(wrapper)
    return decorator


class RoleLoginView(LoginView):
    template_name = 'attendance/index.html'
    redirect_authenticated_user = True

    def get_default_redirect_url(self):
        return home_url_for(self.request.user)


def register(request):
    """Public sign-up. Student accounts only."""
    if request.user.is_authenticated:
        return redirect(home_url_for(request.user))

    if request.method == 'POST':
        form = StudentRegistrationForm(request.POST)
        if form.is_valid():
            form.save()
            messages.success(request, 'Account created. Sign in with your roll number.')
            return redirect('login')
    else:
        form = StudentRegistrationForm()

    return render(request, 'attendance/newregistration.html', {'form': form})


@role_required(User.Role.STUDENT)
def student_home(request):
    """The student portal: enrolled courses, attendance records, missing session alerts."""
    records = request.user.attendance_records.select_related('course', 'session')
    enrolled_courses = request.user.courses.all().select_related('faculty')

    # Detect published sessions for which attendance was not marked for this student
    recorded_session_ids = set(records.values_list('session_id', flat=True))
    missing_sessions = ClassSession.objects.filter(
        course__in=enrolled_courses,
        is_published=True,
        date__lte=timezone.localdate()
    ).exclude(
        id__in=recorded_session_ids
    ).select_related('course', 'course__faculty').order_by('-date', 'session_identifier')[:10]

    # Active pending correction requests for this student
    active_requests = set(
        AttendanceCorrectionRequest.objects.filter(
            student=request.user,
            status=AttendanceCorrectionRequest.Status.PENDING
        ).values_list('session_id', flat=True)
    )

    notifications = request.user.notifications.all()[:5]

    return render(request, 'attendance/student_dashboard.html', {
        'courses': stats.by_course(request.user),
        'overall': stats.totals(records),
        'history': records.order_by('-date', '-created_at')[:15],
        'missing_sessions': missing_sessions,
        'active_requests': active_requests,
        'notifications': notifications,
        'shortfall': stats.SHORTFALL,
        'active_tab': 'attendance',
        'today': timezone.localdate(),
    })


@role_required(User.Role.FACULTY)
def faculty_dashboard(request):
    """Real figures for the signed-in faculty across the courses they teach."""
    ctx = stats.faculty_overview(request.user)
    ctx['active_tab'] = 'dashboard'
    return render(request, 'attendance/dashboard.html', ctx)


# --- Attendance Register & Session Management -------------------------------

def teachable(user):
    """The courses this account may open a register for."""
    if user.role == User.Role.ADMIN or user.is_superuser:
        return Course.objects.select_related('faculty').order_by('code')
    return user.courses_taught.select_related('faculty').order_by('code')


def pick_course(courses, raw):
    if not courses:
        return None
    if not raw:
        return courses[0]
    for course in courses:
        if str(course.pk) == str(raw):
            return course
    raise Http404('No such course for this account.')


def pick_date(request, raw):
    """The requested date, or today. Unreadable input falls back with a message."""
    if not raw:
        return timezone.localdate()
    day = parse_date(raw)
    if day is None:
        messages.error(request, 'That date could not be read, so today is shown instead.')
        return timezone.localdate()
    return day


def pick_session(course, day, raw_session_id=None):
    """Select an existing class session or create default Session 1."""
    if not course:
        return None, []
    sessions = list(course.sessions.filter(date=day).order_by('session_identifier'))
    if raw_session_id:
        for s in sessions:
            if str(s.pk) == str(raw_session_id):
                return s, sessions
    if sessions:
        return sessions[0], sessions
    # Create default session
    session = ClassSession.objects.create(
        course=course,
        date=day,
        session_identifier='Session 1',
        is_published=True
    )
    return session, [session]


def save_register(request, course, session, loaded_at=None):
    """Upsert one Attendance row per marked student for this session."""
    allowed = set(Attendance.Status.values)
    saved, unmarked, skipped_protected = 0, [], []
    with transaction.atomic():
        for student in course.students.order_by('roll_number', 'username'):
            status = request.POST.get('s{}'.format(student.pk))
            if status not in allowed:
                unmarked.append(student.roll_number or student.username)
                continue

            existing = Attendance.objects.filter(student=student, session=session).first()
            if existing and loaded_at:
                # Protect against stale register overwrite if student has newer approved correction
                has_recent_correction = AttendanceCorrectionRequest.objects.filter(
                    student=student,
                    session=session,
                    status=AttendanceCorrectionRequest.Status.APPROVED,
                    reviewed_at__gt=loaded_at
                ).exists()
                if has_recent_correction:
                    skipped_protected.append(student.roll_number or student.username)
                    continue

            Attendance.objects.update_or_create(
                student=student, session=session,
                defaults={
                    'course': course,
                    'date': session.date,
                    'status': status,
                    'marked_by': request.user
                },
            )
            saved += 1
    return saved, unmarked, skipped_protected


@role_required(User.Role.FACULTY)
def attendance_register(request):
    """Mark roll call for a course on a date and session (supports multiple sessions per date)."""
    courses = list(teachable(request.user))
    course = pick_course(courses, request.POST.get('course') or request.GET.get('course'))
    day = pick_date(request, request.POST.get('date') or request.GET.get('date'))

    # Support adding a new session identifier on that date (e.g. Session 2)
    if request.method == 'POST' and request.POST.get('action') == 'add_session' and course:
        new_name = request.POST.get('new_session_identifier', '').strip()
        if new_name:
            session, _ = ClassSession.objects.get_or_create(
                course=course,
                date=day,
                session_identifier=new_name,
                defaults={'is_published': True}
            )
            messages.success(request, f'Created session "{new_name}" for {course.code} on {day}.')
            return redirect(f"{reverse('attendance_register')}?course={course.pk}&date={day.isoformat()}&session={session.pk}")

    session, sessions_on_date = pick_session(
        course, day, request.POST.get('session') or request.GET.get('session')
    )

    if request.method == 'POST' and request.POST.get('action') != 'add_session':
        loaded_at = None
        raw_loaded = request.POST.get('loaded_at')
        if raw_loaded:
            loaded_at = parse_datetime(raw_loaded)

        if course is None:
            messages.error(request, 'You have no courses to mark. Ask an admin to assign one.')
        elif day > timezone.localdate():
            messages.error(request, 'A register cannot be saved for a future date.')
        elif not course.students.exists():
            messages.error(request, 'No students are enrolled in {} yet.'.format(course.code))
        else:
            saved, unmarked, skipped = save_register(request, course, session, loaded_at=loaded_at)
            sess_label = session.session_identifier if session else 'Session 1'
            if saved:
                messages.success(
                    request,
                    f'Register saved: {saved} student{"s" if saved != 1 else ""} marked in {course.code} ({sess_label}) for {day.isoformat()}.'
                )
            if unmarked:
                messages.error(request, f'Left unmarked: {", ".join(unmarked)}.')
            if skipped:
                messages.warning(
                    request,
                    f'Protected from overwrite: {", ".join(skipped)} (an approved attendance correction was completed after this page loaded).'
                )
            redirect_url = f"{reverse('attendance_register')}?course={course.pk}&date={day.isoformat()}"
            if session and len(sessions_on_date) > 1:
                redirect_url += f"&session={session.pk}"
            return redirect(redirect_url)

    rows, marks = [], {}
    if course is not None and session is not None:
        marks = dict(session.attendance_records.values_list('student_id', 'status'))
        rows = stats.by_student(course)
        for row in rows:
            row['mark'] = marks.get(row['student'].pk)

    return render(request, 'attendance/attendance.html', {
        'courses': courses,
        'course': course,
        'day': day,
        'session': session,
        'sessions_on_date': sessions_on_date,
        'today': timezone.localdate(),
        'loaded_at': timezone.now().isoformat(),
        'rows': rows,
        'marked': stats.totals(session.attendance_records) if session else None,
        'saved_before': bool(marks),
        'active_tab': 'attendance',
    })


# --- Reports ---------------------------------------------------------------

HEATMAP_DAYS = 28

def report_context(request, course):
    rows = stats.by_student(course)
    held = stats.class_dates(course)
    published_sessions_count = course.sessions.filter(is_published=True, attendance_records__isnull=False).distinct().count()
    start = timezone.localdate() - timedelta(days=HEATMAP_DAYS - 1)
    days = []
    for day, row in stats.daily_percentages(course.attendance_records, start, HEATMAP_DAYS):
        days.append({'date': day, 'level': heat_level(row), 'row': row})
    return {
        'course': course,
        'rows': rows,
        'shortfalls': stats.shortfalls(rows),
        'overall': stats.totals(course.attendance_records),
        'classes_held': published_sessions_count if course.attendance_records.exists() else 0,
        'last_class': held[0] if held else None,
        'perfect': [r for r in rows if r['held'] and r['percent'] == 100],
        'heatmap': days,
        'threshold': stats.SHORTFALL,
    }


def heat_level(row):
    if not row['held']:
        return 0
    pct = row['percent']
    if pct >= 90:
        return 4
    if pct >= 80:
        return 3
    if pct >= 70:
        return 2
    return 1


@role_required(User.Role.FACULTY)
def reports(request):
    courses = list(teachable(request.user))
    course = pick_course(courses, request.GET.get('course'))
    context = {'courses': courses, 'course': None, 'active_tab': 'reports'}
    if course is not None:
        context.update(report_context(request, course))
    return render(request, 'attendance/reports.html', context)


@role_required(User.Role.FACULTY)
def reports_export(request):
    courses = list(teachable(request.user))
    course = pick_course(courses, request.GET.get('course'))
    if course is None:
        messages.error(request, 'There is no course to export yet.')
        return redirect('reports')

    data = report_context(request, course)
    response = HttpResponse(content_type='text/csv')
    response['Content-Disposition'] = f'attachment; filename="{course.code}-attendance-{timezone.localdate().isoformat()}.csv"'

    writer = csv.writer(response)
    writer.writerow([course.code, course.name, 'Classes held', data['classes_held']])
    writer.writerow([])
    writer.writerow(['Roll number', 'Student', 'Present', 'Late', 'Absent', 'Classes recorded', 'Attendance %'])
    for row in data['rows']:
        student = row['student']
        writer.writerow([
            student.roll_number or student.username,
            student.get_full_name() or student.username,
            row['present'], row['late'], row['absent'], row['held'],
            '' if row['percent'] is None else row['percent'],
        ])
    writer.writerow([])
    writer.writerow(['Class average', '' if data['overall']['percent'] is None else data['overall']['percent']])
    writer.writerow(['Below {}%'.format(stats.SHORTFALL), len(data['shortfalls'])])
    return response


# --- PART 2: ATTENDANCE CORRECTION SYSTEM VIEWS -----------------------------

@role_required(User.Role.STUDENT)
@require_POST
def request_correction(request):
    """Student submits an attendance correction request for an eligible published session."""
    session_id = request.POST.get('session_id')
    requested_status = request.POST.get('requested_status')
    reason = request.POST.get('reason', '').strip()

    if not reason:
        messages.error(request, "A reason explaining the correction request is required.")
        return redirect('student_home')

    if requested_status not in [Attendance.Status.PRESENT, Attendance.Status.LATE]:
        messages.error(request, "Requested status must be Present or Late.")
        return redirect('student_home')

    session = get_object_or_404(ClassSession, pk=session_id)
    course = session.course

    # Student must be enrolled
    if not course.students.filter(pk=request.user.pk).exists():
        raise PermissionDenied("You are not enrolled in this course.")

    # Session must be published
    if not session.is_published:
        messages.error(request, "Attendance for this class session is not published yet.")
        return redirect('student_home')

    # Strictly allow requests for today's classes only (Asia/Kolkata timezone)
    today_kolkata = timezone.localdate()
    if session.date != today_kolkata:
        messages.error(request, "Attendance corrections can be requested only for today's classes.")
        return redirect('student_home')

    # Rate limiting: max 5 requests per hour per student
    one_hour_ago = timezone.now() - timedelta(hours=1)
    if AttendanceCorrectionRequest.objects.filter(student=request.user, created_at__gte=one_hour_ago).count() >= 5:
        messages.error(request, "Submission rate limit reached (maximum 5 requests per hour). Please try again later.")
        return redirect('student_home')

    # Prevent duplicate active requests for the same student and session
    with transaction.atomic():
        if AttendanceCorrectionRequest.objects.filter(
            student=request.user, session=session, status=AttendanceCorrectionRequest.Status.PENDING
        ).exists():
            messages.error(request, "You already have a pending correction request for this class session.")
            return redirect('my_correction_requests')

        current_record = Attendance.objects.filter(student=request.user, session=session).first()
        orig_status = current_record.status if current_record else None

        req = AttendanceCorrectionRequest.objects.create(
            student=request.user,
            session=session,
            course=course,
            requested_status=requested_status,
            original_status=orig_status,
            reason=reason,
            teacher=course.faculty,
            status=AttendanceCorrectionRequest.Status.PENDING
        )

    messages.success(
        request,
        f"Correction request submitted for {course.code} ({session.date}, {session.session_identifier}). "
        f"Assigned to Prof. {course.faculty.get_full_name() or course.faculty.username} for review."
    )
    return redirect('my_correction_requests')


@role_required(User.Role.STUDENT)
def my_correction_requests(request):
    """Student portal tracking submitted correction requests and decision statuses."""
    requests_list = AttendanceCorrectionRequest.objects.filter(
        student=request.user
    ).select_related('course', 'session', 'teacher').order_by('-created_at')

    notifications = request.user.notifications.all().order_by('-created_at')[:10]

    return render(request, 'attendance/my_correction_requests.html', {
        'requests': requests_list,
        'notifications': notifications,
        'active_tab': 'corrections',
    })


@role_required(User.Role.STUDENT)
@require_POST
def cancel_correction_request(request, request_id):
    """Student cancels their pending correction request."""
    req = get_object_or_404(AttendanceCorrectionRequest, pk=request_id, student=request.user)
    if req.status != AttendanceCorrectionRequest.Status.PENDING:
        messages.error(request, "Only pending correction requests can be cancelled.")
        return redirect('my_correction_requests')

    req.status = AttendanceCorrectionRequest.Status.CANCELLED
    req.save(update_fields=['status', 'updated_at'])
    messages.success(request, f"Correction request for {req.course.code} ({req.session.date}) cancelled.")
    return redirect('my_correction_requests')


@role_required(User.Role.FACULTY, User.Role.ADMIN)
def faculty_corrections_inbox(request):
    """Authenticated faculty inbox to view and manage correction requests across courses."""
    return review_corrections(request)


def review_corrections(request):
    """
    Focused review panel showing requests included in an email batch (or authenticated inbox).
    Supports secure, expiring, passwordless email tokens without exposing full account access.
    Pure GET requests never mutate state.
    """
    batch_id = request.GET.get('batch')
    token = request.GET.get('token')

    batch = None
    access_method = 'session'
    target_teacher = None

    if batch_id:
        batch = get_object_or_404(AttendanceCorrectionBatch, batch_id=batch_id)
        target_teacher = batch.teacher

        if getattr(settings, 'REQUIRE_AUTHENTICATED_REVIEW', False):
            if not request.user.is_authenticated or (request.user != batch.teacher and request.user.role != User.Role.ADMIN and not request.user.is_superuser):
                messages.info(request, "Institutional policy requires signing in before reviewing attendance correction requests.")
                return redirect(f"{settings.LOGIN_URL}?next={request.get_full_path()}")
            access_method = 'session'
        elif token:
            valid, reason = batch.is_valid_for_access()
            if not valid:
                return render(request, 'attendance/review_error.html', {'error': reason, 'batch': batch})
            if not verify_token(token, batch.token_hash):
                return render(request, 'attendance/review_error.html', {'error': 'Invalid access token for this email notification.', 'batch': batch})
            access_method = 'email_token'
            request.session['restricted_batch_id'] = str(batch.batch_id)
        elif request.session.get('restricted_batch_id') == str(batch.batch_id):
            valid, reason = batch.is_valid_for_access()
            if not valid:
                return render(request, 'attendance/review_error.html', {'error': reason, 'batch': batch})
            access_method = 'email_token'
        elif request.user.is_authenticated and (request.user == batch.teacher or request.user.role == User.Role.ADMIN or request.user.is_superuser):
            access_method = 'session'
        else:
            return render(request, 'attendance/review_error.html', {
                'error': 'Access link expired, revoked, or requires authentication.',
                'batch': batch
            })
    elif request.user.is_authenticated and (request.user.role in [User.Role.FACULTY, User.Role.ADMIN] or request.user.is_superuser):
        access_method = 'session'
        target_teacher = request.user
    else:
        return redirect(f"{settings.LOGIN_URL}?next={request.get_full_path()}")

    # Retrieve requests to show
    if batch:
        # Show ONLY the exact requests included in this email batch
        requests_qs = batch.requests.select_related('student', 'course', 'session').order_by('status', '-created_at')
    else:
        if request.user.role == User.Role.ADMIN or request.user.is_superuser:
            requests_qs = AttendanceCorrectionRequest.objects.all().select_related('student', 'course', 'session', 'teacher').order_by('status', '-created_at')
        else:
            requests_qs = AttendanceCorrectionRequest.objects.filter(teacher=request.user).select_related('student', 'course', 'session').order_by('status', '-created_at')

    # Enrich each request with current attendance status
    req_items = []
    for req in requests_qs:
        rec = Attendance.objects.filter(student=req.student, session=req.session).first()
        req_items.append({
            'request': req,
            'current_attendance': rec,
            'current_status_display': rec.get_status_display() if rec else 'Entry missing',
        })

    pending_count = requests_qs.filter(status=AttendanceCorrectionRequest.Status.PENDING).count()

    # Calculate current calendar month boundaries (Asia/Kolkata timezone)
    kolkata_tz = ZoneInfo('Asia/Kolkata')
    now_kolkata = timezone.now().astimezone(kolkata_tz)
    start_of_month = now_kolkata.date().replace(day=1)
    if start_of_month.month == 12:
        start_of_next_month = start_of_month.replace(year=start_of_month.year + 1, month=1, day=1)
    else:
        start_of_next_month = start_of_month.replace(month=start_of_month.month + 1, day=1)
    month_name = now_kolkata.strftime('%B %Y')

    # Students with at least one session recorded as Late this month
    if batch:
        batch_course_ids = batch.requests.values_list('course_id', flat=True).distinct()
        batch_student_ids = batch.requests.values_list('student_id', flat=True).distinct()
        late_qs = Attendance.objects.filter(
            student_id__in=batch_student_ids,
            course_id__in=batch_course_ids,
            status=Attendance.Status.LATE,
            session__date__gte=start_of_month,
            session__date__lt=start_of_next_month,
            session__is_published=True
        ).select_related('student', 'course', 'session').order_by('session__date')
    else:
        if request.user.role == User.Role.ADMIN or request.user.is_superuser:
            relevant_courses = Course.objects.all()
        else:
            relevant_courses = request.user.courses_taught.all()
        late_qs = Attendance.objects.filter(
            course__in=relevant_courses,
            status=Attendance.Status.LATE,
            session__date__gte=start_of_month,
            session__date__lt=start_of_next_month,
            session__is_published=True
        ).select_related('student', 'course', 'session').order_by('session__date')

    late_by_student_course = {}
    for att in late_qs:
        key = (att.student_id, att.course_id)
        if key not in late_by_student_course:
            late_by_student_course[key] = {
                'student': att.student,
                'course': att.course,
                'late_count': 0,
                'sessions': [],
            }
        late_by_student_course[key]['late_count'] += 1
        late_by_student_course[key]['sessions'].append({
            'date': att.session.date,
            'identifier': att.session.session_identifier,
        })

    late_students_this_month = sorted(
        late_by_student_course.values(),
        key=lambda x: (-x['late_count'], x['student'].roll_number or x['student'].username)
    )

    return render(request, 'attendance/review_panel.html', {
        'batch': batch,
        'req_items': req_items,
        'pending_count': pending_count,
        'late_students_this_month': late_students_this_month,
        'current_month_name': month_name,
        'access_method': access_method,
        'is_email_access': (access_method == 'email_token'),
        'teacher': target_teacher or (request.user if request.user.is_authenticated else None),
        'active_tab': 'corrections',
    })


def _verify_review_permission(request, req):
    """Verify that current session or restricted token session is authorized to decide this request."""
    # Check course faculty responsibility still matches
    if req.course.faculty != req.teacher:
        return False, "Course instructor assignment has changed. Request permissions invalidated."

    if request.user.is_authenticated:
        if request.user == req.teacher or request.user.role == User.Role.ADMIN or request.user.is_superuser:
            return True, 'session'
    
    # Check restricted email access session
    restricted_batch_id = request.session.get('restricted_batch_id')
    if restricted_batch_id and req.batch and str(req.batch.batch_id) == str(restricted_batch_id):
        valid, reason = req.batch.is_valid_for_access()
        if valid:
            return True, 'email_token'
        return False, reason

    return False, "Unauthorized: decision requires an authenticated instructor session or valid email token."


@require_POST
def approve_correction_request(request, request_id):
    """
    Approve an attendance correction request with atomic row-locking,
    preventing duplicate updates, conflicting decisions, and stale overwrites.
    """
    req = get_object_or_404(AttendanceCorrectionRequest, pk=request_id)
    authorized, method_or_err = _verify_review_permission(request, req)
    if not authorized:
        raise PermissionDenied(method_or_err)

    redirect_target = request.POST.get('next') or reverse('review_corrections')
    if req.batch:
        redirect_target = f"{reverse('review_corrections')}?batch={req.batch.batch_id}"

    with transaction.atomic():
        # Lock request row
        locked_req = AttendanceCorrectionRequest.objects.select_for_update().get(pk=request_id)
        if locked_req.status != AttendanceCorrectionRequest.Status.PENDING:
            messages.info(request, f"This request was already decided ({locked_req.get_status_display()}).")
            return redirect(redirect_target)

        session = locked_req.session
        student = locked_req.student
        course = locked_req.course

        # Verify student is still enrolled
        if not course.students.filter(pk=student.pk).exists():
            messages.error(request, f"Cannot approve: {student.username} is no longer enrolled in {course.code}.")
            return redirect(redirect_target)

        # Retrieve or lock existing attendance record
        att_record = Attendance.objects.select_for_update().filter(student=student, session=session).first()
        prev_status = att_record.status if att_record else None

        # Determine responsible teacher user
        actor = request.user if request.user.is_authenticated else locked_req.teacher

        # Update exact student/session attendance row
        if att_record:
            att_record.status = locked_req.requested_status
            att_record.marked_by = actor
            att_record.save(update_fields=['status', 'marked_by', 'updated_at'])
        else:
            att_record = Attendance.objects.create(
                student=student,
                session=session,
                course=course,
                date=session.date,
                status=locked_req.requested_status,
                marked_by=actor
            )

        # Mark request as approved
        locked_req.status = AttendanceCorrectionRequest.Status.APPROVED
        locked_req.reviewed_at = timezone.now()
        locked_req.access_method = method_or_err
        locked_req.save(update_fields=['status', 'reviewed_at', 'access_method', 'updated_at'])

        # Create immutable audit log
        AttendanceAuditLog.objects.create(
            attendance=att_record,
            student=student,
            session=session,
            course=course,
            previous_status=prev_status,
            new_status=locked_req.requested_status,
            changed_by=actor,
            decision_reason="Approved student correction request.",
            access_method=method_or_err,
            correction_request=locked_req
        )

        # Create in-app and email notification record
        s_notif = StudentNotification.objects.create(
            student=student,
            correction_request=locked_req,
            message=f"Your attendance correction request for {course.code} ({session.date}) was APPROVED. "
                    f"Status updated to {locked_req.get_requested_status_display()}."
        )

        # Queue student decision email after transaction commits
        def notify_student():
            try:
                from .notifications import send_student_decision_email
                send_student_decision_email(s_notif, request_obj=request)
            except Exception:
                pass

        transaction.on_commit(notify_student)

    messages.success(
        request,
        f"Approved: Updated attendance for {student.roll_number or student.username} in {course.code} "
        f"to {locked_req.get_requested_status_display()} ({session.date}, {session.session_identifier})."
    )
    return redirect(redirect_target)


@require_POST
def reject_correction_request(request, request_id):
    """
    Reject an attendance correction request. Requires a short rejection reason.
    Leaves attendance unchanged.
    """
    req = get_object_or_404(AttendanceCorrectionRequest, pk=request_id)
    authorized, method_or_err = _verify_review_permission(request, req)
    if not authorized:
        raise PermissionDenied(method_or_err)

    rejection_reason = request.POST.get('rejection_reason', '').strip()
    redirect_target = request.POST.get('next') or reverse('review_corrections')
    if req.batch:
        redirect_target = f"{reverse('review_corrections')}?batch={req.batch.batch_id}"

    if not rejection_reason:
        messages.error(request, "A reason explaining the rejection is required.")
        return redirect(redirect_target)

    with transaction.atomic():
        locked_req = AttendanceCorrectionRequest.objects.select_for_update().get(pk=request_id)
        if locked_req.status != AttendanceCorrectionRequest.Status.PENDING:
            messages.info(request, f"This request was already decided ({locked_req.get_status_display()}).")
            return redirect(redirect_target)

        actor = request.user if request.user.is_authenticated else locked_req.teacher

        locked_req.status = AttendanceCorrectionRequest.Status.REJECTED
        locked_req.rejection_reason = rejection_reason
        locked_req.reviewed_at = timezone.now()
        locked_req.access_method = method_or_err
        locked_req.save(update_fields=['status', 'rejection_reason', 'reviewed_at', 'access_method', 'updated_at'])

        # Look up existing attendance record without modifying it
        att_record = Attendance.objects.filter(student=locked_req.student, session=locked_req.session).first()
        current_status = att_record.status if att_record else None

        # Audit log of rejection (attendance remains unchanged; missing entry represented consistently as None)
        AttendanceAuditLog.objects.create(
            attendance=att_record,
            student=locked_req.student,
            session=locked_req.session,
            course=locked_req.course,
            previous_status=current_status,
            new_status=current_status,
            changed_by=actor,
            decision_reason=f"Rejected: {rejection_reason}",
            access_method=method_or_err,
            correction_request=locked_req
        )

        # Create in-app and email notification record
        s_notif = StudentNotification.objects.create(
            student=locked_req.student,
            correction_request=locked_req,
            message=f"Your attendance correction request for {locked_req.course.code} ({locked_req.session.date}) "
                    f"was REJECTED. Reason: {rejection_reason}"
        )

        def notify_student():
            try:
                from .notifications import send_student_decision_email
                send_student_decision_email(s_notif, request_obj=request)
            except Exception:
                pass

        transaction.on_commit(notify_student)

    messages.info(request, f"Rejected correction request for {locked_req.student.username}. Reason recorded.")
    return redirect(redirect_target)


def api_student_attendance_report(request, student_id, course_id):
    """
    Returns subject-specific attendance statistics and correction history for a student
    to populate the reviewer's side drawer without revealing other courses or students.
    """
    student = get_object_or_404(User, pk=student_id, role=User.Role.STUDENT)
    course = get_object_or_404(Course, pk=course_id)

    # Permission check: must be teacher of course, or have valid restricted session for batch containing this student & course, or admin
    has_perm = False
    if request.user.is_authenticated:
        if request.user == course.faculty or request.user.role == User.Role.ADMIN or request.user.is_superuser:
            has_perm = True

    if not has_perm:
        batch_id = request.session.get('restricted_batch_id')
        if batch_id:
            batch = AttendanceCorrectionBatch.objects.filter(batch_id=batch_id).first()
            if batch and batch.is_valid_for_access()[0] and batch.teacher == course.faculty:
                if batch.requests.filter(student=student, course=course).exists():
                    has_perm = True

    if not has_perm:
        return JsonResponse({'error': 'Unauthorized'}, status=403)

    # Current calendar month boundaries (Asia/Kolkata timezone)
    kolkata_tz = ZoneInfo('Asia/Kolkata')
    now_kolkata = timezone.now().astimezone(kolkata_tz)
    start_of_month = now_kolkata.date().replace(day=1)
    if start_of_month.month == 12:
        start_of_next_month = start_of_month.replace(year=start_of_month.year + 1, month=1, day=1)
    else:
        start_of_next_month = start_of_month.replace(month=start_of_month.month + 1, day=1)
    month_name = now_kolkata.strftime('%B %Y')

    start_month_dt = timezone.datetime(start_of_month.year, start_of_month.month, 1, 0, 0, 0, tzinfo=kolkata_tz)
    start_next_month_dt = timezone.datetime(start_of_next_month.year, start_of_next_month.month, 1, 0, 0, 0, tzinfo=kolkata_tz)

    # 1. Subject metrics
    records = Attendance.objects.filter(student=student, course=course)
    course_sessions = course.sessions.filter(is_published=True)
    total_sessions_held = course_sessions.count()

    present_count = records.filter(status=Attendance.Status.PRESENT).count()
    late_count = records.filter(status=Attendance.Status.LATE).count()
    absent_count = records.filter(status=Attendance.Status.ABSENT).count()
    attended_count = present_count + late_count

    subject_pct = stats.percent(attended_count, total_sessions_held)

    # 2. Overall student metrics across all enrolled courses
    all_student_records = student.attendance_records.all()
    overall_totals = stats.totals(all_student_records)
    overall_pct = overall_totals['percent']

    # 3. Lateness details (actual class sessions recorded as Late: all time vs this month)
    actual_late_all_qs = records.filter(status=Attendance.Status.LATE).select_related('session').order_by('-session__date')
    actual_late_all_count = actual_late_all_qs.count()
    actual_late_all_sessions = [
        {
            'date': att.session.date.strftime('%d %b %Y'),
            'session': att.session.session_identifier,
        }
        for att in actual_late_all_qs
    ]

    actual_late_month_qs = records.filter(
        status=Attendance.Status.LATE,
        session__date__gte=start_of_month,
        session__date__lt=start_of_next_month
    ).select_related('session').order_by('-session__date')
    actual_late_month_count = actual_late_month_qs.count()
    actual_late_month_sessions = [
        {
            'date': att.session.date.strftime('%d %b %Y'),
            'session': att.session.session_identifier,
        }
        for att in actual_late_month_qs
    ]

    # 4. Previous correction requests history in this subject
    past_requests = AttendanceCorrectionRequest.objects.filter(
        student=student,
        course=course
    ).select_related('session').order_by('-created_at')

    total_requests_all_time = past_requests.count()
    pending_reqs = past_requests.filter(status=AttendanceCorrectionRequest.Status.PENDING).count()
    approved_reqs = past_requests.filter(status=AttendanceCorrectionRequest.Status.APPROVED).count()
    rejected_reqs = past_requests.filter(status=AttendanceCorrectionRequest.Status.REJECTED).count()
    cancelled_reqs = past_requests.filter(status=AttendanceCorrectionRequest.Status.CANCELLED).count()

    month_requests = past_requests.filter(created_at__gte=start_month_dt, created_at__lt=start_next_month_dt)
    requests_this_month = month_requests.count()

    # Requests specifically asking for Late
    late_requested_all_time = past_requests.filter(requested_status=Attendance.Status.LATE).count()
    late_requested_this_month = month_requests.filter(requested_status=Attendance.Status.LATE).count()

    # Recent attendance history (last 10 sessions)
    recent_history = []
    for s in course_sessions.order_by('-date', 'session_identifier')[:10]:
        att = records.filter(session=s).first()
        status_disp = att.get_status_display() if att else "Entry missing"
        status_code = att.status if att else "M"
        recent_history.append({
            'date': s.date.strftime('%d %b %Y'),
            'session': s.session_identifier,
            'status': status_disp,
            'status_code': status_code,
        })

    # Recent requests list
    req_history = []
    for r in past_requests[:10]:
        req_history.append({
            'date': r.session.date.strftime('%d %b %Y'),
            'session': r.session.session_identifier,
            'original_status': r.get_original_status_display() or 'Missing',
            'requested_status': r.get_requested_status_display(),
            'status': r.status.upper(),
            'reason': r.reason,
            'rejection_reason': r.rejection_reason,
            'reviewed_at': r.reviewed_at.strftime('%d %b %Y, %H:%M') if r.reviewed_at else None,
        })

    return JsonResponse({
        'student': {
            'username': student.username,
            'roll_number': student.roll_number or student.username,
            'full_name': student.get_full_name() or student.username,
        },
        'course': {
            'code': course.code,
            'name': course.name,
            'instructor': course.faculty.get_full_name() or course.faculty.username,
        },
        'current_month': month_name,
        'attendance': {
            'percent': f"{subject_pct:.1f}%" if subject_pct is not None else "0.0%",
            'overall_percent': f"{overall_pct:.1f}%" if overall_pct is not None else "0.0%",
            'held': total_sessions_held,
            'attended': attended_count,
            'present': present_count,
            'late': late_count,
            'absent': absent_count,
            'explanation': f"Attended {attended_count} of {total_sessions_held} published class sessions ({subject_pct if subject_pct is not None else 0.0}%). Late arrivals count as attended.",
        },
        'lateness': {
            'actual_late_all_time_count': actual_late_all_count,
            'actual_late_month_count': actual_late_month_count,
            'actual_late_month_sessions': actual_late_month_sessions,
            'actual_late_all_time_sessions': actual_late_all_sessions,
            'late_requested_all_time': late_requested_all_time,
            'late_requested_this_month': late_requested_this_month,
        },
        'requests': {
            'total_all_time': total_requests_all_time,
            'total_this_month': requests_this_month,
            'pending': pending_reqs,
            'approved': approved_reqs,
            'rejected': rejected_reqs,
            'cancelled': cancelled_reqs,
            'history': req_history,
        },
        'history': recent_history,
    })
