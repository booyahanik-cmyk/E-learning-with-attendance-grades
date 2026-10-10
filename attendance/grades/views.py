import json
from decimal import Decimal
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.http import JsonResponse
from django.shortcuts import render, redirect, get_object_or_404
from django.views.decorators.http import require_POST

from attendance.models import User, Course
from attendance.views import role_required
from .models import Semester, Subject, GradeRecord
from .utils import get_student_semester_grades, get_all_student_semesters


@login_required
def student_grades(request):
    """The Grade Management ledger for students: semester summary, marksheet, SGPA and print cards."""
    # If faculty or admin visits without specifying a student, allow viewing STU001 or themselves
    target_student = request.user
    if request.user.role in [User.Role.FACULTY, User.Role.ADMIN]:
        student_id = request.GET.get('student')
        if student_id:
            target_student = get_object_or_404(User, pk=student_id, role=User.Role.STUDENT)
        else:
            # Pick first available student or STU001 for demonstration
            demo_stu = User.objects.filter(role=User.Role.STUDENT).first()
            if demo_stu:
                target_student = demo_stu

    try:
        current_sem = int(request.GET.get('sem', 1))
    except (ValueError, TypeError):
        current_sem = 1

    sem_data = get_student_semester_grades(target_student, current_sem)
    all_sem_data = get_all_student_semesters(target_student)

    context = {
        'student': target_student,
        'current_sem': current_sem,
        'sem_data': sem_data,
        'all_sem_data_json': json.dumps(all_sem_data),
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

    students_data = []
    if selected_course:
        # Get or create a linked subject for this course if not yet present
        subject, _ = Subject.objects.get_or_create(
            code=selected_course.code,
            defaults={'name': selected_course.name, 'credits': 4, 'course': selected_course}
        )
        current_semester, _ = Semester.objects.get_or_create(number=1, defaults={'name': 'Semester 1', 'stamp_text': 'SEM 1'})

        for student in selected_course.students.all().order_by('roll_number', 'username'):
            record = GradeRecord.objects.filter(student=student, subject=subject, semester=current_semester).first()
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
        'students_data': students_data,
        'active_tab': 'grades',
    }
    return render(request, 'grades/faculty_grades.html', context)


@role_required(User.Role.FACULTY)
@require_POST
def save_student_marks(request):
    """Save or update marks entered by faculty for a student."""
    course_id = request.POST.get('course_id')
    student_id = request.POST.get('student_id')
    internal = request.POST.get('internal', '0').strip() or '0'
    external = request.POST.get('external', '0').strip() or '0'

    course = get_object_or_404(Course, pk=course_id, faculty=request.user)
    student = get_object_or_404(User, pk=student_id, role=User.Role.STUDENT)

    subject, _ = Subject.objects.get_or_create(
        code=course.code,
        defaults={'name': course.name, 'credits': 4, 'course': course}
    )
    semester, _ = Semester.objects.get_or_create(number=1, defaults={'name': 'Semester 1', 'stamp_text': 'SEM 1'})

    try:
        internal_val = Decimal(internal)
        external_val = Decimal(external)
    except Exception:
        messages.error(request, "Invalid numeric values entered for marks.")
        return redirect(f"/grades/manage/?course={course_id}")

    total_val = internal_val + external_val
    letter, point = GradeRecord.calculate_grade_and_point(total_val)

    GradeRecord.objects.update_or_create(
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
    messages.success(request, f"Updated marks for {student.roll_number or student.username} ({course.code}): Total {total_val}, Grade {letter}")
    return redirect(f"/grades/manage/?course={course_id}")


@login_required
def api_semester_grades(request, sem_id):
    """JSON API endpoint returning data for semester sem_id."""
    target_student = request.user
    if request.user.role in [User.Role.FACULTY, User.Role.ADMIN]:
        stu_id = request.GET.get('student')
        if stu_id:
            target_student = get_object_or_404(User, pk=stu_id, role=User.Role.STUDENT)
    
    data = get_student_semester_grades(target_student, sem_id)
    return JsonResponse(data)
