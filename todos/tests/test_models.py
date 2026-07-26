from datetime import date, timedelta

from django.contrib.auth import get_user_model
from django.db import IntegrityError
from django.test import TestCase

from todos.models import Project, RecurringTodo, Tag, Todo

User = get_user_model()


class ProjectModelTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user('alice', password='pw12345!')

    def test_str_returns_name(self):
        p = Project.objects.create(user=self.user, name='Work')
        self.assertEqual(str(p), 'Work')

    def test_ordering_by_sort_order_then_name(self):
        Project.objects.create(user=self.user, name='B', sort_order=1)
        Project.objects.create(user=self.user, name='A', sort_order=0)
        Project.objects.create(user=self.user, name='C', sort_order=0)
        names = list(self.user.projects.values_list('name', flat=True))
        # sort_order 0 group first, alpha within it, then sort_order 1
        self.assertEqual(names, ['A', 'C', 'B'])

    def test_unique_name_per_user(self):
        Project.objects.create(user=self.user, name='Dup')
        with self.assertRaises(IntegrityError):
            Project.objects.create(user=self.user, name='Dup')

    def test_one_catchall_per_user_constraint(self):
        Project.objects.create(user=self.user, name='Other', is_catchall=True)
        with self.assertRaises(IntegrityError):
            Project.objects.create(user=self.user, name='Other2', is_catchall=True)


class TagModelTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user('bob', password='pw12345!')

    def test_str_returns_name(self):
        t = Tag.objects.create(user=self.user, name='urgent')
        self.assertEqual(str(t), 'urgent')

    def test_case_insensitive_unique_per_user(self):
        Tag.objects.create(user=self.user, name='Home')
        with self.assertRaises(IntegrityError):
            Tag.objects.create(user=self.user, name='home')


class TodoModelTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user('carol', password='pw12345!')

    def test_str_returns_title(self):
        todo = Todo.objects.create(user=self.user, title='Buy milk')
        self.assertEqual(str(todo), 'Buy milk')

    def test_ordering_open_before_done(self):
        done = Todo.objects.create(user=self.user, title='done', done=True)
        open_ = Todo.objects.create(user=self.user, title='open', done=False)
        ordered = list(self.user.todos.all())
        self.assertEqual(ordered, [open_, done])

    def test_defaults(self):
        todo = Todo.objects.create(user=self.user, title='thing')
        self.assertFalse(todo.done)
        self.assertIsNone(todo.due_date)
        self.assertIsNone(todo.completed_at)
        self.assertIsNone(todo.project)

    def test_unique_recurring_todo_per_due_date(self):
        tpl = RecurringTodo.objects.create(user=self.user, title='weekly')
        due = date(2026, 1, 4)
        Todo.objects.create(user=self.user, title='weekly', source=tpl, due_date=due)
        with self.assertRaises(IntegrityError):
            Todo.objects.create(user=self.user, title='weekly', source=tpl, due_date=due)

    def test_null_source_exempt_from_unique_constraint(self):
        due = date(2026, 1, 4)
        Todo.objects.create(user=self.user, title='a', source=None, due_date=due)
        # Should not raise: NULL sources are distinct.
        Todo.objects.create(user=self.user, title='b', source=None, due_date=due)
        self.assertEqual(self.user.todos.filter(due_date=due).count(), 2)


class RecurringTodoModelTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user('dave', password='pw12345!')

    def test_str_returns_title(self):
        tpl = RecurringTodo.objects.create(user=self.user, title='Trash')
        self.assertEqual(str(tpl), 'Trash')

    def test_default_day_of_week_is_sunday(self):
        tpl = RecurringTodo.objects.create(user=self.user, title='x')
        self.assertEqual(tpl.day_of_week, 6)

    def test_next_due_date_same_day(self):
        # 2026-01-04 is a Sunday (weekday 6).
        tpl = RecurringTodo.objects.create(user=self.user, title='x', day_of_week=6)
        base = date(2026, 1, 4)
        self.assertEqual(tpl.next_due_date(base), base)

    def test_next_due_date_future_in_week(self):
        # base Monday 2026-01-05, target Wednesday (2)
        tpl = RecurringTodo.objects.create(user=self.user, title='x', day_of_week=2)
        base = date(2026, 1, 5)
        self.assertEqual(tpl.next_due_date(base), date(2026, 1, 7))

    def test_next_due_date_wraps_to_next_week(self):
        # base Wednesday 2026-01-07, target Monday (0) -> next Monday
        tpl = RecurringTodo.objects.create(user=self.user, title='x', day_of_week=0)
        base = date(2026, 1, 7)
        self.assertEqual(tpl.next_due_date(base), date(2026, 1, 12))

    def test_next_due_date_defaults_to_today(self):
        tpl = RecurringTodo.objects.create(user=self.user, title='x')
        result = tpl.next_due_date()
        self.assertIsInstance(result, date)

    def test_materialize_creates_todo_with_catchall_project(self):
        tpl = RecurringTodo.objects.create(user=self.user, title='Weekly task', day_of_week=6)
        base = date(2026, 1, 4)
        todo, created = tpl.materialize(base)
        self.assertTrue(created)
        self.assertEqual(todo.title, 'Weekly task')
        self.assertEqual(todo.due_date, base)
        self.assertEqual(todo.source, tpl)
        # No explicit project -> falls back to auto-created catchall.
        self.assertTrue(todo.project.is_catchall)

    def test_materialize_uses_template_project(self):
        proj = Project.objects.create(user=self.user, name='Chores')
        tpl = RecurringTodo.objects.create(user=self.user, title='x', project=proj, day_of_week=6)
        todo, created = tpl.materialize(date(2026, 1, 4))
        self.assertEqual(todo.project, proj)

    def test_materialize_is_idempotent(self):
        tpl = RecurringTodo.objects.create(user=self.user, title='x', day_of_week=6)
        base = date(2026, 1, 4)
        first, created1 = tpl.materialize(base)
        second, created2 = tpl.materialize(base)
        self.assertTrue(created1)
        self.assertFalse(created2)
        self.assertEqual(first.pk, second.pk)
        self.assertEqual(tpl.materialized.count(), 1)

    def test_materialize_copies_tags(self):
        tag = Tag.objects.create(user=self.user, name='home')
        tpl = RecurringTodo.objects.create(user=self.user, title='x', day_of_week=6)
        tpl.tags.set([tag])
        todo, _ = tpl.materialize(date(2026, 1, 4))
        self.assertEqual(list(todo.tags.all()), [tag])
