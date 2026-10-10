import csv
import io
from datetime import timedelta

from django.test import TestCase
from django.urls import reverse
from django.utils import timezone

from . import stats
from .models import Attendance, Course, User

PASSWORD = 'RegisterBook#2026'


class AuthTests(TestCase):
    """Stage 3: login, registration and the role gates."""

    @classmethod
    def setUpTestData(cls):
        cls.student = User.objects.create_user(
            username='23CS045', password=PASSWORD,
            role=User.Role.STUDENT, roll_number='23CS045',
        )
        cls.faculty = User.objects.create_user(
            username='EMP1023', password=PASSWORD,
            role=User.Role.FACULTY, employee_id='EMP1023',
        )

    # --- login -------------------------------------------------------------

    def test_valid_student_login_redirects_to_portal(self):
        response = self.client.post(
            reverse('login'), {'username': '23CS045', 'password': PASSWORD}
        )
        self.assertRedirects(response, reverse('student_home'))

    def test_valid_faculty_login_redirects_to_dashboard(self):
        response = self.client.post(
            reverse('login'), {'username': 'EMP1023', 'password': PASSWORD}
        )
        self.assertRedirects(response, reverse('faculty_dashboard'))

    def test_invalid_login_shows_error_and_stays_anonymous(self):
        response = self.client.post(
            reverse('login'), {'username': '23CS045', 'password': 'wrong-password'}
        )
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'Please enter a correct')
        self.assertFalse(response.wsgi_request.user.is_authenticated)

    def test_login_honours_next_parameter(self):
        response = self.client.post(
            reverse('login'),
            {'username': '23CS045', 'password': PASSWORD, 'next': reverse('student_home')},
        )
        self.assertRedirects(response, reverse('student_home'))

    # --- registration ------------------------------------------------------

    def _register(self, **overrides):
        data = {
            'roll_number': '24CS001',
            'email': 'new.student@college.edu',
            'password1': PASSWORD,
            'password2': PASSWORD,
        }
        data.update(overrides)
        return self.client.post(reverse('register'), data)

    def test_registration_creates_student_who_can_log_in(self):
        response = self._register()
        self.assertRedirects(response, reverse('login'))

        user = User.objects.get(roll_number='24CS001')
        self.assertEqual(user.username, '24CS001')  # roll number doubles as College ID
        self.assertEqual(user.role, User.Role.STUDENT)
        self.assertFalse(user.is_staff)
        self.assertFalse(user.is_superuser)
        self.assertNotEqual(user.password, PASSWORD)  # hashed, not stored raw
        self.assertTrue(self.client.login(username='24CS001', password=PASSWORD))

    def test_registration_rejects_duplicate_username(self):
        # An account already holds this College ID, with no roll number of its own.
        User.objects.create_user(username='24CS002', password=PASSWORD, role=User.Role.FACULTY)
        response = self._register(roll_number='24CS002')
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'College ID already exists')
        self.assertFalse(User.objects.filter(roll_number='24CS002').exists())

    def test_registration_rejects_duplicate_roll_number(self):
        response = self._register(roll_number='23CS045')  # taken by self.student
        self.assertEqual(response.status_code, 200)
        self.assertIn('roll_number', response.context['form'].errors)
        self.assertEqual(User.objects.filter(roll_number='23CS045').count(), 1)

    def test_registration_rejects_password_mismatch(self):
        response = self._register(password2=PASSWORD + 'x')
        self.assertEqual(response.status_code, 200)
        self.assertIn('password2', response.context['form'].errors)
        self.assertFalse(User.objects.filter(roll_number='24CS001').exists())

    def test_registration_requires_roll_number_and_email(self):
        response = self._register(roll_number='', email='')
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.context['form'].errors.keys(), {'roll_number', 'email'})
        self.assertEqual(User.objects.count(), 2)

    def test_registration_cannot_create_faculty_or_admin(self):
        """Posting a role is ignored: the server always creates a student."""
        self._register(role='faculty', is_staff='on', is_superuser='on', employee_id='EMP9')
        user = User.objects.get(roll_number='24CS001')
        self.assertEqual(user.role, User.Role.STUDENT)
        self.assertFalse(user.is_staff)
        self.assertFalse(user.is_superuser)
        self.assertIsNone(user.employee_id)

    # --- logout ------------------------------------------------------------

    def test_logout_ends_the_session(self):
        self.client.force_login(self.student)
        response = self.client.post(reverse('logout'))
        self.assertRedirects(response, reverse('login'))
        self.assertRedirects(
            self.client.get(reverse('student_home')),
            '{}?next={}'.format(reverse('login'), reverse('student_home')),
        )

    # --- access control ----------------------------------------------------

    def test_protected_routes_redirect_anonymous_users_to_login(self):
        for name in ('student_home', 'faculty_dashboard'):
            with self.subTest(route=name):
                url = reverse(name)
                self.assertRedirects(
                    self.client.get(url), '{}?next={}'.format(reverse('login'), url)
                )

    def test_student_cannot_reach_faculty_dashboard(self):
        self.client.force_login(self.student)
        self.assertEqual(self.client.get(reverse('faculty_dashboard')).status_code, 403)

    def test_faculty_cannot_reach_student_portal(self):
        self.client.force_login(self.faculty)
        self.assertEqual(self.client.get(reverse('student_home')).status_code, 403)

    def test_each_role_reaches_its_own_page(self):
        self.client.force_login(self.student)
        self.assertEqual(self.client.get(reverse('student_home')).status_code, 200)
        self.client.force_login(self.faculty)
        self.assertEqual(self.client.get(reverse('faculty_dashboard')).status_code, 200)

    def test_admin_login_goes_to_django_admin(self):
        admin = User.objects.create_superuser(
            username='dean', password=PASSWORD, role=User.Role.ADMIN
        )
        response = self.client.post(
            reverse('login'), {'username': admin.username, 'password': PASSWORD}
        )
        self.assertRedirects(response, reverse('admin:index'))


