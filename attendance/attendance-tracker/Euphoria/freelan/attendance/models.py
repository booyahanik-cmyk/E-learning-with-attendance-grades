from django.contrib.auth.models import AbstractUser
from django.db import models


class User(AbstractUser):
    """A college account. `username` holds the College ID and is the login identifier."""

    class Role(models.TextChoices):
        STUDENT = 'student', 'Student'
        FACULTY = 'faculty', 'Faculty'
        ADMIN = 'admin', 'Admin'

    role = models.CharField(max_length=10, choices=Role.choices, default=Role.STUDENT)
    # Only one of these applies per account, so both are nullable. They must hold
    # NULL rather than '' when unused: MySQL allows repeated NULLs under a unique
    # index but only one ''. save() normalises this (forms hand us '').
    roll_number = models.CharField(max_length=20, unique=True, null=True, blank=True)
    employee_id = models.CharField(max_length=20, unique=True, null=True, blank=True)

    def save(self, *args, **kwargs):
        self.roll_number = self.roll_number or None
        self.employee_id = self.employee_id or None
        super().save(*args, **kwargs)

    def __str__(self):
        return '{} ({})'.format(self.username, self.get_role_display())


class Course(models.Model):
    code = models.CharField(max_length=20, unique=True)
    name = models.CharField(max_length=100)
    faculty = models.ForeignKey(
        User,
        on_delete=models.PROTECT,  # never lose a course by deleting its teacher
        related_name='courses_taught',
        limit_choices_to={'role': User.Role.FACULTY},
    )
    # The enrolment table. Managed from Django admin.
    students = models.ManyToManyField(
        User,
        related_name='courses',
        blank=True,
        limit_choices_to={'role': User.Role.STUDENT},
    )

    def __str__(self):
        return '{} - {}'.format(self.code, self.name)


class Attendance(models.Model):
    class Status(models.TextChoices):
        PRESENT = 'P', 'Present'
        LATE = 'L', 'Late'
        ABSENT = 'A', 'Absent'

    student = models.ForeignKey(User, on_delete=models.CASCADE, related_name='attendance_records')
    course = models.ForeignKey(Course, on_delete=models.CASCADE, related_name='attendance_records')
    date = models.DateField()
    status = models.CharField(max_length=1, choices=Status.choices)
    marked_by = models.ForeignKey(User, on_delete=models.PROTECT, related_name='attendance_marked')
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=['student', 'course', 'date'],
                name='unique_attendance_per_student_course_date',
            ),
        ]

    def __str__(self):
        return '{} | {} | {} | {}'.format(
            self.student.username, self.course.code, self.date, self.status
        )
