from decimal import Decimal, InvalidOperation
from django.conf import settings
from django.core.exceptions import ValidationError
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
    
    internal_marks = models.DecimalField(max_digits=5, decimal_places=1, default=Decimal('0.0'))
    external_marks = models.DecimalField(max_digits=5, decimal_places=1, default=Decimal('0.0'))
    total_marks = models.DecimalField(max_digits=5, decimal_places=1, default=Decimal('0.0'))
    grade = models.CharField(max_length=5, choices=GradeChoices.choices, default='F')
    grade_point = models.DecimalField(max_digits=4, decimal_places=1, default=Decimal('0.0'))

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
        """
        Calculates letter grade and grade point using the institutional 10-point grading scale:
        - 90.0 to 100.0: A+ (10.0 grade points)
        - 80.0 to 89.9:  A  (9.0 grade points)
        - 70.0 to 79.9:  B+ (8.0 grade points)
        - 60.0 to 69.9:  B  (7.0 grade points)
        - 50.0 to 59.9:  C  (6.0 grade points)
        - 40.0 to 49.9:  P  (5.0 grade points)
        - 0.0 to 39.9:   F  (0.0 grade points, Fail)
        Note: This is Cobra Coaching's documented institutional scale.
        """
        try:
            total_dec = Decimal(str(total))
        except (InvalidOperation, TypeError, ValueError):
            return 'F', Decimal('0.0')

        if total_dec >= Decimal('90.0'):
            return 'A+', Decimal('10.0')
        elif total_dec >= Decimal('80.0'):
            return 'A', Decimal('9.0')
        elif total_dec >= Decimal('70.0'):
            return 'B+', Decimal('8.0')
        elif total_dec >= Decimal('60.0'):
            return 'B', Decimal('7.0')
        elif total_dec >= Decimal('50.0'):
            return 'C', Decimal('6.0')
        elif total_dec >= Decimal('40.0'):
            return 'P', Decimal('5.0')
        else:
            return 'F', Decimal('0.0')

    def clean(self):
        super().clean()
        errors = {}

        # Validate internal marks range: 0.0 to 20.0
        try:
            internal_val = Decimal(str(self.internal_marks))
            if internal_val.is_nan() or internal_val.is_infinite():
                errors['internal_marks'] = "Internal marks must be a valid finite number."
            elif internal_val < Decimal('0.0') or internal_val > Decimal('20.0'):
                errors['internal_marks'] = "Internal marks must be between 0.0 and 20.0."
            elif internal_val.as_tuple().exponent < -1:
                errors['internal_marks'] = "Internal marks cannot exceed 1 decimal place of precision."
        except (InvalidOperation, TypeError, ValueError):
            errors['internal_marks'] = "Invalid numeric format for internal marks."

        # Validate external marks range: 0.0 to 80.0
        try:
            external_val = Decimal(str(self.external_marks))
            if external_val.is_nan() or external_val.is_infinite():
                errors['external_marks'] = "External marks must be a valid finite number."
            elif external_val < Decimal('0.0') or external_val > Decimal('80.0'):
                errors['external_marks'] = "External marks must be between 0.0 and 80.0."
            elif external_val.as_tuple().exponent < -1:
                errors['external_marks'] = "External marks cannot exceed 1 decimal place of precision."
        except (InvalidOperation, TypeError, ValueError):
            errors['external_marks'] = "Invalid numeric format for external marks."

        if not errors:
            tot = internal_val + external_val
            if tot < Decimal('0.0') or tot > Decimal('100.0'):
                errors['total_marks'] = "Total marks must be between 0.0 and 100.0."

        if errors:
            raise ValidationError(errors)

    def save(self, *args, **kwargs):
        # Calculate total marks and derive grade and grade point
        try:
            internal_val = Decimal(str(self.internal_marks))
            external_val = Decimal(str(self.external_marks))
        except (InvalidOperation, TypeError, ValueError):
            internal_val = Decimal('0.0')
            external_val = Decimal('0.0')

        self.total_marks = internal_val + external_val
        self.grade, self.grade_point = self.calculate_grade_and_point(self.total_marks)
        super().save(*args, **kwargs)

    def __str__(self):
        return f"{self.student.username} | {self.subject.code} | {self.grade} ({self.total_marks})"