class CollegeData(TestCase):
    """Two faculty, three students and two courses, shared by the Stage 4 tests."""

    @classmethod
    def setUpTestData(cls):
        cls.today = timezone.localdate()
        cls.faculty = User.objects.create_user(
            username='EMP1', password=PASSWORD, first_name='Sunita', last_name='Kulkarni',
            role=User.Role.FACULTY, employee_id='EMP1',
        )
        cls.other_faculty = User.objects.create_user(
            username='EMP2', password=PASSWORD, role=User.Role.FACULTY, employee_id='EMP2',
        )
        cls.alice, cls.bob, cls.cara = (
            User.objects.create_user(
                username=roll, password=PASSWORD, first_name=name,
                role=User.Role.STUDENT, roll_number=roll,
            )
            for roll, name in (('23CS001', 'Alice'), ('23CS002', 'Bob'), ('23CS003', 'Cara'))
        )
        cls.course = Course.objects.create(code='CS301', name='Database Systems',
                                           faculty=cls.faculty)
        cls.course.students.add(cls.alice, cls.bob)
        cls.other_course = Course.objects.create(code='CS110', name='Intro to Programming',
                                                 faculty=cls.other_faculty)
        cls.other_course.students.add(cls.cara)

    def mark(self, student, status, day_offset=0, course=None, by=None):
        return Attendance.objects.create(
            student=student, course=course or self.course, date=self.today - timedelta(days=day_offset),
            status=status, marked_by=by or self.faculty,
        )

    def register_url(self, course=None, day=None):
        url = reverse('attendance_register')
        if course is None and day is None:
            return url
        return '{}?course={}&date={}'.format(url, (course or self.course).pk,
                                             (day or self.today).isoformat())


