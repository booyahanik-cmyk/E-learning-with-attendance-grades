from django.contrib.auth.decorators import login_required
from django.core.exceptions import PermissionDenied
from django.db.models import Count, Q
from django.http import Http404
from django.shortcuts import render, redirect, get_object_or_404
from django.views.decorators.http import require_POST
from django.contrib import messages

from attendance.models import User
from .models import LSCourse, LSLesson, LSEnrollment, LSProgress, LSVoucher


def _course_progress(user, course):
    """Return (total_lessons, completed, percent) for a user in a course."""
    total = course.lessons.count()
    done = LSProgress.objects.filter(
        user=user,
        lesson__course=course,
    ).count()
    pct = int(done * 100 / total) if total else 0
    return total, done, pct


@login_required
def course_catalog(request):
    """Browse all published courses with search, category filter, and student progress metrics."""
    if request.user.role in [User.Role.FACULTY, User.Role.ADMIN] or request.user.is_superuser:
        return faculty_dashboard(request)

    q = request.GET.get('q', '').strip()
    cat = request.GET.get('cat', '')

    # Distinct counts prevent SQL Cartesian product inflation between lessons and enrollments
    courses = LSCourse.objects.select_related('instructor').annotate(
        n_lessons=Count('lessons', distinct=True),
        n_students=Count('enrollments', distinct=True),
    ).filter(is_published=True)

    if q:
        courses = courses.filter(
            Q(title__icontains=q) | 
            Q(description__icontains=q) | 
            Q(category__icontains=q) |
            Q(lessons__title__icontains=q) |
            Q(lessons__content__icontains=q)
        ).distinct()
    if cat:
        courses = courses.filter(category=cat)

    courses = courses.order_by('-id')
    all_categories = list(
        LSCourse.objects.filter(is_published=True).values_list('category', flat=True).distinct()
    )

    # User overall statistics - only count published, accessible courses
    user_enrolled_courses = set(
        LSEnrollment.objects.filter(user=request.user).values_list('course_id', flat=True)
    )
    user_enrolled_count = len(user_enrolled_courses)
    user_completed_lessons = LSProgress.objects.filter(user=request.user).count()
    user_vouchers_count = LSVoucher.objects.filter(user=request.user).count()
    total_courses_count = LSCourse.objects.filter(is_published=True).count()

    # Pre-calculate progress for enrolled courses
    course_progress_map = {}
    if user_enrolled_courses:
        for c in courses:
            if c.id in user_enrolled_courses:
                course_progress_map[c.id] = _course_progress(request.user, c)

    # Attach progress directly to course objects for easy template rendering
    for c in courses:
        if c.id in course_progress_map:
            c.user_progress = course_progress_map[c.id]
        else:
            c.user_progress = None

    return render(request, 'learnsphere/catalog.html', {
        'courses': courses,
        'cats': sorted(all_categories),
        'q': q,
        'cat': cat,
        'active_tab': 'learnsphere',
        'metrics': {
            'total_courses': total_courses_count,
            'enrolled_count': user_enrolled_count,
            'completed_lessons': user_completed_lessons,
            'vouchers_count': user_vouchers_count,
        }
    })


