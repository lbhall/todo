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
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    completed_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        ordering = ['done', 'id']

    def __str__(self):
        return self.title
