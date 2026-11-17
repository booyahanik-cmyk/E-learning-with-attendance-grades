from django.test import TestCase, Client
from django.urls import reverse
from attendance.models import User
from learnsphere.models import LSCourse, LSLesson, LSEnrollment, LSProgress, LSVoucher


class LearnSphereTests(TestCase):
    def setUp(self):
        self.client = Client()
        self.instructor = User.objects.create_user(
            username='INST001',
            password='password123',
            role=User.Role.FACULTY,
            employee_id='INST001'
        )
        self.student = User.objects.create_user(
            username='STU201',
            password='password123',
            role=User.Role.STUDENT,
            roll_number='STU201'
        )
        self.student2 = User.objects.create_user(
            username='STU202',
            password='password123',
            role=User.Role.STUDENT,
            roll_number='STU202'
        )
        self.student3 = User.objects.create_user(
            username='STU203',
            password='password123',
            role=User.Role.STUDENT,
            roll_number='STU203'
        )

        # Published course with multiple lessons
        self.pub_course = LSCourse.objects.create(
            title='Web Development Mastery',
            description='Learn full-stack web engineering',
            category='Engineering',
            instructor=self.instructor,
            is_published=True
        )
        self.l1 = LSLesson.objects.create(course=self.pub_course, title='HTML & CSS', content='Intro to markup', position=1)
        self.l2 = LSLesson.objects.create(course=self.pub_course, title='JavaScript ES6', content='Modern JS syntax', position=2)
        self.l3 = LSLesson.objects.create(course=self.pub_course, title='Django Framework', content='Backend MTV patterns', position=3)
        self.l4 = LSLesson.objects.create(course=self.pub_course, title='Database Design', content='Relational normalization', position=4)

        # Multiple enrollments
        LSEnrollment.objects.create(user=self.student, course=self.pub_course)
        LSEnrollment.objects.create(user=self.student2, course=self.pub_course)
        LSEnrollment.objects.create(user=self.student3, course=self.pub_course)

        # Unpublished draft course
        self.draft_course = LSCourse.objects.create(
            title='Quantum Computing Primer',
            description='Draft curriculum on qubits',
            category='Physics',
            instructor=self.instructor,
            is_published=False
        )
        self.draft_lesson = LSLesson.objects.create(
            course=self.draft_course,
            title='Superposition',
            content='Quantum states',
            position=1
        )

    # --- BUG 8: Catalog count deflation / accurate counting ---

    def test_catalog_counts_not_inflated_by_joins(self):
        """
        Verify that a course with 4 lessons and 3 enrolled students reports
        n_lessons = 4 and n_students = 3, NEVER 4 * 3 = 12.
        """
        self.client.login(username='STU201', password='password123')
        response = self.client.get(reverse('ls_catalog'))
        self.assertEqual(response.status_code, 200)

        courses = list(response.context['courses'])
        pub = next(c for c in courses if c.id == self.pub_course.id)
        self.assertEqual(pub.n_lessons, 4, f"Expected 4 lessons, got {pub.n_lessons}")
        self.assertEqual(pub.n_students, 3, f"Expected 3 students, got {pub.n_students}")

    def test_search_and_category_counts_accurate(self):
        """Search query and category filtering preserve distinct course count."""
        self.client.login(username='STU201', password='password123')
        # Search by lesson content
        response = self.client.get(reverse('ls_catalog'), {'q': 'Django'})
        self.assertEqual(response.status_code, 200)
        courses = list(response.context['courses'])
        self.assertEqual(len(courses), 1)
        self.assertEqual(courses[0].id, self.pub_course.id)
        self.assertEqual(courses[0].n_lessons, 4)
        self.assertEqual(courses[0].n_students, 3)

    def test_student_total_courses_reflects_only_published(self):
        """Student metrics must only count published courses, omitting drafts."""
        self.client.login(username='STU201', password='password123')
        response = self.client.get(reverse('ls_catalog'))
        self.assertEqual(response.status_code, 200)
        # 1 published course in DB, 1 draft course
        self.assertEqual(response.context['metrics']['total_courses'], 1)

    # --- BUG 6: Protect course enrollment and lesson completion ---

    def test_enroll_requires_post(self):
        """GET request to enroll must be rejected with 405 Method Not Allowed."""
        self.client.login(username='STU201', password='password123')
        response = self.client.get(reverse('ls_enroll', kwargs={'course_id': self.pub_course.id}))
        self.assertEqual(response.status_code, 405)

    def test_cannot_enroll_in_unpublished_course(self):
        """Students cannot enroll in draft/unpublished courses."""
        self.client.login(username='STU201', password='password123')
        response = self.client.post(reverse('ls_enroll', kwargs={'course_id': self.draft_course.id}), follow=True)
        self.assertFalse(LSEnrollment.objects.filter(user=self.student, course=self.draft_course).exists())
        self.assertContains(response, 'Cannot enroll in an unpublished course')

    def test_complete_lesson_requires_post(self):
        """GET request to complete_lesson must be rejected with 405 Method Not Allowed."""
        self.client.login(username='STU201', password='password123')
        response = self.client.get(reverse('ls_complete_lesson', kwargs={'lesson_id': self.l1.id}))
        self.assertEqual(response.status_code, 405)
        self.assertFalse(LSProgress.objects.filter(user=self.student, lesson=self.l1).exists())

    def test_cannot_complete_unpublished_lesson(self):
        """Students cannot complete lessons in an unpublished course."""
        self.client.login(username='STU201', password='password123')
        response = self.client.post(reverse('ls_complete_lesson', kwargs={'lesson_id': self.draft_lesson.id}), follow=True)
        self.assertFalse(LSProgress.objects.filter(user=self.student, lesson=self.draft_lesson).exists())

    def test_unenrolled_student_cannot_complete_lesson(self):
        """Student not enrolled in a course cannot mark its lessons complete."""
        new_student = User.objects.create_user(
            username='STU299',
            password='password123',
            role=User.Role.STUDENT,
            roll_number='STU299'
        )
        self.client.login(username='STU299', password='password123')
        response = self.client.post(reverse('ls_complete_lesson', kwargs={'lesson_id': self.l1.id}), follow=True)
        self.assertFalse(LSProgress.objects.filter(user=new_student, lesson=self.l1).exists())
        self.assertContains(response, 'You must be enrolled in this course to mark lessons complete')

    def test_authorized_student_completes_course_and_earns_voucher(self):
        """Enrolled student completing all lectures earns voucher via POST."""
        self.client.login(username='STU201', password='password123')
        # Complete all 4 lessons
        self.client.post(reverse('ls_complete_lesson', kwargs={'lesson_id': self.l1.id}))
        self.client.post(reverse('ls_complete_lesson', kwargs={'lesson_id': self.l2.id}))
        self.client.post(reverse('ls_complete_lesson', kwargs={'lesson_id': self.l3.id}))
        resp = self.client.post(reverse('ls_complete_lesson', kwargs={'lesson_id': self.l4.id}), follow=True)
        
        self.assertEqual(LSProgress.objects.filter(user=self.student, lesson__course=self.pub_course).count(), 4)
        self.assertTrue(LSVoucher.objects.filter(user=self.student, course=self.pub_course).exists())
        self.assertContains(resp, 'unlocked an exclusive reward voucher')