class StatsTests(CollegeData):
    """The shared arithmetic every page depends on."""

    def test_percentage_counts_late_as_attended(self):
        self.mark(self.alice, Attendance.Status.PRESENT, 2)
        self.mark(self.alice, Attendance.Status.LATE, 1)
        self.mark(self.alice, Attendance.Status.ABSENT, 0)
        row = stats.totals(self.alice.attendance_records)
        self.assertEqual((row['attended'], row['held']), (2, 3))
        self.assertEqual(row['percent'], 66.7)

    def test_no_records_gives_no_percentage_rather_than_zero(self):
        row = stats.totals(self.alice.attendance_records)
        self.assertIsNone(row['percent'])
        self.assertEqual(row['held'], 0)
        self.assertFalse(row['low'])

    def test_stamp_follows_the_percentage(self):
        self.assertEqual(stats.stamp(90), 'stamp-present')
        self.assertEqual(stats.stamp(80), 'stamp-late')
        self.assertEqual(stats.stamp(74.9), 'stamp-absent')

    def test_by_course_lists_every_enrolment_even_without_records(self):
        self.mark(self.alice, Attendance.Status.PRESENT)
        rows = stats.by_course(self.alice)
        self.assertEqual([r['course'].code for r in rows], ['CS301'])
        self.assertEqual(rows[0]['percent'], 100.0)

        self.course.students.add(self.cara)
        cara = stats.by_course(self.cara)  # two enrolments, no records in either
        self.assertEqual([r['course'].code for r in cara], ['CS110', 'CS301'])
        self.assertEqual([r['held'] for r in cara], [0, 0])
        self.assertEqual([r['percent'] for r in cara], [None, None])

    def test_by_student_lists_the_whole_roster(self):
        self.mark(self.alice, Attendance.Status.ABSENT)
        rows = stats.by_student(self.course)
        self.assertEqual([r['student'].roll_number for r in rows], ['23CS001', '23CS002'])
        self.assertEqual(rows[0]['percent'], 0.0)
        self.assertIsNone(rows[1]['percent'])

    def test_shortfalls_are_ordered_worst_first(self):
        for offset in range(4):
            self.mark(self.alice, Attendance.Status.ABSENT, offset)  # 0%
            self.mark(self.bob, Attendance.Status.ABSENT if offset < 2
                      else Attendance.Status.PRESENT, offset)        # 50%
        short = stats.shortfalls(stats.by_student(self.course))
        self.assertEqual([r['student'].roll_number for r in short], ['23CS001', '23CS002'])
        self.assertEqual([r['percent'] for r in short], [0.0, 50.0])

    def test_exactly_at_the_threshold_is_not_a_shortfall(self):
        for offset in range(4):  # three present, one absent = exactly 75%
            self.mark(self.alice, Attendance.Status.ABSENT if offset == 3
                      else Attendance.Status.PRESENT, offset)
        rows = [r for r in stats.by_student(self.course) if r['student'] == self.alice]
        self.assertEqual(rows[0]['percent'], 75.0)
        self.assertFalse(rows[0]['low'])
        self.assertEqual(stats.shortfalls(rows), [])