@login_required
def course_detail(request, course_id):
    """View a single course with active lecture reader, curriculum list, progress, and rewards."""
    course = get_object_or_404(
        LSCourse.objects.select_related('instructor'),
        pk=course_id,
    )
    if not course.is_published:
        if request.user.role not in [User.Role.FACULTY, User.Role.ADMIN] and not request.user.is_superuser:
            raise Http404("Course not found or unpublished.")
        if course.instructor != request.user and request.user.role != User.Role.ADMIN and not request.user.is_superuser:
            raise Http404("Course not found or unpublished.")

    lessons = list(course.lessons.all().order_by('position', 'id'))
    enrolled = LSEnrollment.objects.filter(user=request.user, course=course).exists()
    done_ids = set()
    voucher = None
    stats = (len(lessons), 0, 0)

    if enrolled:
        done_ids = set(
            LSProgress.objects.filter(
                user=request.user, lesson__course=course
            ).values_list('lesson_id', flat=True)
        )
        voucher = LSVoucher.objects.filter(user=request.user, course=course).first()
        stats = _course_progress(request.user, course)

    # Determine active lecture
    active_lesson = None
    req_lesson_id = request.GET.get('lesson')
    
    if req_lesson_id:
        try:
            req_id_int = int(req_lesson_id)
            active_lesson = next((l for l in lessons if l.id == req_id_int), None)
        except (ValueError, TypeError):
            active_lesson = None

    if not active_lesson and lessons:
        if enrolled:
            # Pick first uncompleted lesson
            active_lesson = next((l for l in lessons if l.id not in done_ids), lessons[0])
        else:
            active_lesson = lessons[0]

    # Find prev and next lesson relative to active_lesson
    prev_lesson = None
    next_lesson = None
    if active_lesson and lessons:
        idx = lessons.index(active_lesson)
        if idx > 0:
            prev_lesson = lessons[idx - 1]
        if idx < len(lessons) - 1:
            next_lesson = lessons[idx + 1]

    is_active_done = (active_lesson.id in done_ids) if active_lesson else False

    return render(request, 'learnsphere/course_detail.html', {
        'course': course,
        'lessons': lessons,
        'active_lesson': active_lesson,
        'prev_lesson': prev_lesson,
        'next_lesson': next_lesson,
        'is_active_done': is_active_done,
        'enrolled': enrolled,
        'done_ids': done_ids,
        'voucher': voucher,
        'stats': stats,
        'active_tab': 'learnsphere',
    })


@login_required
@require_POST
def enroll(request, course_id):
    """Enroll the current student in an accessible published course."""
    if request.user.role != User.Role.STUDENT and not request.user.is_superuser:
        messages.error(request, 'Only students can enroll in academic courses.')
        return redirect('ls_course_detail', course_id=course_id)

    course = get_object_or_404(LSCourse, pk=course_id)
    if not course.is_published:
        messages.error(request, 'Cannot enroll in an unpublished course.')
        return redirect('ls_catalog')

    LSEnrollment.objects.get_or_create(user=request.user, course=course)
    messages.success(request, f'Successfully enrolled in "{course.title}"! Welcome to the class.')
    return redirect('ls_course_detail', course_id=course_id)


@login_required
@require_POST
def complete_lesson(request, lesson_id):
    """Mark a lesson as completed for the current enrolled student and guide to the next."""
    if request.user.role != User.Role.STUDENT and not request.user.is_superuser:
        messages.error(request, 'Only students can mark lessons as complete.')
        return redirect('ls_catalog')

    lesson = get_object_or_404(LSLesson, pk=lesson_id)
    course = lesson.course

    if not course.is_published:
        messages.error(request, 'Cannot complete lessons for an unpublished course.')
        return redirect('ls_catalog')

    # Must be enrolled
    if not LSEnrollment.objects.filter(user=request.user, course=course).exists():
        messages.error(request, 'You must be enrolled in this course to mark lessons complete.')
        return redirect('ls_course_detail', course_id=course.id)

    LSProgress.objects.get_or_create(user=request.user, lesson=lesson)

    # Check if course is fully complete
    total, done, pct = _course_progress(request.user, course)
    if total and done == total:
        LSVoucher.generate_for_user(request.user, course)
        messages.success(request, f'🎉 Congratulations! You have completed all {total} lectures in "{course.title}" and unlocked an exclusive reward voucher!')
        return redirect('ls_course_detail', course_id=course.id)

    # Find the next lesson in course order
    lessons = list(course.lessons.all().order_by('position', 'id'))
    curr_idx = -1
    for i, l in enumerate(lessons):
        if l.id == lesson.id:
            curr_idx = i
            break

    if curr_idx != -1 and curr_idx + 1 < len(lessons):
        next_les = lessons[curr_idx + 1]
        messages.success(request, f'Completed Lecture {lesson.position}: "{lesson.title}". Proceeding to next lecture!')
        return redirect(f"/learnsphere/course/{course.id}/?lesson={next_les.id}")

    return redirect('ls_course_detail', course_id=course.id)


