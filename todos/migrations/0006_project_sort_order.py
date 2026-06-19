from django.db import migrations, models


def backfill_sort_order(apps, schema_editor):
    Project = apps.get_model('todos', 'Project')
    for uid in Project.objects.values_list('user_id', flat=True).distinct():
        for i, project in enumerate(Project.objects.filter(user_id=uid).order_by('name')):
            project.sort_order = i
            project.save(update_fields=['sort_order'])


def reverse_noop(apps, schema_editor):
    pass


class Migration(migrations.Migration):

    dependencies = [
        ('todos', '0005_todo_due_date'),
    ]

    operations = [
        migrations.AddField(
            model_name='project',
            name='sort_order',
            field=models.PositiveIntegerField(default=0),
        ),
        migrations.AlterModelOptions(
            name='project',
            options={'ordering': ['sort_order', 'name']},
        ),
        migrations.RunPython(backfill_sort_order, reverse_noop),
    ]
