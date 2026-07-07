import logging
from datetime import timedelta

from django.core.management.base import BaseCommand
from django.db import transaction
from django.utils import timezone

from todos.models import RecurringTodo, Todo
from todos.views import _get_or_create_catchall

logger = logging.getLogger(__name__)


class Command(BaseCommand):
    help = 'Materialize every RecurringTodo template into a fresh Todo for the coming week. Intended to run weekly on Sundays via cron.'

    def add_arguments(self, parser):
        parser.add_argument(
            '--dry-run',
            action='store_true',
            help='Report what would be created without writing to the database.',
        )
        parser.add_argument(
            '--today',
            default=None,
            help='Override the base date (YYYY-MM-DD). Useful for testing.',
        )

    def handle(self, *args, dry_run=False, today=None, **options):
        from datetime import date
        base = date.fromisoformat(today) if today else timezone.localdate()
        templates = list(
            RecurringTodo.objects
            .select_related('user', 'project')
            .prefetch_related('tags')
        )
        created = 0
        with transaction.atomic():
            for tpl in templates:
                project = tpl.project or _get_or_create_catchall(tpl.user)
                offset = (tpl.day_of_week - base.weekday()) % 7
                due = base + timedelta(days=offset)
                msg = f'user={tpl.user_id} title={tpl.title!r} project={project.name!r} due={due}'
                if dry_run:
                    self.stdout.write(f'DRY-RUN would create: {msg}')
                    continue
                todo = Todo.objects.create(
                    user=tpl.user,
                    project=project,
                    title=tpl.title,
                    due_date=due,
                )
                todo.tags.set(list(tpl.tags.all()))
                created += 1
                self.stdout.write(f'Created: {msg}')
            if dry_run:
                transaction.set_rollback(True)
        summary = f'{"DRY-RUN " if dry_run else ""}base={base} processed {len(templates)} templates, created {created} todos'
        self.stdout.write(self.style.SUCCESS(summary))
        logger.info('create_recurring_todos: %s', summary)
