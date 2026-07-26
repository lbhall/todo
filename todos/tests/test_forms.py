from django.contrib.auth import get_user_model
from django.test import TestCase

from todos.forms import (
    ProjectEditForm,
    ProjectForm,
    RecurringTodoForm,
    SignUpForm,
    TodoForm,
    _split_tag_text,
)
from todos.models import Project, Tag, Todo

User = get_user_model()


class SplitTagTextTests(TestCase):
    def test_empty_and_none(self):
        self.assertEqual(_split_tag_text(''), [])
        self.assertEqual(_split_tag_text(None), [])

    def test_strips_and_dedupes_case_insensitively(self):
        result = _split_tag_text(' a , b ,A, , b ')
        self.assertEqual(result, ['a', 'b'])


class SignUpFormTests(TestCase):
    def test_valid(self):
        form = SignUpForm(data={
            'username': 'newbie',
            'password1': 'Str0ngPass!x',
            'password2': 'Str0ngPass!x',
        })
        self.assertTrue(form.is_valid())

    def test_password_mismatch_invalid(self):
        form = SignUpForm(data={
            'username': 'newbie',
            'password1': 'Str0ngPass!x',
            'password2': 'different',
        })
        self.assertFalse(form.is_valid())


class TodoFormTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user('u', password='pw12345!')
        self.project = Project.objects.create(user=self.user, name='Work')

    def test_valid_minimal(self):
        form = TodoForm(data={'title': 'Do it'}, user=self.user)
        self.assertTrue(form.is_valid())

    def test_blank_title_invalid(self):
        form = TodoForm(data={'title': ''}, user=self.user)
        self.assertFalse(form.is_valid())
        self.assertIn('title', form.errors)

    def test_project_queryset_scoped_to_user(self):
        other = User.objects.create_user('other', password='pw12345!')
        other_proj = Project.objects.create(user=other, name='Theirs')
        form = TodoForm(user=self.user)
        self.assertIn(self.project, form.fields['project'].queryset)
        self.assertNotIn(other_proj, form.fields['project'].queryset)

    def test_tags_text_initial_from_instance(self):
        todo = Todo.objects.create(user=self.user, title='t')
        tag = Tag.objects.create(user=self.user, name='home')
        todo.tags.set([tag])
        form = TodoForm(instance=todo, user=self.user)
        self.assertEqual(form.fields['tags_text'].initial, 'home')

    def test_apply_tags_creates_and_sets(self):
        form = TodoForm(data={'title': 't', 'tags_text': 'alpha, Beta'}, user=self.user)
        self.assertTrue(form.is_valid())
        todo = form.save(commit=False)
        todo.user = self.user
        todo.save()
        form.apply_tags(todo, self.user)
        self.assertEqual(set(todo.tags.values_list('name', flat=True)), {'alpha', 'Beta'})

    def test_apply_tags_reuses_existing_case_insensitive(self):
        Tag.objects.create(user=self.user, name='Home')
        form = TodoForm(data={'title': 't', 'tags_text': 'home'}, user=self.user)
        self.assertTrue(form.is_valid())
        todo = Todo.objects.create(user=self.user, title='t')
        form.apply_tags(todo, self.user)
        self.assertEqual(Tag.objects.filter(user=self.user).count(), 1)
        self.assertEqual(todo.tags.first().name, 'Home')


class RecurringTodoFormTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user('u', password='pw12345!')

    def test_valid(self):
        form = RecurringTodoForm(data={'title': 'Weekly', 'day_of_week': 6}, user=self.user)
        self.assertTrue(form.is_valid())

    def test_label_override(self):
        form = RecurringTodoForm(user=self.user)
        self.assertEqual(form.fields['day_of_week'].label, 'Repeats on')

    def test_apply_tags(self):
        form = RecurringTodoForm(data={'title': 'W', 'day_of_week': 6, 'tags_text': 'x'}, user=self.user)
        self.assertTrue(form.is_valid())
        tpl = form.save(commit=False)
        tpl.user = self.user
        tpl.save()
        form.apply_tags(tpl, self.user)
        self.assertEqual(tpl.tags.first().name, 'x')


class ProjectFormTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user('u', password='pw12345!')

    def test_valid(self):
        form = ProjectForm(data={'name': 'New', 'color': ''}, user=self.user)
        self.assertTrue(form.is_valid())

    def test_blank_name_invalid(self):
        form = ProjectForm(data={'name': '   '}, user=self.user)
        self.assertFalse(form.is_valid())
        self.assertIn('name', form.errors)

    def test_duplicate_name_invalid(self):
        Project.objects.create(user=self.user, name='Dup')
        form = ProjectForm(data={'name': 'dup'}, user=self.user)
        self.assertFalse(form.is_valid())


class ProjectEditFormTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user('u', password='pw12345!')

    def test_blank_name_invalid(self):
        p = Project.objects.create(user=self.user, name='P')
        form = ProjectEditForm(data={'name': ''}, instance=p, user=self.user)
        self.assertFalse(form.is_valid())

    def test_rename_to_same_name_allowed(self):
        p = Project.objects.create(user=self.user, name='Keep')
        form = ProjectEditForm(data={'name': 'Keep'}, instance=p, user=self.user)
        self.assertTrue(form.is_valid())

    def test_rename_to_existing_other_invalid(self):
        Project.objects.create(user=self.user, name='Taken')
        p = Project.objects.create(user=self.user, name='Mine')
        form = ProjectEditForm(data={'name': 'taken'}, instance=p, user=self.user)
        self.assertFalse(form.is_valid())
