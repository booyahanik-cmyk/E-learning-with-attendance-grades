from django.db import migrations


def backfill_sessions(apps, schema_editor):
    ClassSession = apps.get_model('attendance', 'ClassSession')
    Attendance = apps.get_model('attendance', 'Attendance')

    # Find all unique (course_id, date) pairs in Attendance
    unique_pairs = Attendance.objects.values_list('course_id', 'date').distinct()
    
    session_map = {}
    for course_id, date_val in unique_pairs:
        session, _ = ClassSession.objects.get_or_create(
            course_id=course_id,
            date=date_val,
            session_identifier='Legacy Session',
            defaults={'is_published': True}
        )
        session_map[(course_id, date_val)] = session.id

    # Update all Attendance records
    for (course_id, date_val), session_id in session_map.items():
        Attendance.objects.filter(course_id=course_id, date=date_val).update(session_id=session_id)


def reverse_backfill(apps, schema_editor):
    Attendance = apps.get_model('attendance', 'Attendance')
    ClassSession = apps.get_model('attendance', 'ClassSession')
    Attendance.objects.filter(session__session_identifier='Legacy Session').update(session=None)
    ClassSession.objects.filter(session_identifier='Legacy Session').delete()


class Migration(migrations.Migration):

    dependencies = [
        ('attendance', '0002_classsession_and_correction_models'),
    ]

    operations = [
        migrations.RunPython(backfill_sessions, reverse_backfill),
    ]

