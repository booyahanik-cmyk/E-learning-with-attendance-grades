from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('attendance', '0003_backfill_legacy_class_sessions'),
    ]

    operations = [
        migrations.AddConstraint(
            model_name='attendance',
            constraint=models.UniqueConstraint(fields=('student', 'session'), name='unique_attendance_per_student_session'),
        ),
    ]