class RegisterTests(CollegeData):
    """Marking the roll call: the register page and what it writes to the database."""

    def setUp(self):
        self.client.force_login(self.faculty)

    def marks(self, alice='P', bob='P', day=None, course=None):
        data = {'course': (course or self.course).pk,
                'date': (day or self.today).isoformat()}
        if alice:
            data['s{}'.format(self.alice.pk)] = alice
        if bob:
            data['s{}'.format(self.bob.pk)] = bob
        return data

    def test_page_shows_only_the_roster_of_a_course_this_faculty_teaches(self):
        response = self.client.get(reverse('attendance_register'))
        self.assertEqual(response.status_code, 200)
        self.assertEqual([c.code for c in response.context['courses']], ['CS301'])
        self.assertEqual([r['student'] for r in response.context['rows']],
                         [self.alice, self.bob])
        self.assertContains(response, 'name="s{}"'.format(self.alice.pk))
        self.assertNotContains(response, 'name="s{}"'.format(self.cara.pk))

    def test_saving_writes_one_row_per_student_credited_to_the_signed_in_faculty(self):
        response = self.client.post(reverse('attendance_register'),
                                    self.marks(alice='P', bob='A'))
        self.assertRedirects(response, self.register_url(self.course, self.today))
        rows = Attendance.objects.filter(course=self.course, date=self.today)
        self.assertEqual(rows.count(), 2)
        self.assertEqual(rows.get(student=self.alice).status, Attendance.Status.PRESENT)
        self.assertEqual(rows.get(student=self.bob).status, Attendance.Status.ABSENT)
        self.assertEqual({r.marked_by for r in rows}, {self.faculty})

    def test_saving_twice_updates_the_same_rows_instead_of_duplicating(self):
        self.client.post(reverse('attendance_register'), self.marks(alice='P', bob='P'))
        self.client.post(reverse('attendance_register'), self.marks(alice='A', bob='L'))
        rows = Attendance.objects.filter(course=self.course, date=self.today)
        self.assertEqual(rows.count(), 2)  # the unique constraint holds
        self.assertEqual(rows.get(student=self.alice).status, Attendance.Status.ABSENT)
        self.assertEqual(rows.get(student=self.bob).status, Attendance.Status.LATE)

    def test_previous_marks_come_back_selected(self):
        self.client.post(reverse('attendance_register'), self.marks(alice='L', bob='A'))
        response = self.client.get(self.register_url())
        self.assertContains(response, 'id="s{}l" value="L" checked'.format(self.alice.pk))
        self.assertContains(response, 'id="s{}a" value="A" checked'.format(self.bob.pk))
        self.assertContains(response, 'saving again updates it')

    def test_students_left_blank_are_reported_and_left_alone(self):
        response = self.client.post(reverse('attendance_register'),
                                    self.marks(alice='P', bob=None), follow=True)
        self.assertEqual(Attendance.objects.filter(date=self.today).count(), 1)
        self.assertContains(response, 'Left unmarked: 23CS002')

    def test_an_invalid_status_is_ignored_rather_than_stored(self):
        data = self.marks(alice='P', bob=None)
        data['s{}'.format(self.bob.pk)] = 'X'  # not one of P / L / A
        self.client.post(reverse('attendance_register'), data)
        self.assertFalse(Attendance.objects.filter(student=self.bob).exists())

    def test_a_future_date_is_refused_and_nothing_is_written(self):
        future = self.today + timedelta(days=1)
        response = self.client.post(reverse('attendance_register'),
                                    self.marks(day=future), follow=True)
        self.assertContains(response, 'cannot be saved for a future date')
        self.assertFalse(Attendance.objects.exists())

    def test_an_unreadable_date_falls_back_to_today_with_a_message(self):
        response = self.client.get('{}?date=13/13/2026'.format(reverse('attendance_register')))
        self.assertEqual(response.context['day'], self.today)
        self.assertContains(response, 'could not be read')

    def test_another_faculty_course_is_not_reachable(self):
        self.assertEqual(self.client.get(self.register_url(self.other_course)).status_code, 404)
        response = self.client.post(reverse('attendance_register'),
                                    {'course': self.other_course.pk,
                                     'date': self.today.isoformat(),
                                     's{}'.format(self.cara.pk): 'A'})
        self.assertEqual(response.status_code, 404)
        self.assertFalse(Attendance.objects.exists())

    def test_a_course_with_nobody_enrolled_says_so(self):
        self.course.students.clear()
        response = self.client.get(reverse('attendance_register'))
        self.assertContains(response, 'No students are enrolled in CS301 yet')
        self.assertNotContains(response, 'Save register')  # nothing to save

    def test_the_toolbar_summary_counts_the_saved_marks(self):
        self.client.post(reverse('attendance_register'), self.marks(alice='P', bob='L'))
        response = self.client.get(self.register_url())
        self.assertContains(response, '1 Present · 1 Late · 0 Absent — of 2')

    def test_students_cannot_open_or_post_to_the_register(self):
        self.client.force_login(self.alice)
        self.assertEqual(self.client.get(reverse('attendance_register')).status_code, 403)
        self.assertEqual(self.client.post(reverse('attendance_register'),
                                          self.marks()).status_code, 403)
        self.assertFalse(Attendance.objects.exists())


