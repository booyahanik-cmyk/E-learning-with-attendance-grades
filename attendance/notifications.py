import hashlib
import secrets
import urllib.parse
from datetime import timedelta
from django.conf import settings
from django.core.exceptions import ImproperlyConfigured
from django.core.mail import EmailMultiAlternatives
from django.db import transaction
from django.template.loader import render_to_string
from django.urls import reverse
from django.utils import timezone

from .models import AttendanceCorrectionBatch, AttendanceCorrectionRequest, StudentNotification, User

MAX_DELIVERY_ATTEMPTS = 5


def validate_email_configuration():
    """
    Ensure SMTP credentials and backend are validly configured before dispatch.
    Raises ImproperlyConfigured with a clear actionable message if credentials are missing,
    preventing silent fallback to terminal output or unauthenticated failure.
    """
    backend = getattr(settings, 'EMAIL_BACKEND', '')
    if backend == 'django.core.mail.backends.smtp.EmailBackend':
        user = getattr(settings, 'EMAIL_HOST_USER', '').strip()
        password = getattr(settings, 'EMAIL_HOST_PASSWORD', '').strip()
        if not user or not password:
            raise ImproperlyConfigured(
                "SMTP email delivery is enabled (EMAIL_BACKEND=django.core.mail.backends.smtp.EmailBackend), "
                "but EMAIL_HOST_PASSWORD (Google App Password) is empty. "
                "Please add your 16-character Google App Password to .env before triggering email delivery."
            )


def get_base_url(request_obj=None):
    """
    Returns the configured base URL for external notification links.
    Prioritizes settings.APP_BASE_URL (configured reachable HTTPS host).
    Prevents localhost/127.0.0.1 links in real external notifications if configured.
    """
    base_url = getattr(settings, 'APP_BASE_URL', '').strip().rstrip('/')
    if base_url:
        return base_url
    if request_obj:
        host = request_obj.get_host()
        return f"{request_obj.scheme}://{host}".rstrip('/')
    return "http://127.0.0.1:8000"


def create_token():
    """Generate a raw URL-safe token and its SHA-256 hash for secure storage."""
    raw_token = secrets.token_urlsafe(32)
    token_hash = hashlib.sha256(raw_token.encode('utf-8')).hexdigest()
    return raw_token, token_hash


def verify_token(raw_token, token_hash):
    """Verify that a raw token matches its stored SHA-256 hash."""
    if not raw_token or not token_hash:
        return False
    computed = hashlib.sha256(raw_token.encode('utf-8')).hexdigest()
    return secrets.compare_digest(computed, token_hash)


def is_batch_eligible_for_retry(batch, max_attempts=MAX_DELIVERY_ATTEMPTS):
    """
    Determine if a failed teacher batch is eligible for retry:
    - Must not have exceeded max_attempts.
    - If previously failed due to missing email, only retry if teacher now has a registered email.
    - Applies exponential backoff based on delivery attempts: min(30, 2 ** (attempts - 1)) minutes.
    """
    if batch.status != 'failed':
        return False
    if batch.delivery_attempts >= max_attempts:
        return False

    teacher_email = (batch.teacher.email or '').strip()
    if 'has no valid registered email address' in (batch.last_error or ''):
        return bool(teacher_email and '@' in teacher_email)

    backoff_minutes = min(30, 2 ** max(0, batch.delivery_attempts - 1))
    last_attempt = batch.email_sent_at or batch.created_at
    if timezone.now() < last_attempt + timedelta(minutes=backoff_minutes):
        return False
    return True


def is_student_notif_eligible_for_retry(notif, max_attempts=MAX_DELIVERY_ATTEMPTS):
    """
    Determine if a failed student notification is eligible for retry:
    - Must not have exceeded max_attempts.
    - If previously flagged as invalid/missing email, only retry if student now has a registered email.
    - Applies exponential backoff based on delivery attempts: min(30, 2 ** (attempts - 1)) minutes.
    """
    if notif.email_status not in [StudentNotification.EmailStatus.FAILED, StudentNotification.EmailStatus.INVALID_EMAIL]:
        return False
    if notif.email_delivery_attempts >= max_attempts:
        return False

    student_email = (notif.student.email or '').strip()
    if notif.email_status == StudentNotification.EmailStatus.INVALID_EMAIL or 'has no valid registered email address' in (notif.email_last_error or ''):
        return bool(student_email and '@' in student_email)

    backoff_minutes = min(30, 2 ** max(0, notif.email_delivery_attempts - 1))
    last_attempt = notif.email_sent_at or notif.created_at
    if timezone.now() < last_attempt + timedelta(minutes=backoff_minutes):
        return False
    return True


