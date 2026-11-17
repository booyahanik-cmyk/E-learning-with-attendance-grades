import uuid
from django.contrib.auth.models import AbstractUser
from django.db import models
from django.utils import timezone


class User(AbstractUser):
    """A college account. `username` holds the College ID and is the login identifier."""

    class Role(models.TextChoices):
        STUDENT = 'student', 'Student'
        FACULTY = 'faculty', 'Faculty'
        ADMIN = 'admin', 'Admin'

    role = models.CharField(max_length=10, choices=Role.choices, default=Role.STUDENT)
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
        on_delete=models.PROTECT,
        related_name='courses_taught',
        limit_choices_to={'role': User.Role.FACULTY},
    )
    students = models.ManyToManyField(
        User,
        related_name='courses',
        blank=True,
        limit_choices_to={'role': User.Role.STUDENT},
    )

    def __str__(self):
        return '{} - {}'.format(self.code, self.name)


class ClassSession(models.Model):
    """
    An individual lecture session for a course on a given date.
    Supports multiple sessions on the same date (e.g. Session 1, Session 2).
    """
    course = models.ForeignKey(Course, on_delete=models.CASCADE, related_name='sessions')
    date = models.DateField()
    session_identifier = models.CharField(max_length=50, default='Session 1')
    is_published = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['-date', 'session_identifier']
        constraints = [
            models.UniqueConstraint(
                fields=['course', 'date', 'session_identifier'],
                name='unique_session_per_course_date_identifier'
            )
        ]

    def __str__(self):
        return f"{self.course.code} | {self.date} | {self.session_identifier}"


class Attendance(models.Model):
    class Status(models.TextChoices):
        PRESENT = 'P', 'Present'
        LATE = 'L', 'Late'
        ABSENT = 'A', 'Absent'

    session = models.ForeignKey(
        ClassSession,
        on_delete=models.CASCADE,
        related_name='attendance_records',
        null=True,
        blank=True
    )
    student = models.ForeignKey(User, on_delete=models.CASCADE, related_name='attendance_records')
    course = models.ForeignKey(Course, on_delete=models.CASCADE, related_name='attendance_records')
    date = models.DateField()
    status = models.CharField(max_length=1, choices=Status.choices)
    marked_by = models.ForeignKey(User, on_delete=models.PROTECT, related_name='attendance_marked')
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=['student', 'session'],
                name='unique_attendance_per_student_session',
            ),
        ]

    def save(self, *args, **kwargs):
        if self.session:
            self.course = self.session.course
            self.date = self.session.date
        elif self.course and self.date and not self.session:
            session, _ = ClassSession.objects.get_or_create(
                course=self.course,
                date=self.date,
                session_identifier='Session 1',
                defaults={'is_published': True}
            )
            self.session = session
        super().save(*args, **kwargs)

    def __str__(self):
        sess_str = self.session.session_identifier if self.session else str(self.date)
        return f"{self.student.username} | {self.course.code} | {sess_str} | {self.status}"


class AttendanceCorrectionBatch(models.Model):
    """
    Stores batched email notification dispatches and secure, expiring passwordless tokens.
    """
    batch_id = models.UUIDField(default=uuid.uuid4, unique=True, editable=False)
    teacher = models.ForeignKey(User, on_delete=models.CASCADE, related_name='correction_batches')
    token_hash = models.CharField(max_length=64, blank=True)
    token_expires_at = models.DateTimeField(null=True, blank=True)
    is_revoked = models.BooleanField(default=False)
    email_sent_at = models.DateTimeField(null=True, blank=True)
    delivery_attempts = models.PositiveSmallIntegerField(default=0)
    last_error = models.TextField(blank=True)
    status = models.CharField(max_length=20, default='pending')  # pending, sent, failed
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-created_at']

    def is_valid_for_access(self):
        if self.is_revoked:
            return False, "This email access link has been revoked."
        if not self.token_expires_at or timezone.now() > self.token_expires_at:
            return False, "This email access link has expired. Please log in with your faculty account."
        return True, ""

    def __str__(self):
        return f"Batch {self.batch_id} for {self.teacher.username} ({self.status})"


