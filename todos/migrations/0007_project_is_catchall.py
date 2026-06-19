from django.db import migrations, models


def create_catchalls(apps, schema_editor):
    """Per user: ensure a catchall project exists, then reassign their null-project todos to it.
    If the user already has a project literally named 'Other', flag THAT one as catchall instead
    of creating a new conflicting row."""
    Project = apps.get_model('todos', 'Project')
    Todo = apps.get_model('todos', 'Todo')
    user_ids = set(Project.objects.values_list('user_id', flat=True)) \
        | set(Todo.objects.values_list('user_id', flat=True))
    for uid in user_ids:
        existing_other = Project.objects.filter(user_id=uid, name__iexact='Other').first()
        if existing_other is not None:
            existing_other.is_catchall = True
            existing_other.save(update_fields=['is_catchall'])
            catchall = existing_other
        else:
            max_so = Project.objects.filter(user_id=uid).aggregate(m=models.Max('sort_order'))['m']
            catchall = Project.objects.create(
                user_id=uid,
                name='Other',
                is_catchall=True,
                sort_order=(max_so + 1) if max_so is not None else 0,
            )
        Todo.objects.filter(user_id=uid, project__isnull=True).update(project=catchall)


def reverse_noop(apps, schema_editor):
    pass


class Migration(migrations.Migration):

    dependencies = [
        ('todos', '0006_project_sort_order'),
    ]

    operations = [
        migrations.AddField(
            model_name='project',
            name='is_catchall',
            field=models.BooleanField(default=False),
        ),
        migrations.RunPython(create_catchalls, reverse_noop),
        migrations.AddConstraint(
            model_name='project',
            constraint=models.UniqueConstraint(
                fields=['user'],
                condition=models.Q(is_catchall=True),
                name='one_catchall_per_user',
            ),
        ),
    ]
