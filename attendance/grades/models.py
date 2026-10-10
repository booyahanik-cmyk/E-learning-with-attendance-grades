from decimal import Decimal
from django.conf import settings
from django.db import models
from attendance.models import Course


class Semester(models.Model):
    """An academic semester (e.g. Semester 1, 2, 3, 4)."""
    number = models.PositiveSmallIntegerField(unique=True)
    name = models.CharField(max_length=50, blank=True)
    stamp_text = models.CharField(max_length=20, blank=True)

    class Meta:
        ordering = ['number']

    def save(self, *args, **kwargs):
        if not self.stamp_text:
            self.stamp_text = f"SEM {self.number}"
        if not self.name:
            self.name = f"Semester {self.number}"
        super().save(*args, **kwargs)

    def __str__(self):
        return self.name or f"Semester {self.number}"


class Subject(models.Model):
    """A subject/module examined within a curriculum."""
    code = models.CharField(max_length=20, unique=True)
    name = models.CharField(max_length=150)
    credits = models.PositiveSmallIntegerField(default=4)
    course = models.ForeignKey(
        Course,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='grade_subjects',
        help_text="Optional link to an active attendance course."
    )

    class Meta:
        ordering = ['code']

    def __str__(self):
        return f"{self.code} - {self.name}"


class GradeRecord(models.Model):
    """A student's marks and final grade in a subject for a given semester."""
    class GradeChoices(models.TextChoices):
        O = 'O', 'O (Outstanding)'
        A_PLUS = 'A+', 'A+ (Excellent)'
        A = 'A', 'A (Very Good)'
        B_PLUS = 'B+', 'B+ (Good)'
        B = 'B', 'B (Above Average)'
        C = 'C', 'C (Average)'
        P = 'P', 'P (Pass)'
        F = 'F', 'F (Fail)'

    student = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='grade_records',
        limit_choices_to={'role': 'student'},
    )
    semester = models.ForeignKey(Semester, on_delete=models.PROTECT, related_name='grade_records')
    subject = models.ForeignKey(Subject, on_delete=models.PROTECT, related_name='grade_records')
    
    internal_marks = models.DecimalField(max_digits=5, decimal_places=1, default=0)
    external_marks = models.DecimalField(max_digits=5, decimal_places=1, default=0)
    total_marks = models.DecimalField(max_digits=5, decimal_places=1, default=0)
    grade = models.CharField(max_length=5, choices=GradeChoices.choices, default='A')
    grade_point = models.DecimalField(max_digits=4, decimal_places=1, default=9.0)

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=['student', 'semester', 'subject'],
                name='unique_student_semester_subject_grade'
            )
        ]
        ordering = ['subject__code']

    @staticmethod
    def calculate_grade_and_point(total):
        if total >= 90:
            return 'A+', Decimal('10.0')
        elif total >= 80:
            return 'A', Decimal('9.0')
        elif total >= 70:
            return 'B+', Decimal('8.0')
        elif total >= 60:
            return 'B', Decimal('7.0')
        elif total >= 50:
            return 'C', Decimal('6.0')
        elif total >= 40:
            return 'P', Decimal('5.0')
        else:
            return 'F', Decimal('0.0')

    def save(self, *args, **kwargs):
        self.total_marks = Decimal(str(self.internal_marks)) + Decimal(str(self.external_marks))
        # If grade not explicitly overridden, compute standard letter and point
        if not self.grade:
            self.grade, self.grade_point = self.calculate_grade_and_point(self.total_marks)
        super().save(*args, **kwargs)

    def __str__(self):
        return f"{self.student.username} | {self.subject.code} | {self.grade} ({self.total_marks})"