@login_required
def my_learning(request):
    """Student portal dashboard showing enrolled tracks, completed lessons and vouchers."""
    if request.user.role in [User.Role.FACULTY, User.Role.ADMIN] or request.user.is_superuser:
        return faculty_dashboard(request)

    enrollments = LSEnrollment.objects.filter(user=request.user).select_related('course').order_by('-enrolled_at')
    
    items = []
    completed_courses_count = 0
    total_completed_lessons = LSProgress.objects.filter(user=request.user).count()

    for en in enrollments:
        total, done, pct = _course_progress(request.user, en.course)
        voucher = LSVoucher.objects.filter(user=request.user, course=en.course).first()
        if total and done == total:
            completed_courses_count += 1
        items.append({
            'enrollment': en,
            'course': en.course,
            'total': total,
            'done': done,
            'pct': pct,
            'voucher': voucher,
        })

    vouchers = LSVoucher.objects.filter(user=request.user).select_related('course').order_by('-issued_at')

    return render(request, 'learnsphere/my_learning.html', {
        'items': items,
        'vouchers': vouchers,
        'active_tab': 'learnsphere',
        'metrics': {
            'enrolled_courses': len(items),
            'completed_courses': completed_courses_count,
            'completed_lessons': total_completed_lessons,
            'vouchers_count': vouchers.count(),
        }
    })


@login_required
def add_course(request):
    """Instructor-only: create a new course."""
    if request.user.role not in [User.Role.FACULTY, User.Role.ADMIN] and not request.user.is_superuser:
        messages.error(request, 'Only instructors and administrators can create new courses.')
        return redirect('ls_catalog')

    if request.method == 'POST':
        title = request.POST.get('title', '').strip()
        category = request.POST.get('category', 'General').strip()
        icon = request.POST.get('icon', '').strip()
        description = request.POST.get('description', '').strip()

        if not title:
            messages.error(request, 'Course title is required.')
            return render(request, 'learnsphere/add_course.html', {'active_tab': 'learnsphere'})

        course = LSCourse.objects.create(
            title=title,
            category=category,
            icon=icon or '',
            description=description,
            instructor=request.user,
            is_published=False,
        )

        messages.success(request, f'Draft Course "{title}" created! You can now add lectures.')
        return redirect('ls_manage_lectures', course_id=course.id)

    return render(request, 'learnsphere/add_course.html', {'active_tab': 'learnsphere'})


@login_required
def faculty_dashboard(request):
    """Faculty/Admin overview of authored courses, total enrolments and materials."""
    if request.user.role not in [User.Role.FACULTY, User.Role.ADMIN] and not request.user.is_superuser:
        raise Http404()
    q = request.GET.get('q', '').strip()
    cat = request.GET.get('cat', '')
    
    courses = LSCourse.objects.annotate(
        n_lessons=Count('lessons', distinct=True),
        n_students=Count('enrollments', distinct=True)
    )
    if request.user.role == User.Role.FACULTY:
        courses = courses.filter(instructor=request.user)
    
    if q:
        courses = courses.filter(
            Q(title__icontains=q) | Q(category__icontains=q) | Q(lessons__title__icontains=q)
        ).distinct()
    if cat:
        courses = courses.filter(category=cat)
        
    courses = courses.order_by('-id')
    all_categories = list(LSCourse.objects.filter(id__in=courses.values('id')).values_list('category', flat=True).distinct()) if courses else []
    
    total_courses = courses.count()
    published_courses = courses.filter(is_published=True).count()
    total_enrolments = sum(c.n_students for c in courses)
    total_materials = sum(c.n_lessons for c in courses)
    
    return render(request, 'learnsphere/faculty_dashboard.html', {
        'courses': courses,
        'cats': sorted(all_categories),
        'q': q,
        'cat': cat,
        'active_tab': 'learnsphere',
        'metrics': {
            'total_courses': total_courses,
            'published_courses': published_courses,
            'total_enrolments': total_enrolments,
            'total_materials': total_materials,
        }
    })