class StudentPortalTests(CollegeData):
    """What a student sees at /me/, and that it is only ever their own data."""

    def test_percentage_and_counts_come_from_the_records(self):
        self.mark(self.alice, Attendance.Status.PRESENT, 2)
        self.mark(self.alice, Attendance.Status.LATE, 1)
        self.mark(self.alice, Attendance.Status.ABSENT, 0)
        self.client.force_login(self.alice)
        response = self.client.get(reverse('student_home'))

        overall = response.context['overall']
        self.assertEqual((overall['present'], overall['late'], overall['absent']), (1, 1, 1))
        self.assertEqual(overall['percent'], 66.7)
        self.assertContains(response, '66.7%')
        self.assertContains(response, 'below the 75% requirement')

    def test_enrolled_course_with_no_records_is_listed_as_such(self):
        self.client.force_login(self.bob)
        response = self.client.get(reverse('student_home'))
        self.assertEqual([r['course'].code for r in response.context['courses']], ['CS301'])
        self.assertContains(response, 'No classes recorded')
        self.assertContains(response, 'No register has been')

    def test_a_student_with_no_enrolment_gets_a_plain_explanation(self):
        loner = User.objects.create_user(username='23CS009', password=PASSWORD,
                                         role=User.Role.STUDENT, roll_number='23CS009')
        self.client.force_login(loner)
        response = self.client.get(reverse('student_home'))
        self.assertEqual(response.context['courses'], [])
        self.assertContains(response, 'not enrolled in any course yet')
        self.assertNotContains(response, '%</span>')

    def test_the_portal_never_shows_another_students_records(self):
        self.mark(self.alice, Attendance.Status.PRESENT)
        self.mark(self.cara, Attendance.Status.ABSENT, course=self.other_course,
                  by=self.other_faculty)
        self.client.force_login(self.alice)
        response = self.client.get(reverse('student_home'))
        self.assertEqual([r.student for r in response.context['history']], [self.alice])
        self.assertNotContains(response, 'CS110')

    def test_marking_changes_the_students_percentage(self):
        self.client.force_login(self.faculty)
        post = {'course': self.course.pk, 'date': self.today.isoformat(),
                's{}'.format(self.alice.pk): 'P', 's{}'.format(self.bob.pk): 'P'}
        self.client.post(reverse('attendance_register'), post)

        self.client.force_login(self.alice)
        self.assertEqual(self.client.get(reverse('student_home')).context['overall']['percent'],
                         100.0)

        self.client.force_login(self.faculty)
        post['date'] = (self.today - timedelta(days=1)).isoformat()
        post['s{}'.format(self.alice.pk)] = 'A'
        self.client.post(reverse('attendance_register'), post)

        self.client.force_login(self.alice)
        self.assertEqual(self.client.get(reverse('student_home')).context['overall']['percent'],
                         50.0)


class ReportTests(CollegeData):
    """The reports page and its CSV export."""

    def setUp(self):
        self.client.force_login(self.faculty)
        # Four class days: Alice 1/4, Bob 4/4.
        for offset in range(4):
            self.mark(self.alice, Attendance.Status.PRESENT if offset == 0
                      else Attendance.Status.ABSENT, offset)
            self.mark(self.bob, Attendance.Status.PRESENT, offset)

    def test_summary_figures_are_calculated_from_the_records(self):
        response = self.client.get(reverse('reports'))
        self.assertEqual(response.context['classes_held'], 4)
        self.assertEqual(response.context['overall']['percent'], 62.5)
        self.assertEqual([r['student'] for r in response.context['perfect']], [self.bob])
        self.assertEqual([r['student'] for r in response.context['shortfalls']], [self.alice])
        self.assertContains(response, '62.5%')
        self.assertContains(response, 'Roll 23CS001')

    def test_the_heatmap_covers_28_days_and_marks_the_days_with_a_class(self):
        response = self.client.get(reverse('reports'))
        cells = response.context['heatmap']
        self.assertEqual(len(cells), 28)
        self.assertEqual(cells[-1]['date'], self.today)
        # Today both attended (100%); the three days before, only Bob did (50%).
        self.assertEqual([c['level'] for c in cells[-4:]], [1, 1, 1, 4])
        self.assertEqual(cells[0]['level'], 0)  # no class that day
        self.assertContains(response, 'class="cell" data-lvl="4"')

    def test_a_course_without_records_reports_nothing_rather_than_zero(self):
        Attendance.objects.all().delete()
        response = self.client.get(reverse('reports'))
        self.assertIsNone(response.context['overall']['percent'])
        self.assertEqual(response.context['classes_held'], 0)
        self.assertContains(response, 'No Data')
        self.assertContains(response, 'No registers have been saved for this course yet')

    def test_export_downloads_a_csv_of_the_real_figures(self):
        response = self.client.get('{}?course={}'.format(reverse('reports_export'),
                                                         self.course.pk))
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response['Content-Type'], 'text/csv')
        self.assertIn('attachment; filename="CS301-attendance-', response['Content-Disposition'])

        rows = list(csv.reader(io.StringIO(response.content.decode())))
        self.assertEqual(rows[0], ['CS301', 'Database Systems', 'Classes held', '4'])
        self.assertEqual(rows[2], ['Roll number', 'Student', 'Present', 'Late', 'Absent',
                                   'Classes recorded', 'Attendance %'])
        self.assertEqual(rows[3], ['23CS001', 'Alice', '1', '0', '3', '4', '25.0'])
        self.assertEqual(rows[4], ['23CS002', 'Bob', '4', '0', '0', '4', '100.0'])
        self.assertEqual(rows[-2:], [['Class average', '62.5'], ['Below 75%', '1']])

    def test_export_refuses_another_faculty_course(self):
        response = self.client.get('{}?course={}'.format(reverse('reports_export'),
                                                         self.other_course.pk))
        self.assertEqual(response.status_code, 404)

    def test_students_cannot_read_reports_or_the_export(self):
        self.client.force_login(self.alice)
        self.assertEqual(self.client.get(reverse('reports')).status_code, 403)
        self.assertEqual(self.client.get(reverse('reports_export')).status_code, 403)