def send_batch_email(batch, raw_token, requests_list, request_obj=None):
    """
    Construct and send a grouped email notification (HTML and plain text)
    summarizing attendance correction requests to the responsible teacher.
    Generates the review path using reverse('review_corrections') and URL-encodes parameters.
    """
    teacher_email = (batch.teacher.email or '').strip()
    if not teacher_email or '@' not in teacher_email:
        err_msg = f"Teacher '{batch.teacher.username}' has no valid registered email address in the database."
        batch.delivery_attempts += 1
        batch.status = 'failed'
        batch.last_error = err_msg
        batch.email_sent_at = timezone.now()
        batch.save(update_fields=['delivery_attempts', 'status', 'last_error', 'email_sent_at'])
        return False, err_msg

    # Build URL using named resolution and URL-encoded query parameters
    params = urllib.parse.urlencode({
        'batch': str(batch.batch_id),
        'token': raw_token,
    })
    resolved_path = reverse('review_corrections')
    query_path = f"{resolved_path}?{params}"

    base_url = get_base_url(request_obj)
    if base_url:
        review_url = f"{base_url.rstrip('/')}/{query_path.lstrip('/')}"
    elif request_obj:
        review_url = request_obj.build_absolute_uri(query_path)
    else:
        review_url = query_path

    count = len(requests_list)
    subject = f"[Cobra Coaching] {count} student{'s' if count != 1 else ''} requested attendance corrections"

    context = {
        'batch': batch,
        'teacher': batch.teacher,
        'requests': requests_list,
        'count': count,
        'review_url': review_url,
        'expires_at': batch.token_expires_at,
    }

    text_body = render_to_string('attendance/emails/batch_notification.txt', context)
    html_body = render_to_string('attendance/emails/batch_notification.html', context)

    msg = EmailMultiAlternatives(
        subject=subject,
        body=text_body,
        from_email=settings.DEFAULT_FROM_EMAIL,
        to=[teacher_email]
    )
    msg.attach_alternative(html_body, "text/html")

    try:
        validate_email_configuration()
        msg.send(fail_silently=False)
        batch.email_sent_at = timezone.now()
        batch.status = 'sent'
        batch.last_error = ''
        batch.save(update_fields=['email_sent_at', 'status', 'last_error'])
        return True, ""
    except Exception as exc:
        batch.delivery_attempts += 1
        batch.status = 'failed'
        batch.last_error = str(exc)
        batch.email_sent_at = timezone.now()
        batch.save(update_fields=['delivery_attempts', 'status', 'last_error', 'email_sent_at'])
        return False, str(exc)


def send_student_decision_email(student_notification, request_obj=None):
    """
    Send an individual decision notification (Approval or Rejection) directly
    to the student's registered email address after decision commitment.
    Never includes the teacher's private review token or decisions of other students.
    """
    student = student_notification.student
    req = student_notification.correction_request

    student_email = (student.email or '').strip()
    if not student_email or '@' not in student_email:
        err_msg = f"Student '{student.username}' has no valid registered email address in the database."
        student_notification.email_delivery_attempts += 1
        student_notification.email_status = StudentNotification.EmailStatus.INVALID_EMAIL
        student_notification.email_last_error = err_msg
        student_notification.email_sent_at = timezone.now()
        student_notification.save(update_fields=['email_delivery_attempts', 'email_status', 'email_last_error', 'email_sent_at'])
        return False, err_msg

    is_approved = (req.status == AttendanceCorrectionRequest.Status.APPROVED)
    is_rejected = (req.status == AttendanceCorrectionRequest.Status.REJECTED)

    if not is_approved and not is_rejected:
        return False, "Request is not decided yet."

    base_url = get_base_url(request_obj)
    attendance_path = reverse('student_home')
    request_details_path = reverse('my_correction_requests')

    if base_url:
        attendance_url = f"{base_url.rstrip('/')}/{attendance_path.lstrip('/')}"
        request_details_url = f"{base_url.rstrip('/')}/{request_details_path.lstrip('/')}"
    elif request_obj:
        attendance_url = request_obj.build_absolute_uri(attendance_path)
        request_details_url = request_obj.build_absolute_uri(request_details_path)
    else:
        attendance_url = attendance_path
        request_details_url = request_details_path

    if is_approved:
        subject = f"Attendance correction approved — {req.course.code}"
        template_base = 'attendance/emails/student_approval'
    else:
        subject = f"Attendance correction rejected — {req.course.code}"
        template_base = 'attendance/emails/student_rejection'

    context = {
        'student': student,
        'course': req.course,
        'session': req.session,
        'previous_status': req.get_original_status_display() or 'Missing / Unmarked',
        'corrected_status': req.get_requested_status_display(),
        'rejection_reason': req.rejection_reason,
        'attendance_url': attendance_url,
        'request_details_url': request_details_url,
    }

    text_body = render_to_string(f"{template_base}.txt", context)
    html_body = render_to_string(f"{template_base}.html", context)

    msg = EmailMultiAlternatives(
        subject=subject,
        body=text_body,
        from_email=settings.DEFAULT_FROM_EMAIL,
        to=[student_email]
    )
    msg.attach_alternative(html_body, "text/html")

    try:
        validate_email_configuration()
        msg.send(fail_silently=False)
        student_notification.email_sent_at = timezone.now()
        student_notification.email_status = StudentNotification.EmailStatus.SENT
        student_notification.email_last_error = ''
        student_notification.save(update_fields=['email_sent_at', 'email_status', 'email_last_error'])
        return True, ""
    except Exception as exc:
        student_notification.email_delivery_attempts += 1
        student_notification.email_status = StudentNotification.EmailStatus.FAILED
        student_notification.email_last_error = str(exc)
        student_notification.email_sent_at = timezone.now()
        student_notification.save(update_fields=['email_delivery_attempts', 'email_status', 'email_last_error', 'email_sent_at'])
        return False, str(exc)


