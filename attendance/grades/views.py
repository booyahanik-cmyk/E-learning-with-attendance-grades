import json
from decimal import Decimal, InvalidOperation
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.core.exceptions import PermissionDenied, ValidationError
from django.http import JsonResponse
from django.shortcuts import render, redirect, get_object_or_404
from django.views.decorators.http import require_POST

from attendance.models import User, Course
from attendance.views import role_required
from .models import Semester, Subject, GradeRecord
from .utils import get_student_semester_grades, get_all_student_semesters


def _filter_grades_for_faculty(sem_dict, faculty):
    """Filter subjects in semester grades dictionary to only those taught by the faculty."""
    faculty_course_codes = set(faculty.courses_taught.values_list('code', flat=True))
    filtered_subjects = [s for s in sem_dict.get('subjects', []) if s['code'] in faculty_course_codes]
    
    total_credits = sum(s['credits'] for s in filtered_subjects)
    total_credit_points = sum(Decimal(s['gradePoint']) * s['credits'] for s in filtered_subjects)
    sgpa = (total_credit_points / total_credits) if total_credits > 0 else Decimal('0.00')
    has_fail = any(s['grade'] == 'F' for s in filtered_subjects)
    
    raw_scores = [s['total'] for s in filtered_subjects]
    avg_raw = sum(raw_scores) / len(raw_scores) if raw_scores else 0.0
    best = max(filtered_subjects, key=lambda s: s['total']) if filtered_subjects else None

    return {
        "semester": sem_dict['semester'],
        "sgpa": f"{sgpa:.2f}" if filtered_subjects else "N/A",
        "totalSubjects": len(filtered_subjects),
        "status": ("FAIL" if has_fail else "PASS") if filtered_subjects else "No grades available",
        "totalCredits": total_credits,
        "stampText": sem_dict.get('stampText', f"SEM {sem_dict['semester']}"),
        "subjects": filtered_subjects,
        "avgScore": f"{avg_raw:.1f}" if filtered_subjects else "N/A",
        "highestSubject": f"{best['name']} ({best['code']} - {best['total']:.0f}/100)" if best else "N/A",
        "has_records": bool(filtered_subjects)
    }


@login_required
def student_grades(request):
    """The Grade Management ledger for students: semester summary, marksheet, SGPA and print cards."""
    target_student = request.user
    is_faculty_view = False

    if request.user.role == User.Role.STUDENT:
        # Students can only view their own grades. Disallow ?student= parameter
        target_student = request.user
    elif request.user.role == User.Role.FACULTY:
        is_faculty_view = True
        student_id = request.GET.get('student')
        if student_id:
            target_student = get_object_or_404(User, pk=student_id, role=User.Role.STUDENT)
            # Verify student is enrolled in at least one course taught by this faculty member
            is_enrolled = Course.objects.filter(faculty=request.user, students=target_student).exists()
            if not is_enrolled:
                raise PermissionDenied("You are not authorized to view grades for students not enrolled in your courses.")
        else:
            # Pick first student enrolled in this faculty's courses
            target_student = User.objects.filter(
                role=User.Role.STUDENT,
                courses__faculty=request.user
            ).distinct().first()
            if not target_student:
                # No enrolled students in faculty's courses
                return render(request, 'grades/grades.html', {
                    'student': request.user,
                    'current_sem': 1,
                    'sem_data': {
                        'semester': 1, 'sgpa': 'N/A', 'totalSubjects': 0,
                        'status': 'No grades available', 'totalCredits': 0,
                        'stampText': 'SEM 1', 'subjects': [], 'avgScore': 'N/A',
                        'highestSubject': 'N/A', 'has_records': False
                    },
                    'all_sem_data': {},
                    'available_semesters': Semester.objects.all().order_by('number'),
                    'active_tab': 'grades',
                    'no_enrolled_students': True,
                })
    elif request.user.role == User.Role.ADMIN or request.user.is_superuser:
        student_id = request.GET.get('student')
        if student_id:
            target_student = get_object_or_404(User, pk=student_id, role=User.Role.STUDENT)
        else:
            target_student = User.objects.filter(role=User.Role.STUDENT).first() or request.user

    available_semesters = list(Semester.objects.all().order_by('number'))
    default_sem_num = available_semesters[0].number if available_semesters else 1

    try:
        current_sem = int(request.GET.get('sem', default_sem_num))
    except (ValueError, TypeError):
        current_sem = default_sem_num

    sem_data = get_student_semester_grades(target_student, current_sem)
    all_sem_data = get_all_student_semesters(target_student)

    # Restrict faculty view to only the subjects and courses they are authorized to manage
    if is_faculty_view and request.user.role == User.Role.FACULTY:
        sem_data = _filter_grades_for_faculty(sem_data, request.user)
        filtered_all = {}
        for s_num, s_data in all_sem_data.items():
            filtered_all[s_num] = _filter_grades_for_faculty(s_data, request.user)
        all_sem_data = filtered_all

    context = {
        'student': target_student,
        'current_sem': current_sem,
        'sem_data': sem_data,
        'all_sem_data': all_sem_data,
        'available_semesters': available_semesters,
        'active_tab': 'grades',
    }
    return render(request, 'grades/grades.html', context)


