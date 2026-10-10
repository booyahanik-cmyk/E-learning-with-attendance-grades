"""Fill an empty database with a small, believable college so the app can be demoed.

Safe to re-run: accounts, courses and enrolments are matched on their identifiers,
and attendance rows rely on the unique(student, course, date) constraint instead of
being deleted and rewritten. Passwords are generated at run time and printed once --
no credentials live in this file.
"""

import random
from datetime import timedelta

from django.core.management.base import BaseCommand
from django.utils import timezone
from django.utils.crypto import get_random_string

from attendance.models import Attendance, Course, User

FACULTY = [
    ('EMP2001', 'Sunita', 'Kulkarni'),
    ('EMP2002', 'Anil', 'Deshpande'),
]

COURSES = [
    ('CS301', 'Database Systems', 'EMP2001'),
    ('CS204', 'Data Structures', 'EMP2001'),
    ('CS110', 'Intro to Programming', 'EMP2002'),
]

# Roll number, first name, last name, and roughly how often they turn up.
STUDENTS = [
    ('23CS014', 'Ananya', 'Rao', 0.96),
    ('23CS015', 'Devansh', 'Iyer', 0.74),
    ('23CS016', 'Priya', 'Menon', 0.61),
    ('23CS017', 'Kabir', 'Shah', 0.95),
    ('23CS018', 'Nisha', 'Thomas', 0.88),
    ('23CS019', 'Rohan', 'Verma', 0.70),
    ('23CS020', 'Sana', 'Gupta', 1.00),
    ('23CS021', 'Arjun', 'Nair', 0.64),
    ('23CS022', 'Meera', 'Pillai', 0.80),
    ('23CS023', 'Vikram', 'Bose', 0.91),
    ('23CS024', 'Tara', 'Krishnan', 0.85),
    ('23CS025', 'Imran', 'Sheikh', 0.78),
]


class Command(BaseCommand):
    help = 'Create demo faculty, students, courses, enrolments and attendance history.'

    def add_arguments(self, parser):
        parser.add_argument('--weeks', type=int, default=4,
                            help='Weeks of class days to generate (default 4).')
        parser.add_argument('--password',
                            help='Password for accounts created now. Random if omitted.')

    def handle(self, *args, **options):
        password = options['password'] or get_random_string(12)
        rng = random.Random(20260904)  # same demo data every run
        created = []

        def account(username, first, last, role, **fields):
            user, is_new = User.objects.get_or_create(
                username=username,
                defaults={'first_name': first, 'last_name': last, 'role': role, **fields},
            )
            if is_new:
                user.set_password(password)  # never touch an existing account's password
                user.save(update_fields=['password'])
                created.append(user)
            return user

        faculty = {
            emp: account(emp, first, last, User.Role.FACULTY, employee_id=emp)
            for emp, first, last in FACULTY
        }
        students = [
            account(roll, first, last, User.Role.STUDENT, roll_number=roll)
            for roll, first, last, _ in STUDENTS
        ]
        admin = account('admin', 'College', 'Admin', User.Role.ADMIN,
                        is_staff=True, is_superuser=True, email='admin@college.edu')

        courses = []
        for code, name, emp in COURSES:
            course, _ = Course.objects.get_or_create(
                code=code, defaults={'name': name, 'faculty': faculty[emp]}
            )
            courses.append(course)

        # CS301 and CS110 take everyone; CS204 takes the first eight.
        rosters = {'CS301': students, 'CS204': students[:8], 'CS110': students}
        for course in courses:
            course.students.add(*rosters[course.code])

        reliability = {roll: score for roll, _, _, score in STUDENTS}
        rows, days = [], self.class_days(options['weeks'])
        for course in courses:
            roster = rosters[course.code]
            for day in days:
                if rng.random() < 0.2:
                    continue  # not every course meets every day
                for student in roster:
                    score = reliability[student.username]
                    draw = rng.random()
                    if draw < score - 0.06:
                        status = Attendance.Status.PRESENT
                    elif draw < score + 0.04:
                        status = Attendance.Status.LATE
                    else:
                        status = Attendance.Status.ABSENT
                    rows.append(Attendance(
                        student=student, course=course, date=day,
                        status=status, marked_by=course.faculty,
                    ))
        # ignore_conflicts leans on unique(student, course, date): existing marks stand.
        Attendance.objects.bulk_create(rows, ignore_conflicts=True)

        self.report(created, password, courses, days, admin)

    @staticmethod
    def class_days(weeks):
        """Weekdays from `weeks` ago up to today."""
        today = timezone.localdate()
        span = [today - timedelta(days=offset) for offset in range(weeks * 7)]
        return sorted(day for day in span if day.weekday() < 5)

    def report(self, created, password, courses, days, admin):
        self.stdout.write(self.style.SUCCESS('Demo data ready.'))
        self.stdout.write('  courses: {}'.format(', '.join(c.code for c in courses)))
        self.stdout.write('  students: {}'.format(User.objects.filter(role=User.Role.STUDENT).count()))
        self.stdout.write('  attendance rows: {} across {} class days'.format(
            Attendance.objects.count(), len(days)))
        if not created:
            self.stdout.write('  accounts: all already existed, passwords left untouched')
            return
        self.stdout.write('')
        self.stdout.write('New accounts (all share this one generated password):')
        self.stdout.write('  password: {}'.format(password))
        for user in created:
            self.stdout.write('  {:10} {}'.format(user.username, user.get_role_display()))
        if admin in created:
            self.stdout.write('Sign in as "admin" for Django admin at /admin/.')