def process_pending_notifications(force_now=False, request_obj=None, retry_eligible=True):
    """
    Group pending correction requests by teacher and dispatch grouped email notifications.
    Supports configurable batching window (default 0 for immediate eligibility in local use),
    and automatic retries with exponential backoff and attempt limits.
    """
    batch_minutes = getattr(settings, 'ATTENDANCE_BATCH_MINUTES', 0)
    cutoff_time = timezone.now() - timedelta(minutes=batch_minutes)

    retry_results = []
    if retry_eligible:
        failed_batches = AttendanceCorrectionBatch.objects.filter(status='failed').select_related('teacher')
        for b in failed_batches:
            if not is_batch_eligible_for_retry(b):
                continue
            req_list = list(b.requests.all())
            raw_token, token_hash = create_token()
            b.token_hash = token_hash
            b.save(update_fields=['token_hash'])
            success, err = send_batch_email(b, raw_token, req_list, request_obj)
            retry_results.append({
                'teacher': b.teacher.username,
                'count': len(req_list),
                'success': success,
                'error': err,
                'retried': True
            })

    # Find unbatched pending requests
    pending_qs = AttendanceCorrectionRequest.objects.filter(
        status=AttendanceCorrectionRequest.Status.PENDING,
        batch__isnull=True
    ).select_related('student', 'course', 'session', 'teacher')

    if not force_now and batch_minutes > 0:
        pending_qs = pending_qs.filter(created_at__lte=cutoff_time)

    # Group by responsible teacher
    teacher_groups = {}
    for req in pending_qs:
        teacher_groups.setdefault(req.teacher, []).append(req)

    results = list(retry_results)

    for teacher, req_list in teacher_groups.items():
        if not req_list:
            continue

        raw_token, token_hash = create_token()
        expiry_hours = getattr(settings, 'ATTENDANCE_LINK_EXPIRY_HOURS', 48)
        expires_at = timezone.now() + timedelta(hours=expiry_hours)

        with transaction.atomic():
            batch = AttendanceCorrectionBatch.objects.create(
                teacher=teacher,
                token_hash=token_hash,
                token_expires_at=expires_at,
                status='pending'
            )
            for req in req_list:
                req.batch = batch
                req.save(update_fields=['batch'])

            def do_send(b=batch, t=raw_token, r_list=req_list, req_o=request_obj):
                success, err = send_batch_email(b, t, r_list, req_o)
                results.append({
                    'teacher': b.teacher.username,
                    'count': len(r_list),
                    'success': success,
                    'error': err,
                    'retried': False
                })

            transaction.on_commit(do_send)

    return results


def process_pending_student_notifications(retry_eligible=True, request_obj=None):
    """
    Process pending student decision emails, and automatically retry eligible temporary failures
    subject to exponential backoff and max attempt limits.
    """
    # 1. Fresh pending notifications
    pending_notifs = list(
        StudentNotification.objects.filter(
            email_status=StudentNotification.EmailStatus.PENDING
        ).select_related('student', 'correction_request', 'correction_request__course', 'correction_request__session')
    )

    # 2. Eligible failed notifications
    if retry_eligible:
        failed_notifs = StudentNotification.objects.filter(
            email_status__in=[
                StudentNotification.EmailStatus.FAILED,
                StudentNotification.EmailStatus.INVALID_EMAIL
            ]
        ).select_related('student', 'correction_request', 'correction_request__course', 'correction_request__session')

        for fn in failed_notifs:
            if is_student_notif_eligible_for_retry(fn):
                pending_notifs.append(fn)

    results = []
    for notif in pending_notifs:
        success, err = send_student_decision_email(notif, request_obj=request_obj)
        results.append({
            'student': notif.student.username,
            'request_id': notif.correction_request.id,
            'success': success,
            'error': err
        })
    return results
