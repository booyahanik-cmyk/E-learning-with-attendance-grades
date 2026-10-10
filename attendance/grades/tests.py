from decimal import Decimal
from django.test import TestCase, Client
from django.urls import reverse
from attendance.models import User, Course
from grades.models import Semester, Subject, GradeRecord
from grades.utils import get_student_semester_grades, DEFAULT_SEMESTER_DATA


class GradeManagementTests(TestCase):
    def setUp(self):
        self.client = Client()
        self.faculty = User.objects.create_user(
            username='EMP101',
            password='password123',
            role=User.Role.FACULTY,
            employee_id='EMP101'
        )
        self.student = User.objects.create_user(
            username='STU101',
            password='password123',
            role=User.Role.STUDENT,
            roll_number='STU101'
        )
        self.course = Course.objects.create(
            code='CS101',
            name='Programming Fundamentals',
            faculty=self.faculty
        )
        self.course.students.add(self.student)
        self.semester = Semester.objects.create(number=1, name='Semester 1', stamp_text='SEM 1')
        self.subject = Subject.objects.create(code='CS101', name='Programming Fundamentals', credits=4, course=self.course)

    def test_grade_record_calculation(self):
        """Ensure total marks and grades compute properly."""
        record = GradeRecord.objects.create(
            student=self.student,
            semester=self.semester,
            subject=self.subject,
            internal_marks=Decimal('18.0'),
            external_marks=Decimal('62.0'),
        )
        self.assertEqual(record.total_marks, Decimal('80.0'))
        self.assertEqual(record.grade, 'A')
        self.assertEqual(record.grade_point, Decimal('9.0'))

    def test_student_grades_view_redirects_unauthenticated(self):
        """Unauthenticated user redirected to login."""
        response = self.client.get(reverse('student_grades'))
        self.assertEqual(response.status_code, 302)

    def test_student_grades_view_authenticated(self):
        """Authenticated student gets their grade ledger."""
        self.client.login(username='STU101', password='password123')
        response = self.client.get(reverse('student_grades'))
        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, 'grades/grades.html')
        self.assertContains(response, 'Your grades')

    def test_faculty_grades_view(self):
        """Faculty can open assessment registry for their course."""
        self.client.login(username='EMP101', password='password123')
        response = self.client.get(reverse('faculty_grades'))
        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, 'grades/faculty_grades.html')
        self.assertContains(response, 'Grade Registry &amp; Assessment')

    def test_save_student_marks(self):
        """Faculty can submit student assessment marks."""
        self.client.login(username='EMP101', password='password123')
        response = self.client.post(reverse('save_student_marks'), {
            'course_id': self.course.pk,
            'student_id': self.student.pk,
            'internal': '19',
            'external': '71',
        }, follow=True)
        self.assertEqual(response.status_code, 200)
        record = GradeRecord.objects.get(student=self.student, subject=self.subject, semester=self.semester)
        self.assertEqual(record.total_marks, Decimal('90.0'))
        self.assertEqual(record.grade, 'A+')
        self.assertEqual(record.grade_point, Decimal('10.0'))

    def test_api_semester_grades(self):
        """API endpoint returns JSON with semester grade information."""
        self.client.login(username='STU101', password='password123')
        response = self.client.get(reverse('api_semester_grades', kwargs={'sem_id': 1}))
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertEqual(data['semester'], 1)
        self.assertIn('sgpa', data)
        self.assertIn('subjects', data)
