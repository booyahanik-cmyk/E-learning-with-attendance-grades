import msvcrt
import os
import sys
from pathlib import Path
from django.conf import settings
from django.core.management.base import BaseCommand
from attendance.notifications import (
    process_pending_notifications,
    process_pending_student_notifications,
    validate_email_configuration,
)


class Command(BaseCommand):
    help = "Process pending attendance correction requests and dispatch grouped teacher and student notifications."

    def add_arguments(self, parser):
        parser.add_argument(
            '--now',
            action='store_true',
            help='Dispatch teacher batch notifications immediately without waiting for the batching threshold.',
        )
        parser.add_argument(
            '--no-retry',
            action='store_true',
            help='Skip automatic retry of eligible failed notifications.',
        )
        parser.add_argument(
            '--students-only',
            action='store_true',
            help='Only process/retry student decision notifications.',
        )
        parser.add_argument(
            '--teachers-only',
            action='store_true',
            help='Only process/retry teacher grouped notifications.',
        )

    def handle(self, *args, **options):
        # 1. Prevent overlapping workers using a cross-process lock file on Windows
        lock_file_path = Path(settings.BASE_DIR) / '.notification_processor.lock'
        lock_file = None
        try:
            lock_file = open(lock_file_path, 'a+')
            msvcrt.locking(lock_file.fileno(), msvcrt.LK_NBLCK, 1)
        except (BlockingIOError, OSError):
            self.stdout.write(
                self.style.NOTICE("Another notification processor worker is currently active. Exiting to avoid overlap.")
            )
            return

        try:
            force_now = options.get('now', False)
            retry_eligible = not options.get('no_retry', False)
            students_only = options.get('students_only', False)
            teachers_only = options.get('teachers_only', False)

            # Validate configuration (outputs a clear warning if credentials missing)
            try:
                validate_email_configuration()
            except Exception as exc:
                self.stdout.write(self.style.ERROR(f"Configuration Check: {exc}"))
                self.stdout.write(
                    self.style.WARNING(
                        "Emails cannot be delivered until EMAIL_HOST_PASSWORD is set in .env."
                    )
                )

            # 2. Process Teacher Grouped Notifications
            if not students_only:
                teacher_results = process_pending_notifications(force_now=force_now, retry_eligible=retry_eligible)
                if teacher_results:
                    for res in teacher_results:
                        action_type = "Retried" if res.get('retried') else "Dispatched"
                        if res['success']:
                            self.stdout.write(
                                self.style.SUCCESS(
                                    f"{action_type} email to {res['teacher']} for {res['count']} correction request(s)."
                                )
                            )
                        else:
                            self.stdout.write(
                                self.style.ERROR(
                                    f"Failed delivery to {res['teacher']}: {res['error']}"
                                )
                            )

            # 3. Process Student Decision Notifications
            if not teachers_only:
                student_results = process_pending_student_notifications(retry_eligible=retry_eligible)
                if student_results:
                    for res in student_results:
                        if res['success']:
                            self.stdout.write(
                                self.style.SUCCESS(
                                    f"Dispatched decision email to student {res['student']} (Request #{res['request_id']})."
                                )
                            )
                        else:
                            self.stdout.write(
                                self.style.ERROR(
                                    f"Failed decision email to student {res['student']} (Request #{res['request_id']}): {res['error']}"
                                )
                            )

        finally:
            if lock_file:
                try:
                    msvcrt.locking(lock_file.fileno(), msvcrt.LK_UNLCK, 1)
                    lock_file.close()
                except Exception:
                    pass
