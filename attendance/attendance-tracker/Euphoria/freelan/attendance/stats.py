"""Attendance figures, derived on demand.

Nothing here is stored: every percentage is recomputed from Attendance rows, so
saving a register immediately moves the faculty dashboard, the student portal and
the reports together. All of the pages share these helpers rather than each
re-inventing the arithmetic.
"""

from datetime import timedelta

from django.db.models import Count, Max, Q
from django.utils import timezone

from .models import Attendance

# A late arrival still attended the class; only 'A' counts against a student.
ATTENDED = (Attendance.Status.PRESENT, Attendance.Status.LATE)
ATTENDED_Q = Q(status__in=ATTENDED)

SHORTFALL = 75  # the college's debarment line, used by the reports page
HEALTHY = 85    # at or above this a figure is shown as a "present" stamp

# Counts reused by every group-by below.
_TALLY = {
    'held': Count('id'),
    'present': Count('id', filter=Q(status=Attendance.Status.PRESENT)),
    'late': Count('id', filter=Q(status=Attendance.Status.LATE)),
    'absent': Count('id', filter=Q(status=Attendance.Status.ABSENT)),
}


def percent(attended, held):
    """Attendance percentage, or None when no class has been held yet."""
    if not held:
        return None
    return round(100 * attended / held, 1)


def stamp(pct):
    """The existing stamp class that matches a percentage."""
    if pct is None:
        return 'stamp-late'
    if pct >= HEALTHY:
        return 'stamp-present'
    if pct >= SHORTFALL:
        return 'stamp-late'
    return 'stamp-absent'


def _row(tally, **extra):
    """Turn one group-by result into the dict the templates read."""
    held = tally.get('held', 0)
    attended = tally.get('present', 0) + tally.get('late', 0)
    pct = percent(attended, held)
    row = {
        'held': held,
        'present': tally.get('present', 0),
        'late': tally.get('late', 0),
        'absent': tally.get('absent', 0),
        'attended': attended,
        'percent': pct,
        'stamp': stamp(pct),
        'low': pct is not None and pct < SHORTFALL,
    }
    row.update(extra)
    return row


def totals(records):
    """One summary row for any Attendance queryset."""
    return _row(records.aggregate(**_TALLY))


def by_course(student):
    """A student's attendance per enrolled course, ordered by course code."""
    tallies = {
        t['course']: t
        for t in Attendance.objects.filter(student=student).values('course').annotate(**_TALLY)
    }
    return [
        _row(tallies.get(course.id, {}), course=course)
        for course in student.courses.select_related('faculty').order_by('code')
    ]


def by_student(course):
    """Every enrolled student's attendance in one course, ordered by roll number."""
    tallies = {
        t['student']: t
        for t in course.attendance_records.values('student').annotate(**_TALLY)
    }
    return [
        _row(tallies.get(student.id, {}), student=student)
        for student in course.students.order_by('roll_number', 'username')
    ]


def shortfalls(rows):
    """The rows sitting below the debarment line, worst first."""
    short = [r for r in rows if r['percent'] is not None and r['percent'] < SHORTFALL]
    return sorted(short, key=lambda r: r['percent'])


def class_dates(course):
    """Dates this course has a register for, newest first."""
    return list(
        course.attendance_records.order_by('-date').values_list('date', flat=True).distinct()
    )


def week_start(day):
    """The Monday of that day's week."""
    return day - timedelta(days=day.weekday())


def daily_percentages(records, start, days):
    """[(date, row)] for `days` consecutive dates from `start`, gaps included."""
    tallies = {
        t['date']: t
        for t in records.filter(date__gte=start, date__lt=start + timedelta(days=days))
        .values('date')
        .annotate(**_TALLY)
    }
    return [
        (start + timedelta(days=offset), _row(tallies.get(start + timedelta(days=offset), {})))
        for offset in range(days)
    ]


def recent_registers(records, limit=5):
    """The last few saved registers, one row per course and date."""
    groups = (
        records.values('course__code', 'course__name', 'date', 'marked_by__username')
        .annotate(saved_at=Max('created_at'), **_TALLY)
        .order_by('-date', '-saved_at')[:limit]
    )
    return [
        _row(
            g,
            code=g['course__code'],
            name=g['course__name'],
            date=g['date'],
            marked_by=g['marked_by__username'],
        )
        for g in groups
    ]


def faculty_overview(faculty):
    """Everything the faculty dashboard shows, from one place."""
    courses = list(
        faculty.courses_taught.annotate(enrolled=Count('students', distinct=True)).order_by('code')
    )
    records = Attendance.objects.filter(course__faculty=faculty)
    today = timezone.localdate()
    this_monday = week_start(today)

    overall = totals(records)
    this_week = totals(records.filter(date__gte=this_monday))
    last_week = totals(
        records.filter(date__gte=this_monday - timedelta(days=7), date__lt=this_monday)
    )
    delta = None
    if this_week['percent'] is not None and last_week['percent'] is not None:
        delta = round(this_week['percent'] - last_week['percent'], 1)

    marked_today = set(
        records.filter(date=today).values_list('course_id', flat=True).distinct()
    )
    at_risk = {
        row['student'].id
        for course in courses
        for row in shortfalls(by_student(course))
    }

    return {
        'courses': courses,
        'overall': overall,
        'this_week': this_week,
        'week_delta': delta,
        'today': today,
        'today_totals': totals(records.filter(date=today)),
        'registers_saved_today': len(marked_today),
        'registers_open_today': [c for c in courses if c.id not in marked_today],
        'at_risk_count': len(at_risk),
        'threshold': SHORTFALL,
        'week_days': daily_percentages(records, this_monday, 7),
        'recent': recent_registers(records),
    }
