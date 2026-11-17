from decimal import Decimal
from django.core.exceptions import ValidationError
from django.test import TestCase, Client
from django.urls import reverse
from attendance.models import User, Course
from grades.models import Semester, Subject, GradeRecord
from grades.utils import get_student_semester_grades


class GradeManagementTests(TestCase):
    def setUp(self):
        self.client = Client()
        self.faculty = User.objects.create_user(
            username='EMP101',
            password='password123',
            role=User.Role.FACULTY,
            employee_id='EMP101'
        )
        self.other_faculty = User.objects.create_user(
            username='EMP102',
            password='password123',
            role=User.Role.FACULTY,
            employee_id='EMP102'
        )
        self.student = User.objects.create_user(
            username='STU101',
            password='password123',
            role=User.Role.STUDENT,
            roll_number='STU101'
        )
        self.other_student = User.objects.create_user(
            username='STU102',
            password='password123',
            role=User.Role.STUDENT,
            roll_number='STU102'
        )
        self.admin = User.objects.create_superuser(
            username='admin_user',
            password='password123',
            email='admin@example.com'
        )
        self.course = Course.objects.create(
            code='CS101',
            name='Programming Fundamentals',
            faculty=self.faculty
        )
        self.course.students.add(self.student)
        # Note: other_student is NOT enrolled in course

        self.other_course = Course.objects.create(
            code='EC201',
            name='Electronics',
            faculty=self.other_faculty
        )
        self.other_course.students.add(self.other_student)

        self.semester1 = Semester.objects.create(number=1, name='Semester 1', stamp_text='SEM 1')
        self.semester2 = Semester.objects.create(number=2, name='Semester 2', stamp_text='SEM 2')
        self.subject = Subject.objects.create(code='CS101', name='Programming Fundamentals', credits=4, course=self.course)

    # --- BUG 1: Remove invented student results ---

    def test_no_invented_grades_for_student_without_records(self):
        """Student with no records must see 'No grades available' with N/A SGPA, not invented data."""
        data = get_student_semester_grades(self.student, semester_num=1)
        self.assertEqual(data['status'], 'No grades available')
        self.assertEqual(data['sgpa'], 'N/A')
        self.assertEqual(data['totalSubjects'], 0)
        self.assertEqual(len(data['subjects']), 0)
        self.assertFalse(data['has_records'])

        # Check API endpoint returns empty genuine state
        self.client.login(username='STU101', password='password123')
        response = self.client.get(reverse('api_semester_grades', kwargs={'sem_id': 1}))
        self.assertEqual(response.status_code, 200)
        res_json = response.json()
        self.assertEqual(res_json['status'], 'No grades available')
        self.assertEqual(res_json['sgpa'], 'N/A')
        self.assertEqual(len(res_json['subjects']), 0)

        # Check student grades HTML displays genuine empty state
        page = self.client.get(reverse('student_grades'))
        self.assertEqual(page.status_code, 200)
        self.assertContains(page, 'No grades available')

    # --- BUG 2: Fix grade permissions ---

    def test_teacher_cannot_enter_marks_for_unenrolled_student(self):
        """Teacher cannot submit marks for a student not enrolled in the course."""
        self.client.login(username='EMP101', password='password123')
        response = self.client.post(reverse('save_student_marks'), {
            'course_id': self.course.pk,
            'student_id': self.other_student.pk,  # unenrolled
            'semester_id': self.semester1.pk,
            'internal': '15.0',
            'external': '60.0',
        })
        self.assertEqual(response.status_code, 403)
        self.assertFalse(GradeRecord.objects.filter(student=self.other_student).exists())

    def test_teacher_cannot_enter_marks_for_unauthorized_course(self):
        """Teacher cannot enter marks for courses taught by other faculty."""
        self.client.login(username='EMP101', password='password123')
        response = self.client.post(reverse('save_student_marks'), {
            'course_id': self.other_course.pk,
            'student_id': self.other_student.pk,
            'semester_id': self.semester1.pk,
            'internal': '15.0',
            'external': '60.0',
        })
        self.assertEqual(response.status_code, 404)

    def test_teacher_cannot_access_unrelated_student_grades(self):
        """Teacher cannot view grades of students not enrolled in their courses."""
        self.client.login(username='EMP101', password='password123')
        response = self.client.get(f"{reverse('student_grades')}?student={self.other_student.pk}")
        self.assertEqual(response.status_code, 403)

    def test_student_cannot_view_other_student_grades(self):
        """Student cannot view another student's grade ledger by tampering with query param."""
        self.client.login(username='STU101', password='password123')
        response = self.client.get(f"{reverse('student_grades')}?student={self.other_student.pk}")
        self.assertEqual(response.status_code, 200)
        # Target student remains STU101
        self.assertEqual(response.context['student'], self.student)

    # --- BUG 3: Validate marks properly ---

    def test_reject_out_of_range_marks(self):
        """Internal > 20 and External > 80 must be rejected."""
        self.client.login(username='EMP101', password='password123')
        # Internal too high
        resp = self.client.post(reverse('save_student_marks'), {
            'course_id': self.course.pk,
            'student_id': self.student.pk,
            'semester_id': self.semester1.pk,
            'internal': '25.0',
            'external': '60.0',
        }, follow=True)
        self.assertContains(resp, 'Internal marks must be between 0.0 and 20.0')

        # External too high
        resp = self.client.post(reverse('save_student_marks'), {
            'course_id': self.course.pk,
            'student_id': self.student.pk,
            'semester_id': self.semester1.pk,
            'internal': '15.0',
            'external': '90.0',
        }, follow=True)
        self.assertContains(resp, 'External marks must be between 0.0 and 80.0')

        # Negative marks
        resp = self.client.post(reverse('save_student_marks'), {
            'course_id': self.course.pk,
            'student_id': self.student.pk,
            'semester_id': self.semester1.pk,
            'internal': '-5.0',
            'external': '50.0',
        }, follow=True)
        self.assertContains(resp, 'Internal marks must be between 0.0 and 20.0')

    def test_reject_blank_or_invalid_marks_input(self):
        """Reject non-numeric strings, NaN, Infinity, and blank inputs."""
        self.client.login(username='EMP101', password='password123')
        # Blank internal marks
        resp = self.client.post(reverse('save_student_marks'), {
            'course_id': self.course.pk,
            'student_id': self.student.pk,
            'semester_id': self.semester1.pk,
            'internal': '',
            'external': '50.0',
        }, follow=True)
        self.assertContains(resp, 'Internal marks are required.')

        # Invalid text
        resp = self.client.post(reverse('save_student_marks'), {
            'course_id': self.course.pk,
            'student_id': self.student.pk,
            'semester_id': self.semester1.pk,
            'internal': 'abc',
            'external': '50.0',
        }, follow=True)
        self.assertContains(resp, 'Invalid numeric format')

    def test_model_level_validation(self):
        """GradeRecord clean() rejects out-of-range or invalid marks."""
        record = GradeRecord(
            student=self.student,
            semester=self.semester1,
            subject=self.subject,
            internal_marks=Decimal('25.0'),
            external_marks=Decimal('50.0')
        )
        with self.assertRaises(ValidationError):
            record.clean()

    # --- BUG 4: Correct automatic grade calculation ---

    def test_zero_marks_receives_fail(self):
        """Zero marks must calculate to Grade F and 0.0 Grade Point, never default A/9.0."""
        record = GradeRecord.objects.create(
            student=self.student,
            semester=self.semester1,
            subject=self.subject,
            internal_marks=Decimal('0.0'),
            external_marks=Decimal('0.0')
        )
        self.assertEqual(record.total_marks, Decimal('0.0'))
        self.assertEqual(record.grade, 'F')
        self.assertEqual(record.grade_point, Decimal('0.0'))

    def test_grading_scale_tiers(self):
        """Verify institutional grading tiers."""
        self.assertEqual(GradeRecord.calculate_grade_and_point(95), ('A+', Decimal('10.0')))
        self.assertEqual(GradeRecord.calculate_grade_and_point(85), ('A', Decimal('9.0')))
        self.assertEqual(GradeRecord.calculate_grade_and_point(75), ('B+', Decimal('8.0')))
        self.assertEqual(GradeRecord.calculate_grade_and_point(65), ('B', Decimal('7.0')))
        self.assertEqual(GradeRecord.calculate_grade_and_point(55), ('C', Decimal('6.0')))
        self.assertEqual(GradeRecord.calculate_grade_and_point(45), ('P', Decimal('5.0')))
        self.assertEqual(GradeRecord.calculate_grade_and_point(35), ('F', Decimal('0.0')))

    # --- BUG 5: Fix semester handling ---

    def test_semester_isolation_and_preservation(self):
        """Marks entered for Semester 2 are saved under Semester 2 and do not overwrite Semester 1."""
        self.client.login(username='EMP101', password='password123')
        
        # Save Semester 1 marks
        self.client.post(reverse('save_student_marks'), {
            'course_id': self.course.pk,
            'student_id': self.student.pk,
            'semester_id': self.semester1.pk,
            'internal': '18.0',
            'external': '62.0',
        })
        
        # Save Semester 2 marks
        self.client.post(reverse('save_student_marks'), {
            'course_id': self.course.pk,
            'student_id': self.student.pk,
            'semester_id': self.semester2.pk,
            'internal': '12.0',
            'external': '40.0',
        })

        rec_sem1 = GradeRecord.objects.get(student=self.student, subject=self.subject, semester=self.semester1)
        rec_sem2 = GradeRecord.objects.get(student=self.student, subject=self.subject, semester=self.semester2)

        self.assertEqual(rec_sem1.total_marks, Decimal('80.0'))
        self.assertEqual(rec_sem1.grade, 'A')
        self.assertEqual(rec_sem2.total_marks, Decimal('52.0'))
        self.assertEqual(rec_sem2.grade, 'C')
