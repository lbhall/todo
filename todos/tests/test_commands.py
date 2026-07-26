from io import StringIO

from django.contrib.auth import get_user_model
from django.core.management import call_command
from django.test import TestCase

from todos.models import Project, RecurringTodo, Tag, Todo

User = get_user_model()


class CreateRecurringTodosCommandTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user('u', password='pw12345!')

    def _run(self, **kwargs):
        out = StringIO()
        call_command('create_recurring_todos', stdout=out, **kwargs)
        return out.getvalue()

    def test_creates_todo_for_template(self):
        RecurringTodo.objects.create(user=self.user, title='Weekly', day_of_week=6)
        output = self._run(today='2026-01-04')  # Sunday
        self.assertIn('Created', output)
        todo = Todo.objects.get(user=self.user, title='Weekly')
        self.assertEqual(str(todo.due_date), '2026-01-04')
        self.assertTrue(todo.project.is_catchall)

    def test_uses_template_project_and_copies_tags(self):
        proj = Project.objects.create(user=self.user, name='Chores')
        tpl = RecurringTodo.objects.create(user=self.user, title='X', project=proj, day_of_week=6)
        tag = Tag.objects.create(user=self.user, name='home')
        tpl.tags.set([tag])
        self._run(today='2026-01-04')
        todo = Todo.objects.get(title='X')
        self.assertEqual(todo.project, proj)
        self.assertEqual(list(todo.tags.all()), [tag])

    def test_idempotent_second_run_skips(self):
        RecurringTodo.objects.create(user=self.user, title='Weekly', day_of_week=6)
        self._run(today='2026-01-04')
        output = self._run(today='2026-01-04')
        self.assertIn('Skipped', output)
        self.assertEqual(Todo.objects.filter(title='Weekly').count(), 1)

    def test_dry_run_writes_nothing(self):
        RecurringTodo.objects.create(user=self.user, title='Weekly', day_of_week=6)
        output = self._run(today='2026-01-04', dry_run=True)
        self.assertIn('DRY-RUN', output)
        self.assertEqual(Todo.objects.count(), 0)

    def test_dry_run_reports_existing_as_skip(self):
        RecurringTodo.objects.create(user=self.user, title='Weekly', day_of_week=6)
        self._run(today='2026-01-04')
        output = self._run(today='2026-01-04', dry_run=True)
        self.assertIn('already exists', output)
        self.assertEqual(Todo.objects.count(), 1)

    def test_default_today_runs(self):
        RecurringTodo.objects.create(user=self.user, title='Weekly', day_of_week=6)
        output = self._run()
        self.assertIn('processed 1 templates', output)
