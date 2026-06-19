from django.db import migrations, models
from django.db.models import F


def backfill_timestamps(apps, schema_editor):
    Todo = apps.get_model('todos', 'Todo')
    # All existing rows: updated_at = created_at (best approximation of "never updated")
    Todo.objects.update(updated_at=F('created_at'))
    # For rows already marked done, set completed_at = created_at as a best-effort backfill
    Todo.objects.filter(done=True).update(completed_at=F('created_at'))


def reverse_noop(apps, schema_editor):
    pass


class Migration(migrations.Migration):

    dependencies = [
        ('todos', '0003_tag_todo_tags_tag_unique_tag_name_per_user_ci'),
    ]

    operations = [
        migrations.AddField(
            model_name='todo',
            name='updated_at',
            # temporarily nullable so we can backfill, then alter to auto_now
            field=models.DateTimeField(null=True),
        ),
        migrations.AddField(
            model_name='todo',
            name='completed_at',
            field=models.DateTimeField(blank=True, null=True),
        ),
        migrations.RunPython(backfill_timestamps, reverse_noop),
        migrations.AlterField(
            model_name='todo',
            name='updated_at',
            field=models.DateTimeField(auto_now=True),
        ),
    ]
