import django.db.models.deletion
import uuid
from django.conf import settings
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('attendance', '0001_initial'),
    ]

    operations = [
        migrations.CreateModel(
            name='ClassSession',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('date', models.DateField()),
                ('session_identifier', models.CharField(default='Session 1', max_length=50)),
                ('is_published', models.BooleanField(default=True)),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('updated_at', models.DateTimeField(auto_now=True)),
                ('course', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='sessions', to='attendance.course')),
            ],
            options={
                'ordering': ['-date', 'session_identifier'],
            },
        ),
        migrations.AddConstraint(
            model_name='classsession',
            constraint=models.UniqueConstraint(fields=('course', 'date', 'session_identifier'), name='unique_session_per_course_date_identifier'),
        ),
        migrations.CreateModel(
            name='AttendanceCorrectionBatch',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('batch_id', models.UUIDField(default=uuid.uuid4, editable=False, unique=True)),
                ('token_hash', models.CharField(blank=True, max_length=64)),
                ('token_expires_at', models.DateTimeField(blank=True, null=True)),
                ('is_revoked', models.BooleanField(default=False)),
                ('email_sent_at', models.DateTimeField(blank=True, null=True)),
                ('delivery_attempts', models.PositiveSmallIntegerField(default=0)),
                ('last_error', models.TextField(blank=True)),
                ('status', models.CharField(default='pending', max_length=20)),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('teacher', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='correction_batches', to=settings.AUTH_USER_MODEL)),
            ],
            options={
                'ordering': ['-created_at'],
            },
        ),
        migrations.CreateModel(
            name='AttendanceCorrectionRequest',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('requested_status', models.CharField(choices=[('P', 'Present'), ('L', 'Late'), ('A', 'Absent')], max_length=1)),
                ('original_status', models.CharField(blank=True, choices=[('P', 'Present'), ('L', 'Late'), ('A', 'Absent')], max_length=1, null=True)),
                ('reason', models.TextField()),
                ('status', models.CharField(choices=[('pending', 'Pending'), ('approved', 'Approved'), ('rejected', 'Rejected'), ('cancelled', 'Cancelled')], default='pending', max_length=10)),
                ('reviewed_at', models.DateTimeField(blank=True, null=True)),
                ('rejection_reason', models.TextField(blank=True, default='')),
                ('access_method', models.CharField(blank=True, default='', max_length=20)),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('updated_at', models.DateTimeField(auto_now=True)),
                ('batch', models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='requests', to='attendance.attendancecorrectionbatch')),
                ('course', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='correction_requests', to='attendance.course')),
                ('session', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='correction_requests', to='attendance.classsession')),
                ('student', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='correction_requests', to=settings.AUTH_USER_MODEL)),
                ('teacher', models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, related_name='correction_reviews', to=settings.AUTH_USER_MODEL)),
            ],
            options={
                'ordering': ['-created_at'],
            },
        ),
        migrations.CreateModel(
            name='AttendanceAuditLog',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('previous_status', models.CharField(blank=True, max_length=1, null=True)),
                ('new_status', models.CharField(max_length=1)),
                ('decision_reason', models.TextField(blank=True)),
                ('access_method', models.CharField(default='session', max_length=20)),
                ('timestamp', models.DateTimeField(auto_now_add=True)),
                ('attendance', models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='audit_logs', to='attendance.attendance')),
                ('changed_by', models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, related_name='attendance_changes_made', to=settings.AUTH_USER_MODEL)),
                ('correction_request', models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='audit_logs', to='attendance.attendancecorrectionrequest')),
                ('course', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, to='attendance.course')),
                ('session', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='attendance_audit_logs', to='attendance.classsession')),
                ('student', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='attendance_audit_logs', to=settings.AUTH_USER_MODEL)),
            ],
            options={
                'ordering': ['-timestamp'],
            },
        ),
        migrations.CreateModel(
            name='AttendanceCorrectionWindowExtension',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('extended_until', models.DateTimeField()),
                ('reason', models.CharField(max_length=255)),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('course', models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.CASCADE, related_name='window_extensions', to='attendance.course')),
                ('created_by', models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, to=settings.AUTH_USER_MODEL)),
                ('session', models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.CASCADE, related_name='window_extensions', to='attendance.classsession')),
                ('student', models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.CASCADE, related_name='window_extensions', to=settings.AUTH_USER_MODEL)),
            ],
            options={
                'ordering': ['-created_at'],
            },
        ),
        migrations.CreateModel(
            name='StudentNotification',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('message', models.TextField()),
                ('is_read', models.BooleanField(default=False)),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('correction_request', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='notifications', to='attendance.attendancecorrectionrequest')),
                ('student', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='notifications', to=settings.AUTH_USER_MODEL)),
            ],
            options={
                'ordering': ['-created_at'],
            },
        ),
        migrations.RemoveConstraint(
            model_name='attendance',
            name='unique_attendance_per_student_course_date',
        ),
        migrations.AddField(
            model_name='attendance',
            name='session',
            field=models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.CASCADE, related_name='attendance_records', to='attendance.classsession'),
        ),
        migrations.AddField(
            model_name='attendance',
            name='updated_at',
            field=models.DateTimeField(auto_now=True),
        ),
    ]