@login_required
def edit_course(request, course_id):
    if request.user.role not in [User.Role.FACULTY, User.Role.ADMIN] and not request.user.is_superuser:
        raise Http404()
    course = get_object_or_404(LSCourse, pk=course_id)
    if course.instructor != request.user and request.user.role != User.Role.ADMIN and not request.user.is_superuser:
        messages.error(request, 'You can only edit courses that you authored.')
        return redirect('ls_catalog')
        
    if request.method == 'POST':
        title = request.POST.get('title', '').strip()
        category = request.POST.get('category', 'General').strip()
        icon = request.POST.get('icon', '').strip()
        description = request.POST.get('description', '').strip()
        
        if not title:
            messages.error(request, 'Course title is required.')
            return render(request, 'learnsphere/edit_course.html', {'course': course, 'active_tab': 'learnsphere'})
            
        course.title = title
        course.category = category
        course.icon = icon or ''
        course.description = description
        course.save()
        
        messages.success(request, f'Course "{title}" updated successfully.')
        return redirect('ls_catalog')
        
    return render(request, 'learnsphere/edit_course.html', {'course': course, 'active_tab': 'learnsphere'})


@login_required
def delete_course(request, course_id):
    if request.user.role not in [User.Role.FACULTY, User.Role.ADMIN] and not request.user.is_superuser:
        raise Http404()
    course = get_object_or_404(LSCourse, pk=course_id)
    if course.instructor != request.user and request.user.role != User.Role.ADMIN and not request.user.is_superuser:
        messages.error(request, 'You can only delete courses that you authored.')
        return redirect('ls_catalog')
        
    if request.method == 'POST':
        title = course.title
        course.delete()
        messages.success(request, f'Course "{title}" has been deleted.')
        return redirect('ls_catalog')
        
    return render(request, 'learnsphere/delete_course_confirm.html', {'course': course, 'active_tab': 'learnsphere'})


@login_required
def toggle_publish(request, course_id):
    if request.user.role not in [User.Role.FACULTY, User.Role.ADMIN] and not request.user.is_superuser:
        raise Http404()
    course = get_object_or_404(LSCourse, pk=course_id)
    if course.instructor != request.user and request.user.role != User.Role.ADMIN and not request.user.is_superuser:
        messages.error(request, 'You can only publish or unpublish courses you authored.')
        return redirect('ls_catalog')
        
    if request.method == 'POST':
        course.is_published = not course.is_published
        course.save()
        status_str = 'published and available to students' if course.is_published else 'unpublished and moved to drafts'
        messages.success(request, f'Course "{course.title}" is now {status_str}.')
        
    return redirect('ls_catalog')


@login_required
def manage_lectures(request, course_id):
    if request.user.role not in [User.Role.FACULTY, User.Role.ADMIN] and not request.user.is_superuser:
        raise Http404()
    course = get_object_or_404(LSCourse, pk=course_id)
    if course.instructor != request.user and request.user.role != User.Role.ADMIN and not request.user.is_superuser:
        messages.error(request, 'You can only manage lectures for courses you authored.')
        return redirect('ls_catalog')
        
    lessons = course.lessons.all().order_by('position', 'id')
    
    if request.method == 'POST':
        action = request.POST.get('action')
        if action == 'add':
            title = request.POST.get('title', '').strip()
            content = request.POST.get('content', '').strip()
            if not title:
                messages.error(request, 'Lecture title is required.')
            else:
                next_pos = (lessons.last().position + 1) if lessons.exists() else 1
                LSLesson.objects.create(
                    course=course,
                    title=title,
                    content=content,
                    position=next_pos
                )
                messages.success(request, f'Lecture "{title}" added.')
            return redirect('ls_manage_lectures', course_id=course.id)
            
        elif action == 'edit':
            lesson_id = request.POST.get('lesson_id')
            lesson = get_object_or_404(LSLesson, pk=lesson_id, course=course)
            title = request.POST.get('title', '').strip()
            content = request.POST.get('content', '').strip()
            if not title:
                messages.error(request, 'Lecture title is required.')
            else:
                lesson.title = title
                lesson.content = content
                lesson.save()
                messages.success(request, f'Lecture "{title}" updated.')
            return redirect('ls_manage_lectures', course_id=course.id)
            
        elif action == 'delete':
            lesson_id = request.POST.get('lesson_id')
            lesson = get_object_or_404(LSLesson, pk=lesson_id, course=course)
            title = lesson.title
            lesson.delete()
            messages.success(request, f'Lecture "{title}" deleted.')
            return redirect('ls_manage_lectures', course_id=course.id)
            
    return render(request, 'learnsphere/manage_lectures.html', {
        'course': course,
        'lessons': lessons,
        'active_tab': 'learnsphere'
    })
