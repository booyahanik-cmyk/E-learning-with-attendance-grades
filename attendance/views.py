import csv
from datetime import timedelta
from functools import wraps

from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.contrib.auth.views import LoginView
from django.core.exceptions import PermissionDenied
from django.db import transaction
from django.http import Http404, HttpResponse
from django.shortcuts import redirect, render
from django.urls import reverse
from django.utils import timezone
from django.utils.dateparse import parse_date

from . import stats
from .forms import StudentRegistrationForm
from .models import Attendance, Course, User


def home_url_for(user):
    """The page an account belongs on after signing in."""
    if user.role == User.Role.FACULTY:
        return reverse('faculty_dashboard')
    if user.role == User.Role.ADMIN or user.is_superuser:
        return reverse('admin:index')  # admins keep using Django admin
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
    """Django's own login, rendered in the existing index.html and routed by role.

    Overriding get_default_redirect_url (not get_success_url) keeps Django's
    handling of ?next=, so protected pages still resume after signing in.
    """

    template_name = 'attendance/index.html'
    redirect_authenticated_user = True

    def get_default_redirect_url(self):
        return home_url_for(self.request.user)


def register(request):
    """Public sign-up. Student accounts only -- see StudentRegistrationForm."""
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
    """The student portal: their courses and their own attendance, from the database."""
    records = request.user.attendance_records.select_related('course')
    return render(request, 'attendance/student_dashboard.html', {
        'courses': stats.by_course(request.user),
        'overall': stats.totals(records),
        'history': records.order_by('-date', 'course__code')[:10],
        'shortfall': stats.SHORTFALL,
        'active_tab': 'attendance',
    })


@role_required(User.Role.FACULTY)
def faculty_dashboard(request):
    """Real figures for the signed-in faculty across the courses they teach."""
    ctx = stats.faculty_overview(request.user)
    ctx['active_tab'] = 'dashboard'
    return render(request, 'attendance/dashboard.html', ctx)


# --- attendance register ----------------------------------------------------

def teachable(user):
    """The courses this account may open a register for."""
    if user.role == User.Role.ADMIN or user.is_superuser:
        return Course.objects.select_related('faculty').order_by('code')  # admins see everything
    return user.courses_taught.select_related('faculty').order_by('code')


def pick_course(courses, raw):
    """The requested course, or the first one available. 404 on anything else.

    Scoping the lookup to `courses` is what stops one faculty from reading
    another's roster by editing the ?course= id.
    """
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


def save_register(request, course, day):
    """Upsert one Attendance row per marked student. Returns (saved, unmarked)."""
    allowed = set(Attendance.Status.values)
    saved, unmarked = 0, []
    with transaction.atomic():
        for student in course.students.order_by('roll_number', 'username'):
            status = request.POST.get('s{}'.format(student.pk))
            if status not in allowed:
                unmarked.append(student.roll_number or student.username)
                continue
            # update_or_create honours unique(student, course, date): re-saving a
            # register corrects the existing rows instead of duplicating them.
            Attendance.objects.update_or_create(
                student=student, course=course, date=day,
                defaults={'status': status, 'marked_by': request.user},
            )
            saved += 1
    return saved, unmarked


@role_required(User.Role.FACULTY)
def attendance_register(request):
    """Mark today's (or any day's) roll call for one course."""
    courses = list(teachable(request.user))
    course = pick_course(courses, request.POST.get('course') or request.GET.get('course'))
    day = pick_date(request, request.POST.get('date') or request.GET.get('date'))

    if request.method == 'POST':
        if course is None:
            messages.error(request, 'You have no courses to mark. Ask an admin to assign one.')
        elif day > timezone.localdate():
            messages.error(request, 'A register cannot be saved for a future date.')
        elif not course.students.exists():
            messages.error(request, 'No students are enrolled in {} yet.'.format(course.code))
        else:
            saved, unmarked = save_register(request, course, day)
            if saved:
                messages.success(request, 'Register saved: {} student{} marked in {} for {}.'.format(
                    saved, '' if saved == 1 else 's', course.code, day.isoformat()))
            if unmarked:
                messages.error(request, 'Left unmarked: {}.'.format(', '.join(unmarked)))
            # Redirect after POST so a refresh cannot re-submit the register.
            return redirect('{}?course={}&date={}'.format(
                reverse('attendance_register'), course.pk, day.isoformat()))

    rows, marks = [], {}
    if course is not None:
        marks = dict(course.attendance_records.filter(date=day).values_list('student_id', 'status'))
        rows = stats.by_student(course)
        for row in rows:
            row['mark'] = marks.get(row['student'].pk)

    return render(request, 'attendance/attendance.html', {
        'courses': courses,
        'course': course,
        'day': day,
        'today': timezone.localdate(),
        'rows': rows,
        'marked': stats.totals(course.attendance_records.filter(date=day)) if course else None,
        'saved_before': bool(marks),
        'active_tab': 'attendance',
    })


# --- reports ---------------------------------------------------------------

HEATMAP_DAYS = 28  # four weeks, matching the grid in the design


def report_context(request, course):
    """The figures behind both the reports page and its CSV export."""
    rows = stats.by_student(course)
    held = stats.class_dates(course)
    start = timezone.localdate() - timedelta(days=HEATMAP_DAYS - 1)
    days = []
    for day, row in stats.daily_percentages(course.attendance_records, start, HEATMAP_DAYS):
        days.append({'date': day, 'level': heat_level(row), 'row': row})
    return {
        'course': course,
        'rows': rows,
        'shortfalls': stats.shortfalls(rows),
        'overall': stats.totals(course.attendance_records),
        'classes_held': len(held),
        'last_class': held[0] if held else None,
        'perfect': [r for r in rows if r['held'] and r['percent'] == 100],
        'heatmap': days,
        'threshold': stats.SHORTFALL,
    }


def heat_level(row):
    """The data-lvl the existing heatmap CSS and legend expect (0 = no class held)."""
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
    """Semester patterns for one course, computed from its attendance rows."""
    courses = list(teachable(request.user))
    course = pick_course(courses, request.GET.get('course'))
    context = {'courses': courses, 'course': None, 'active_tab': 'reports'}
    if course is not None:
        context.update(report_context(request, course))
    return render(request, 'attendance/reports.html', context)


@role_required(User.Role.FACULTY)
def reports_export(request):
    """The same report as a CSV download, written with the standard library."""
    courses = list(teachable(request.user))
    course = pick_course(courses, request.GET.get('course'))
    if course is None:
        messages.error(request, 'There is no course to export yet.')
        return redirect('reports')

    data = report_context(request, course)
    response = HttpResponse(content_type='text/csv')
    response['Content-Disposition'] = 'attachment; filename="{}-attendance-{}.csv"'.format(
        course.code, timezone.localdate().isoformat())

    writer = csv.writer(response)
    writer.writerow([course.code, course.name, 'Classes held', data['classes_held']])
    writer.writerow([])
    writer.writerow(['Roll number', 'Student', 'Present', 'Late', 'Absent',
                     'Classes recorded', 'Attendance %'])
    for row in data['rows']:
        student = row['student']
        writer.writerow([
            student.roll_number or student.username,
            student.get_full_name() or student.username,
            row['present'], row['late'], row['absent'], row['held'],
            '' if row['percent'] is None else row['percent'],
        ])
    writer.writerow([])
    writer.writerow(['Class average', '' if data['overall']['percent'] is None
                     else data['overall']['percent']])
    writer.writerow(['Below {}%'.format(stats.SHORTFALL), len(data['shortfalls'])])
    return response