@role_required(User.Role.FACULTY)
def faculty_grades(request):
    """Faculty portal to inspect course rosters, enter internal/external assessments, and track grade distribution."""
    courses = request.user.courses_taught.all().order_by('code')
    selected_course_id = request.GET.get('course')
    
    selected_course = None
    if selected_course_id:
        selected_course = courses.filter(pk=selected_course_id).first()
    elif courses.exists():
        selected_course = courses.first()

    available_semesters = list(Semester.objects.all().order_by('number'))
    if not available_semesters:
        Semester.objects.create(number=1, name='Semester 1', stamp_text='SEM 1')
        available_semesters = list(Semester.objects.all().order_by('number'))

    sem_req = request.GET.get('sem')
    selected_semester = None
    if sem_req:
        try:
            sem_num = int(sem_req)
            selected_semester = next((s for s in available_semesters if s.number == sem_num), None)
        except (ValueError, TypeError):
            selected_semester = None
    if not selected_semester:
        selected_semester = available_semesters[0]

    students_data = []
    if selected_course:
        subject, _ = Subject.objects.get_or_create(
            code=selected_course.code,
            defaults={'name': selected_course.name, 'credits': 4, 'course': selected_course}
        )

        for student in selected_course.students.all().order_by('roll_number', 'username'):
            record = GradeRecord.objects.filter(
                student=student,
                subject=subject,
                semester=selected_semester
            ).first()
            students_data.append({
                'student': student,
                'record': record,
                'internal': record.internal_marks if record else '',
                'external': record.external_marks if record else '',
                'total': record.total_marks if record else '',
                'grade': record.grade if record else '—',
                'grade_point': record.grade_point if record else '—',
            })

    context = {
        'courses': courses,
        'selected_course': selected_course,
        'available_semesters': available_semesters,
        'selected_semester': selected_semester,
        'students_data': students_data,
        'active_tab': 'grades',
    }
    return render(request, 'grades/faculty_grades.html', context)


