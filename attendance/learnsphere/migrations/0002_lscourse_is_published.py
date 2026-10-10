from django.db import migrations, models

class Migration(migrations.Migration):

    dependencies = [
        ('learnsphere', '0001_initial'),
    ]

    operations = [
        migrations.AddField(
            model_name='lscourse',
            name='is_published',
            field=models.BooleanField(default=True),
        ),
    ]