class AttendanceCorrectionRequest(models.Model):
    """
    A student's request for attendance correction on a genuine published class session.
    """
    class Status(models.TextChoices):
        PENDING = 'pending', 'Pending'
        APPROVED = 'approved', 'Approved'
        REJECTED = 'rejected', 'Rejected'
        CANCELLED = 'cancelled', 'Cancelled'

    student = models.ForeignKey(User, on_delete=models.CASCADE, related_name='correction_requests')
    session = models.ForeignKey(ClassSession, on_delete=models.CASCADE, related_name='correction_requests')
    course = models.ForeignKey(Course, on_delete=models.CASCADE, related_name='correction_requests')
    requested_status = models.CharField(max_length=1, choices=Attendance.Status.choices)
    original_status = models.CharField(max_length=1, choices=Attendance.Status.choices, null=True, blank=True)
    reason = models.TextField()
    status = models.CharField(max_length=10, choices=Status.choices, default=Status.PENDING)
    teacher = models.ForeignKey(User, on_delete=models.PROTECT, related_name='correction_reviews')
    reviewed_at = models.DateTimeField(null=True, blank=True)
    rejection_reason = models.TextField(blank=True, default='')
    access_method = models.CharField(max_length=20, blank=True, default='')  # 'session' or 'email_token'
    batch = models.ForeignKey(
        AttendanceCorrectionBatch,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='requests'
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['-created_at']

    def __str__(self):
        return f"{self.student.username} | {self.course.code} | {self.session.date} | {self.status}"


class AttendanceAuditLog(models.Model):
    """
    Immutable audit history recording every attendance change, reviewer, method, and reason.
    """
    attendance = models.ForeignKey(
        Attendance,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='audit_logs'
    )
    student = models.ForeignKey(User, on_delete=models.CASCADE, related_name='attendance_audit_logs')
    session = models.ForeignKey(ClassSession, on_delete=models.CASCADE, related_name='attendance_audit_logs')
    course = models.ForeignKey(Course, on_delete=models.CASCADE)
    previous_status = models.CharField(max_length=1, null=True, blank=True)
    new_status = models.CharField(max_length=1, null=True, blank=True)
    changed_by = models.ForeignKey(User, on_delete=models.PROTECT, related_name='attendance_changes_made')
    decision_reason = models.TextField(blank=True)
    access_method = models.CharField(max_length=20, default='session')  # 'session' or 'email_token'
    correction_request = models.ForeignKey(
        AttendanceCorrectionRequest,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='audit_logs'
    )
    timestamp = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-timestamp']

    def __str__(self):
        prev = self.previous_status or 'None'
        return f"{self.student.username} ({self.course.code}): {prev} -> {self.new_status} by {self.changed_by.username} [{self.access_method}]"


class StudentNotification(models.Model):
    """
    Student notification and email delivery tracking record created upon decision commitment.
    """
    class EmailStatus(models.TextChoices):
        PENDING = 'pending', 'Pending'
        SENT = 'sent', 'Sent'
        FAILED = 'failed', 'Failed'
        INVALID_EMAIL = 'invalid_email', 'Invalid/Missing Email'

    student = models.ForeignKey(User, on_delete=models.CASCADE, related_name='notifications')
    correction_request = models.ForeignKey(
        AttendanceCorrectionRequest,
        on_delete=models.CASCADE,
        related_name='notifications'
    )
    message = models.TextField()
    is_read = models.BooleanField(default=False)
    email_status = models.CharField(
        max_length=20,
        choices=EmailStatus.choices,
        default=EmailStatus.PENDING
    )
    email_sent_at = models.DateTimeField(null=True, blank=True)
    email_delivery_attempts = models.PositiveSmallIntegerField(default=0)
    email_last_error = models.TextField(blank=True, default='')
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-created_at']

    def __str__(self):
        return f"To {self.student.username}: {self.message[:50]}"


class AttendanceCorrectionWindowExtension(models.Model):
    """
    Administrative exception grant extending the request window beyond the default 7 days.
    """
    course = models.ForeignKey(Course, on_delete=models.CASCADE, null=True, blank=True, related_name='window_extensions')
    student = models.ForeignKey(User, on_delete=models.CASCADE, null=True, blank=True, related_name='window_extensions')
    session = models.ForeignKey(ClassSession, on_delete=models.CASCADE, null=True, blank=True, related_name='window_extensions')
    extended_until = models.DateTimeField()
    created_by = models.ForeignKey(User, on_delete=models.PROTECT)
    reason = models.CharField(max_length=255)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-created_at']

    def __str__(self):
        target = self.student or self.course or self.session or "Global"
        return f"Extension until {self.extended_until} for {target}"
