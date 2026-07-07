from django.conf import settings
from django.db import models
from django.db.models.functions import Lower


class Project(models.Model):
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='projects',
    )
    name = models.CharField(max_length=80)
    sort_order = models.PositiveIntegerField(default=0)
    is_catchall = models.BooleanField(default=False)
    color = models.CharField(max_length=7, blank=True, default='')
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['sort_order', 'name']
        constraints = [
            models.UniqueConstraint(fields=['user', 'name'], name='unique_project_name_per_user'),
            models.UniqueConstraint(
                fields=['user'],
                condition=models.Q(is_catchall=True),
                name='one_catchall_per_user',
            ),
        ]

    def __str__(self):
        return self.name


class Tag(models.Model):
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='tags',
    )
    name = models.CharField(max_length=50)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['name']
        constraints = [
            models.UniqueConstraint(Lower('name'), 'user', name='unique_tag_name_per_user_ci'),
        ]

    def __str__(self):
        return self.name


class Todo(models.Model):
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='todos',
    )
    project = models.ForeignKey(
        Project,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name='todos',
    )
    tags = models.ManyToManyField(Tag, blank=True, related_name='todos')
    title = models.CharField(max_length=200)
    done = models.BooleanField(default=False)
    due_date = models.DateField(null=True, blank=True)
    source = models.ForeignKey(
        'RecurringTodo',
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name='materialized',
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    completed_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        ordering = ['done', 'id']
        constraints = [
            # A recurring template can produce at most one todo per due date.
            # source=NULL (manually-created todos) is exempt: NULLs are distinct.
            models.UniqueConstraint(
                fields=['source', 'due_date'],
                name='unique_recurring_todo_per_due_date',
            ),
        ]

    def __str__(self):
        return self.title


class RecurringTodo(models.Model):
    DAYS_OF_WEEK = [
        (0, 'Monday'),
        (1, 'Tuesday'),
        (2, 'Wednesday'),
        (3, 'Thursday'),
        (4, 'Friday'),
        (5, 'Saturday'),
        (6, 'Sunday'),
    ]

    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='recurring_todos',
    )
    project = models.ForeignKey(
        Project,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name='recurring_todos',
    )
    tags = models.ManyToManyField(Tag, blank=True, related_name='recurring_todos')
    title = models.CharField(max_length=200)
    day_of_week = models.PositiveSmallIntegerField(choices=DAYS_OF_WEEK, default=6)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['day_of_week', 'id']

    def __str__(self):
        return self.title

    def next_due_date(self, base=None):
        """The date of the coming occurrence of day_of_week on or after base."""
        from datetime import timedelta
        from django.utils import timezone
        base = base or timezone.localdate()
        offset = (self.day_of_week - base.weekday()) % 7
        return base + timedelta(days=offset)

    def materialize(self, base=None):
        """Create the concrete Todo for the coming week, once.

        Idempotent: if a todo already exists for this template + due date
        (e.g. the UI already seeded it, or the cron ran twice), the existing
        one is returned instead of a duplicate. Returns (todo, created).
        """
        from todos.views import _get_or_create_catchall
        project = self.project or _get_or_create_catchall(self.user)
        todo, created = Todo.objects.get_or_create(
            source=self,
            due_date=self.next_due_date(base),
            defaults={'user': self.user, 'project': project, 'title': self.title},
        )
        if created:
            todo.tags.set(list(self.tags.all()))
        return todo, created