class DashboardTests(CollegeData):
    """The faculty dashboard, and that its navigation actually goes somewhere."""

    def setUp(self):
        self.client.force_login(self.faculty)

    def test_it_reports_only_this_facultys_courses_and_figures(self):
        self.mark(self.alice, Attendance.Status.PRESENT)
        self.mark(self.bob, Attendance.Status.ABSENT)
        self.mark(self.cara, Attendance.Status.PRESENT, course=self.other_course,
                  by=self.other_faculty)
        response = self.client.get(reverse('faculty_dashboard'))

        self.assertEqual([c.code for c in response.context['courses']], ['CS301'])
        self.assertEqual(response.context['overall']['percent'], 50.0)  # CS110 excluded
        self.assertEqual(response.context['today_totals']['held'], 2)
        self.assertEqual(response.context['at_risk_count'], 1)  # Bob at 0%
        self.assertContains(response, 'Sunita Kulkarni')

    def test_recent_entries_list_saved_registers_newest_first(self):
        for offset in (0, 3):
            self.mark(self.alice, Attendance.Status.PRESENT, offset)
            self.mark(self.bob, Attendance.Status.PRESENT, offset)
        response = self.client.get(reverse('faculty_dashboard'))
        recent = response.context['recent']
        self.assertEqual([r['date'] for r in recent],
                         [self.today, self.today - timedelta(days=3)])
        self.assertEqual(recent[0]['attended'], 2)
        self.assertContains(response, 'Marked by you')
        self.assertContains(response, '2/2')

    def test_an_empty_database_reads_as_empty_rather_than_wrong(self):
        response = self.client.get(reverse('faculty_dashboard'))
        self.assertIsNone(response.context['overall']['percent'])
        self.assertContains(response, 'No registers saved yet')
        self.assertContains(response, 'Still to mark today')
        self.assertContains(response, '1 register still open')

    def test_the_week_chart_has_one_column_per_weekday(self):
        response = self.client.get(reverse('faculty_dashboard'))
        self.assertEqual(len(response.context['week_days']), 7)
        self.assertEqual(response.context['week_days'][0][0],
                         stats.week_start(self.today))
        self.assertContains(response, 'class="bar-label">MON')

    def test_the_navigation_points_at_real_routes(self):
        for page in ('faculty_dashboard', 'attendance_register', 'reports'):
            with self.subTest(page=page):
                response = self.client.get(reverse(page))
                for target in ('faculty_dashboard', 'attendance_register', 'reports'):
                    self.assertContains(response, 'href="{}"'.format(reverse(target)))
                self.assertNotContains(response, 'href="#"')

    def test_a_faculty_with_no_courses_is_told_so(self):
        self.client.force_login(self.other_faculty)
        self.other_course.delete()
        response = self.client.get(reverse('faculty_dashboard'))
        self.assertEqual(response.context['courses'], [])
        self.assertContains(response, 'No courses are assigned to your account yet')

    def test_an_admin_sees_every_course(self):
        admin = User.objects.create_superuser(username='dean', password=PASSWORD,
                                              role=User.Role.ADMIN)
        self.client.force_login(admin)
        response = self.client.get(reverse('attendance_register'))
        self.assertEqual([c.code for c in response.context['courses']], ['CS110', 'CS301'])