@role_required(User.Role.FACULTY)
@require_POST
def save_student_marks(request):
    """Save or update marks entered by faculty for an authorized student."""
    course_id = request.POST.get('course_id')
    student_id = request.POST.get('student_id')
    semester_id = request.POST.get('semester_id')
    internal_raw = request.POST.get('internal')
    external_raw = request.POST.get('external')

    # Enforce faculty authorization for the course
    course = get_object_or_404(Course, pk=course_id, faculty=request.user)

    # Enforce student role and enrollment authorization
    student = get_object_or_404(User, pk=student_id, role=User.Role.STUDENT)
    if not course.students.filter(pk=student.pk).exists():
        raise PermissionDenied("Cannot enter marks: this student is not enrolled in your course.")

    # Enforce semester validation
    if semester_id:
        semester = get_object_or_404(Semester, pk=semester_id)
    else:
        semester = Semester.objects.order_by('number').first()
        if not semester:
            semester = Semester.objects.create(number=1, name='Semester 1', stamp_text='SEM 1')

    redirect_url = f"/grades/manage/?course={course.pk}&sem={semester.number}"

    # Enforce explicit, non-blank inputs (reject silent zero conversion)
    if internal_raw is None or internal_raw.strip() == '':
        messages.error(request, "Internal marks are required.")
        return redirect(redirect_url)
    if external_raw is None or external_raw.strip() == '':
        messages.error(request, "External marks are required.")
        return redirect(redirect_url)

    internal_str = internal_raw.strip()
    external_str = external_raw.strip()

    # Reject non-numeric, NaN, Infinity, negative, excessive precision, or out-of-bounds
    try:
        internal_val = Decimal(internal_str)
        external_val = Decimal(external_str)
    except (InvalidOperation, ValueError):
        messages.error(request, "Invalid numeric format entered for marks.")
        return redirect(redirect_url)

    if internal_val.is_nan() or internal_val.is_infinite() or external_val.is_nan() or external_val.is_infinite():
        messages.error(request, "Marks must be finite numeric values.")
        return redirect(redirect_url)

    if internal_val.as_tuple().exponent < -1 or external_val.as_tuple().exponent < -1:
        messages.error(request, "Marks cannot exceed 1 decimal place of precision.")
        return redirect(redirect_url)

    if internal_val < Decimal('0.0') or internal_val > Decimal('20.0'):
        messages.error(request, f"Internal marks must be between 0.0 and 20.0 (received {internal_val}).")
        return redirect(redirect_url)

    if external_val < Decimal('0.0') or external_val > Decimal('80.0'):
        messages.error(request, f"External marks must be between 0.0 and 80.0 (received {external_val}).")
        return redirect(redirect_url)

    total_val = internal_val + external_val
    if total_val < Decimal('0.0') or total_val > Decimal('100.0'):
        messages.error(request, f"Total marks must be between 0.0 and 100.0 (received {total_val}).")
        return redirect(redirect_url)

    # Retrieve or create subject linked to course
    subject, _ = Subject.objects.get_or_create(
        code=course.code,
        defaults={'name': course.name, 'credits': 4, 'course': course}
    )

    letter, point = GradeRecord.calculate_grade_and_point(total_val)

    record, _ = GradeRecord.objects.update_or_create(
        student=student,
        subject=subject,
        semester=semester,
        defaults={
            'internal_marks': internal_val,
            'external_marks': external_val,
            'total_marks': total_val,
            'grade': letter,
            'grade_point': point,
        }
    )

    messages.success(
        request,
        f"Saved marks for {student.roll_number or student.username} in {course.code} ({semester.name}): "
        f"Internal {internal_val}, External {external_val}, Total {total_val}, Grade {letter} ({point} GP)"
    )
    return redirect(redirect_url)


@login_required
def api_semester_grades(request, sem_id):
    """JSON API endpoint returning data for semester sem_id with strict authorization."""
    target_student = request.user
    is_faculty_view = False

    if request.user.role == User.Role.STUDENT:
        target_student = request.user
    elif request.user.role == User.Role.FACULTY:
        is_faculty_view = True
        stu_id = request.GET.get('student')
        if stu_id:
            target_student = get_object_or_404(User, pk=stu_id, role=User.Role.STUDENT)
            is_enrolled = Course.objects.filter(faculty=request.user, students=target_student).exists()
            if not is_enrolled:
                return JsonResponse({'error': 'Unauthorized'}, status=403)
        else:
            target_student = User.objects.filter(
                role=User.Role.STUDENT,
                courses__faculty=request.user
            ).distinct().first()
            if not target_student:
                return JsonResponse({'error': 'No enrolled students'}, status=404)
    elif request.user.role == User.Role.ADMIN or request.user.is_superuser:
        stu_id = request.GET.get('student')
        if stu_id:
            target_student = get_object_or_404(User, pk=stu_id, role=User.Role.STUDENT)

    data = get_student_semester_grades(target_student, sem_id)
    if is_faculty_view and request.user.role == User.Role.FACULTY:
        data = _filter_grades_for_faculty(data, request.user)

    return JsonResponse(data)
