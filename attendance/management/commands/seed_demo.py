"""Fill an empty database with a small, believable college so the app can be demoed.

Safe to re-run: accounts, courses and enrolments are matched on their identifiers,
and attendance rows rely on session/student constraints instead of being deleted.
Passwords are generated or configured, and no raw secrets live in code.
"""

import hashlib
import random
import secrets
from datetime import timedelta

from django.core.management.base import BaseCommand
from django.utils import timezone
from django.utils.crypto import get_random_string

from attendance.models import (
    Attendance, Course, User,
    ClassSession, AttendanceCorrectionBatch, AttendanceCorrectionRequest,
    AttendanceAuditLog, StudentNotification, AttendanceCorrectionWindowExtension
)
from attendance.notifications import create_token

FACULTY = [
    ('EMP2001', 'Sunita', 'Kulkarni'),
    ('EMP2002', 'Anil', 'Deshpande'),
    ('EMP1023', 'Rajesh', 'Sharma'),
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
    help = 'Create demo faculty, students, courses, enrolments, attendance history and correction scenarios.'

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
            emp: account(emp, first, last, User.Role.FACULTY, employee_id=emp, email=f"{emp.lower()}@college.edu")
            for emp, first, last in FACULTY
        }
        students = [
            account(roll, first, last, User.Role.STUDENT, roll_number=roll, email=f"{roll.lower()}@college.edu")
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
        days = self.class_days(options['weeks'])
        for course in courses:
            roster = rosters[course.code]
            for day in days:
                if rng.random() < 0.2:
                    continue  # not every course meets every day
                session, _ = ClassSession.objects.get_or_create(
                    course=course,
                    date=day,
                    session_identifier='Session 1',
                    defaults={'is_published': True}
                )
                for student in roster:
                    score = reliability[student.username]
                    draw = rng.random()
                    if draw < score - 0.06:
                        status = Attendance.Status.PRESENT
                    elif draw < score + 0.04:
                        status = Attendance.Status.LATE
                    else:
                        status = Attendance.Status.ABSENT

                    Attendance.objects.get_or_create(
                        student=student,
                        session=session,
                        defaults={
                            'course': course,
                            'date': day,
                            'status': status,
                            'marked_by': course.faculty,
                        }
                    )

        from django.core.management import call_command
        try:
            call_command('seed_grades')
        except Exception:
            pass

        # === POPULATE SPECIFIC PART 2 & PART 3 PREVIEW DEMO CASES ===
        cs301 = Course.objects.get(code='CS301')
        cs204 = Course.objects.get(code='CS204')
        cs110 = Course.objects.get(code='CS110')
        prof_sunita = faculty['EMP2001']
        prof_anil = faculty['EMP2002']

        stu_ananya = User.objects.get(username='23CS014')
        stu_devansh = User.objects.get(username='23CS015')
        stu_priya = User.objects.get(username='23CS016')
        stu_kabir = User.objects.get(username='23CS017')
        stu_nisha = User.objects.get(username='23CS018')

        # Recent class days
        d_recent = days[-1] if days else timezone.localdate()
        d_two_days = days[-2] if len(days) > 1 else d_recent - timedelta(days=2)
        d_four_days = days[-3] if len(days) > 2 else d_recent - timedelta(days=4)
        d_five_days = days[-4] if len(days) > 3 else d_recent - timedelta(days=5)

        # 1. Two sessions of the same subject on one date (CS301 on d_two_days)
        sess_lecture, _ = ClassSession.objects.get_or_create(
            course=cs301,
            date=d_two_days,
            session_identifier='Session 1 (Lecture: Normalization)',
            defaults={'is_published': True}
        )
        sess_lab, _ = ClassSession.objects.get_or_create(
            course=cs301,
            date=d_two_days,
            session_identifier='Session 2 (Lab: SQL Queries)',
            defaults={'is_published': True}
        )

        # 2. Case: Incorrect Absent entry
        # Devansh was marked Absent in Session 1
        att_devansh, _ = Attendance.objects.get_or_create(
            student=stu_devansh,
            session=sess_lecture,
            defaults={
                'course': cs301,
                'date': d_two_days,
                'status': Attendance.Status.ABSENT,
                'marked_by': prof_sunita,
            }
        )
        att_devansh.status = Attendance.Status.ABSENT
        att_devansh.save()

        req_devansh, _ = AttendanceCorrectionRequest.objects.get_or_create(
            student=stu_devansh,
            session=sess_lecture,
            defaults={
                'course': cs301,
                'teacher': prof_sunita,
                'original_status': Attendance.Status.ABSENT,
                'requested_status': Attendance.Status.PRESENT,
                'reason': 'I was present in the front row and actively participated in the 3NF vs BCNF discussion. Please correct my attendance.',
                'status': AttendanceCorrectionRequest.Status.PENDING,
            }
        )

        # 3. Case: Genuinely missing attendance entry for a published session
        # For Session 2 (Lab), Ananya has no record in DB
        Attendance.objects.filter(student=stu_ananya, session=sess_lab).delete()

        req_ananya, _ = AttendanceCorrectionRequest.objects.get_or_create(
            student=stu_ananya,
            session=sess_lab,
            defaults={
                'course': cs301,
                'teacher': prof_sunita,
                'original_status': None,
                'requested_status': Attendance.Status.PRESENT,
                'reason': 'Attended full database practical lab and submitted exercises to the TA. My entry was omitted in register.',
                'status': AttendanceCorrectionRequest.Status.PENDING,
            }
        )

        # 4. Case: Student with previous correction history (Priya Menon: 1 approved, 1 rejected, 1 pending)
        # 4a. Approved request from 4 days ago
        sess_priya_app, _ = ClassSession.objects.get_or_create(
            course=cs301,
            date=d_four_days,
            session_identifier='Session 1',
            defaults={'is_published': True}
        )
        att_priya_app, _ = Attendance.objects.get_or_create(
            student=stu_priya,
            session=sess_priya_app,
            defaults={
                'course': cs301,
                'date': d_four_days,
                'status': Attendance.Status.PRESENT,
                'marked_by': prof_sunita,
            }
        )
        att_priya_app.status = Attendance.Status.PRESENT
        att_priya_app.save()

        req_priya_app, _ = AttendanceCorrectionRequest.objects.get_or_create(
            student=stu_priya,
            session=sess_priya_app,
            defaults={
                'course': cs301,
                'teacher': prof_sunita,
                'original_status': Attendance.Status.ABSENT,
                'requested_status': Attendance.Status.PRESENT,
                'reason': 'Signed physical roll sheet, but marked absent on portal.',
                'status': AttendanceCorrectionRequest.Status.APPROVED,
                'reviewed_at': timezone.now() - timedelta(days=2),
                'access_method': 'session',
            }
        )
        AttendanceAuditLog.objects.get_or_create(
            correction_request=req_priya_app,
            defaults={
                'attendance': att_priya_app,
                'student': stu_priya,
                'session': sess_priya_app,
                'course': cs301,
                'previous_status': Attendance.Status.ABSENT,
                'new_status': Attendance.Status.PRESENT,
                'changed_by': prof_sunita,
                'decision_reason': 'Verified signature on attendance ledger.',
                'access_method': 'session',
            }
        )
        StudentNotification.objects.get_or_create(
            student=stu_priya,
            correction_request=req_priya_app,
            defaults={
                'message': f"Your attendance correction request for CS301 ({d_four_days}) was APPROVED. Status updated to Present.",
                'is_read': True,
            }
        )

        # 4b. Rejected request from 5 days ago
        sess_priya_rej, _ = ClassSession.objects.get_or_create(
            course=cs301,
            date=d_five_days,
            session_identifier='Session 1',
            defaults={'is_published': True}
        )
        att_priya_rej, _ = Attendance.objects.get_or_create(
            student=stu_priya,
            session=sess_priya_rej,
            defaults={
                'course': cs301,
                'date': d_five_days,
                'status': Attendance.Status.ABSENT,
                'marked_by': prof_sunita,
            }
        )
        req_priya_rej, _ = AttendanceCorrectionRequest.objects.get_or_create(
            student=stu_priya,
            session=sess_priya_rej,
            defaults={
                'course': cs301,
                'teacher': prof_sunita,
                'original_status': Attendance.Status.ABSENT,
                'requested_status': Attendance.Status.PRESENT,
                'reason': 'Arrived during second half of lecture.',
                'status': AttendanceCorrectionRequest.Status.REJECTED,
                'rejection_reason': 'Roll sheet does not show your signature and no in-class worksheet received.',
                'reviewed_at': timezone.now() - timedelta(days=3),
                'access_method': 'session',
            }
        )
        AttendanceAuditLog.objects.get_or_create(
            correction_request=req_priya_rej,
            defaults={
                'attendance': att_priya_rej,
                'student': stu_priya,
                'session': sess_priya_rej,
                'course': cs301,
                'previous_status': Attendance.Status.ABSENT,
                'new_status': Attendance.Status.ABSENT,
                'changed_by': prof_sunita,
                'decision_reason': 'Rejected: Roll sheet does not show your signature and no in-class worksheet received.',
                'access_method': 'session',
            }
        )
        StudentNotification.objects.get_or_create(
            student=stu_priya,
            correction_request=req_priya_rej,
            defaults={
                'message': f"Your attendance correction request for CS301 ({d_five_days}) was DECLINED. Feedback: Roll sheet does not show your signature and no in-class worksheet received.",
                'is_read': True,
            }
        )

        # 4c. Currently pending request for Priya (Requested Late)
        sess_priya_pend, _ = ClassSession.objects.get_or_create(
            course=cs204,
            date=d_recent,
            session_identifier='Session 1',
            defaults={'is_published': True}
        )
        Attendance.objects.get_or_create(
            student=stu_priya,
            session=sess_priya_pend,
            defaults={
                'course': cs204,
                'date': d_recent,
                'status': Attendance.Status.ABSENT,
                'marked_by': prof_sunita,
            }
        )
        req_priya_pend, _ = AttendanceCorrectionRequest.objects.get_or_create(
            student=stu_priya,
            session=sess_priya_pend,
            defaults={
                'course': cs204,
                'teacher': prof_sunita,
                'original_status': Attendance.Status.ABSENT,
                'requested_status': Attendance.Status.LATE,
                'reason': 'Local train delayed by 15 mins due to signal issue. Joined class with permission at 10:15 AM.',
                'status': AttendanceCorrectionRequest.Status.PENDING,
            }
        )

        # 5. Case: Request belonging to ANOTHER teacher (EMP2002 Anil Deshpande for CS110)
        sess_kabir, _ = ClassSession.objects.get_or_create(
            course=cs110,
            date=d_two_days,
            session_identifier='Session 1',
            defaults={'is_published': True}
        )
        Attendance.objects.get_or_create(
            student=stu_kabir,
            session=sess_kabir,
            defaults={
                'course': cs110,
                'date': d_two_days,
                'status': Attendance.Status.ABSENT,
                'marked_by': prof_anil,
            }
        )
        req_kabir, _ = AttendanceCorrectionRequest.objects.get_or_create(
            student=stu_kabir,
            session=sess_kabir,
            defaults={
                'course': cs110,
                'teacher': prof_anil,
                'original_status': Attendance.Status.ABSENT,
                'requested_status': Attendance.Status.PRESENT,
                'reason': 'Was present during Python functions demo. Instructor noted my code demo.',
                'status': AttendanceCorrectionRequest.Status.PENDING,
            }
        )

        # 6. Case: Student-cancelled request (Nisha Thomas)
        sess_nisha, _ = ClassSession.objects.get_or_create(
            course=cs301,
            date=d_two_days,
            session_identifier='Session 1',
            defaults={'is_published': True}
        )
        req_nisha, _ = AttendanceCorrectionRequest.objects.get_or_create(
            student=stu_nisha,
            session=sess_nisha,
            defaults={
                'course': cs301,
                'teacher': prof_sunita,
                'original_status': Attendance.Status.ABSENT,
                'requested_status': Attendance.Status.PRESENT,
                'reason': 'Submitted by mistake, I was attending another elective session.',
                'status': AttendanceCorrectionRequest.Status.CANCELLED,
            }
        )

        # 7. Create Grouped Email Batch with Active Magic Link (for EMP2001)
        raw_demo_token = "preview-token-sunita-kulkarni-2026"
        token_hash = hashlib.sha256(raw_demo_token.encode('utf-8')).hexdigest()
        batch_active, _ = AttendanceCorrectionBatch.objects.get_or_create(
            teacher=prof_sunita,
            status='sent',
            defaults={
                'token_hash': token_hash,
                'token_expires_at': timezone.now() + timedelta(hours=48),
                'email_sent_at': timezone.now() - timedelta(minutes=10),
            }
        )
        batch_active.token_hash = token_hash
        batch_active.token_expires_at = timezone.now() + timedelta(hours=48)
        batch_active.save()

        # Link Devansh, Ananya and Priya's pending requests to this batch
        for r in [req_devansh, req_ananya, req_priya_pend]:
            r.batch = batch_active
            r.save(update_fields=['batch'])

        # 8. Create Expired Link Batch (demonstrating graceful security page)
        raw_expired_token = "expired-token-sunita-2026"
        expired_hash = hashlib.sha256(raw_expired_token.encode('utf-8')).hexdigest()
        batch_expired, _ = AttendanceCorrectionBatch.objects.get_or_create(
            teacher=prof_sunita,
            status='failed',
            defaults={
                'token_hash': expired_hash,
                'token_expires_at': timezone.now() - timedelta(hours=3),
                'email_sent_at': timezone.now() - timedelta(hours=50),
            }
        )
        batch_expired.token_hash = expired_hash
        batch_expired.token_expires_at = timezone.now() - timedelta(hours=3)
        batch_expired.save()

        self.report(created, password, courses, days, admin, batch_active, raw_demo_token, batch_expired, raw_expired_token)

    @staticmethod
    def class_days(weeks):
        """Weekdays from `weeks` ago up to today."""
        today = timezone.localdate()
        span = [today - timedelta(days=offset) for offset in range(weeks * 7)]
        return sorted(day for day in span if day.weekday() < 5)

    def report(self, created, password, courses, days, admin, batch_active, active_token, batch_expired, expired_token):
        self.stdout.write(self.style.SUCCESS('\n========================================='))
        self.stdout.write(self.style.SUCCESS(' Cobra Coaching Demonstration Data Ready '))
        self.stdout.write(self.style.SUCCESS('=========================================\n'))
        self.stdout.write('  Courses: {}'.format(', '.join(c.code for c in courses)))
        self.stdout.write('  Students: {}'.format(User.objects.filter(role=User.Role.STUDENT).count()))
        self.stdout.write('  Sessions: {}'.format(ClassSession.objects.count()))
        self.stdout.write('  Attendance rows: {} across {} class days'.format(
            Attendance.objects.count(), len(days)))
        self.stdout.write('  Correction requests: {}'.format(AttendanceCorrectionRequest.objects.count()))

        self.stdout.write('\n--- DEMONSTRATION WORKFLOW LINKS & ACCOUNTS ---')
        self.stdout.write(f'1. Active Single-Batch Magic Link (Prof. Sunita Kulkarni - EMP2001):')
        self.stdout.write(f'   http://127.0.0.1:8000/attendance/review/?batch={batch_active.batch_id}&token={active_token}')
        self.stdout.write(f'2. Expired Magic Link Demonstration (Security Boundary Test):')
        self.stdout.write(f'   http://127.0.0.1:8000/attendance/review/?batch={batch_expired.batch_id}&token={expired_token}')
        self.stdout.write('3. Faculty Sign-In (Full Authenticated Review Inbox):')
        self.stdout.write('   Username: EMP2001 (Sunita Kulkarni) or EMP2002 (Anil Deshpande)')
        self.stdout.write('4. Student Sign-In (Correction Requesting & Status Ledger):')
        self.stdout.write('   Devansh Iyer: 23CS015 (Has pending Absent -> Present request)')
        self.stdout.write('   Ananya Rao:   23CS014 (Has pending Missing Entry request)')
        self.stdout.write('   Priya Menon:  23CS016 (Has complete history: 1 Approved, 1 Rejected, 1 Pending)')
        self.stdout.write('   Kabir Shah:   23CS017 (Request in CS110 for Prof. Anil Deshpande)')
        self.stdout.write('   Nisha Thomas: 23CS018 (Has cancelled request example)')

        if created:
            self.stdout.write(f'\nGenerated Password for newly created accounts: {password}')
        else:
            self.stdout.write('\nAll existing user accounts and passwords preserved.')
        self.stdout.write('Sign in as "admin" for Django administration at /admin/.\n')

