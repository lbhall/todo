from datetime import timedelta

from django.contrib.auth import get_user_model
from django.test import TestCase
from django.urls import reverse
from django.utils import timezone

from todos.models import Project, RecurringTodo, Tag, Todo
from todos.views import _get_or_create_catchall

User = get_user_model()


class AuthRequiredTests(TestCase):
    """Anonymous users are redirected to login for protected routes."""

    def test_todo_list_requires_login(self):
        resp = self.client.get(reverse('todo_list'))
        self.assertEqual(resp.status_code, 302)
        self.assertIn('/accounts/login/', resp['Location'])

    def test_recurring_list_requires_login(self):
        resp = self.client.get(reverse('recurring_list'))
        self.assertEqual(resp.status_code, 302)


class GetOrCreateCatchallTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user('u', password='pw12345!')

    def test_creates_when_missing(self):
        catchall = _get_or_create_catchall(self.user)
        self.assertTrue(catchall.is_catchall)
        self.assertEqual(catchall.name, 'Other')

    def test_returns_existing(self):
        first = _get_or_create_catchall(self.user)
        second = _get_or_create_catchall(self.user)
        self.assertEqual(first.pk, second.pk)

    def test_sort_order_after_existing_projects(self):
        Project.objects.create(user=self.user, name='A', sort_order=5)
        catchall = _get_or_create_catchall(self.user)
        self.assertEqual(catchall.sort_order, 6)


class SignupViewTests(TestCase):
    def test_get_renders_form(self):
        resp = self.client.get(reverse('signup'))
        self.assertEqual(resp.status_code, 200)
        self.assertIn('form', resp.context)

    def test_post_valid_creates_user_and_catchall(self):
        resp = self.client.post(reverse('signup'), {
            'username': 'fresh',
            'password1': 'Str0ngPass!x',
            'password2': 'Str0ngPass!x',
        })
        self.assertRedirects(resp, reverse('todo_list'))
        user = User.objects.get(username='fresh')
        self.assertTrue(user.projects.filter(is_catchall=True).exists())

    def test_post_invalid_rerenders(self):
        resp = self.client.post(reverse('signup'), {
            'username': 'fresh',
            'password1': 'a',
            'password2': 'b',
        })
        self.assertEqual(resp.status_code, 200)
        self.assertFalse(User.objects.filter(username='fresh').exists())

    def test_authenticated_user_redirected(self):
        user = User.objects.create_user('u', password='pw12345!')
        self.client.force_login(user)
        resp = self.client.get(reverse('signup'))
        self.assertRedirects(resp, reverse('todo_list'))


class TodoListViewTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user('u', password='pw12345!')
        self.client.force_login(self.user)
        self.project = Project.objects.create(user=self.user, name='Work')
        self.today = timezone.localdate()

    def test_list_ok(self):
        Todo.objects.create(user=self.user, title='visible', project=self.project)
        resp = self.client.get(reverse('todo_list'))
        self.assertEqual(resp.status_code, 200)
        self.assertContains(resp, 'visible')

    def test_status_filter_open_default_hides_done(self):
        Todo.objects.create(user=self.user, title='opentask', project=self.project, done=False)
        Todo.objects.create(user=self.user, title='donetask', project=self.project, done=True)
        resp = self.client.get(reverse('todo_list'))
        self.assertContains(resp, 'opentask')
        self.assertNotContains(resp, 'donetask')

    def test_status_done_filter(self):
        Todo.objects.create(user=self.user, title='donetask', project=self.project, done=True)
        resp = self.client.get(reverse('todo_list'), {'status': 'done'})
        self.assertContains(resp, 'donetask')

    def test_status_all_shows_both(self):
        Todo.objects.create(user=self.user, title='opentask', project=self.project)
        Todo.objects.create(user=self.user, title='donetask', project=self.project, done=True)
        resp = self.client.get(reverse('todo_list'), {'status': 'all'})
        self.assertContains(resp, 'opentask')
        self.assertContains(resp, 'donetask')

    def test_status_invalid_falls_back_to_open(self):
        resp = self.client.get(reverse('todo_list'), {'status': 'bogus'})
        self.assertEqual(resp.context['active_status'], 'open')

    def test_due_today_filter(self):
        Todo.objects.create(user=self.user, title='duetoday', project=self.project, due_date=self.today)
        Todo.objects.create(user=self.user, title='noduedate', project=self.project)
        resp = self.client.get(reverse('todo_list'), {'due': 'today'})
        self.assertContains(resp, 'duetoday')
        self.assertNotContains(resp, 'noduedate')

    def test_due_future_filter(self):
        Todo.objects.create(user=self.user, title='futuretask', project=self.project,
                            due_date=self.today + timedelta(days=3))
        resp = self.client.get(reverse('todo_list'), {'due': 'future'})
        self.assertContains(resp, 'futuretask')

    def test_due_past_filter(self):
        Todo.objects.create(user=self.user, title='pasttask', project=self.project,
                            due_date=self.today - timedelta(days=3))
        resp = self.client.get(reverse('todo_list'), {'due': 'past'})
        self.assertContains(resp, 'pasttask')

    def test_tag_filter(self):
        tag = Tag.objects.create(user=self.user, name='urgent')
        tagged = Todo.objects.create(user=self.user, title='taggedtask', project=self.project)
        tagged.tags.set([tag])
        Todo.objects.create(user=self.user, title='untagged', project=self.project)
        resp = self.client.get(reverse('todo_list'), {'tag': 'urgent'})
        self.assertContains(resp, 'taggedtask')
        self.assertNotContains(resp, 'untagged')

    def test_project_filter(self):
        other = Project.objects.create(user=self.user, name='Home')
        Todo.objects.create(user=self.user, title='worktask', project=self.project)
        Todo.objects.create(user=self.user, title='hometask', project=other)
        resp = self.client.get(reverse('todo_list'), {'project': str(self.project.pk)})
        self.assertContains(resp, 'worktask')
        self.assertNotContains(resp, 'hometask')

    def test_project_filter_non_digit_ignored(self):
        resp = self.client.get(reverse('todo_list'), {'project': 'abc'})
        self.assertIsNone(resp.context['active_project'])

    def test_custom_project_color_used(self):
        Project.objects.create(user=self.user, name='Colored', color='#123456')
        resp = self.client.get(reverse('todo_list'))
        colors = {g['project'].name: g['color'] for g in resp.context['groups']}
        self.assertEqual(colors['Colored'], '#123456')


class TodoAddViewTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user('u', password='pw12345!')
        self.client.force_login(self.user)

    def test_get_not_allowed(self):
        resp = self.client.get(reverse('todo_add'))
        self.assertEqual(resp.status_code, 405)

    def test_add_simple_todo_falls_back_to_catchall(self):
        resp = self.client.post(reverse('todo_add'), {'title': 'New task'})
        self.assertEqual(resp.status_code, 302)
        todo = Todo.objects.get(title='New task')
        self.assertTrue(todo.project.is_catchall)

    def test_add_with_project_and_tags(self):
        proj = Project.objects.create(user=self.user, name='Work')
        resp = self.client.post(reverse('todo_add'), {
            'title': 'Task', 'project': proj.pk, 'tags_text': 'a, b',
        })
        self.assertEqual(resp.status_code, 302)
        todo = Todo.objects.get(title='Task')
        self.assertEqual(todo.project, proj)
        self.assertEqual(todo.tags.count(), 2)

    def test_add_recurring_creates_template_and_first_occurrence(self):
        resp = self.client.post(reverse('todo_add'), {
            'title': 'Weekly thing', 'recurring': 'on', 'day_of_week': '2',
        })
        self.assertEqual(resp.status_code, 302)
        tpl = RecurringTodo.objects.get(title='Weekly thing')
        self.assertEqual(tpl.day_of_week, 2)
        self.assertEqual(tpl.materialized.count(), 1)

    def test_add_invalid_returns_400(self):
        resp = self.client.post(reverse('todo_add'), {'title': ''})
        self.assertEqual(resp.status_code, 400)
        self.assertEqual(Todo.objects.count(), 0)

    def test_add_preserves_filters_in_redirect(self):
        resp = self.client.post(reverse('todo_add'), {
            'title': 'x', 'next_status': 'all', 'next_due': 'today',
        })
        self.assertEqual(resp.status_code, 302)
        self.assertIn('status=all', resp['Location'])
        self.assertIn('due=today', resp['Location'])


class TodoToggleDeleteViewTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user('u', password='pw12345!')
        self.client.force_login(self.user)
        self.todo = Todo.objects.create(user=self.user, title='t')

    def test_toggle_marks_done_and_sets_completed_at(self):
        resp = self.client.post(reverse('todo_toggle', args=[self.todo.pk]))
        self.assertEqual(resp.status_code, 302)
        self.todo.refresh_from_db()
        self.assertTrue(self.todo.done)
        self.assertIsNotNone(self.todo.completed_at)

    def test_toggle_back_to_open_clears_completed_at(self):
        self.todo.done = True
        self.todo.completed_at = timezone.now()
        self.todo.save()
        self.client.post(reverse('todo_toggle', args=[self.todo.pk]))
        self.todo.refresh_from_db()
        self.assertFalse(self.todo.done)
        self.assertIsNone(self.todo.completed_at)

    def test_toggle_other_users_todo_404(self):
        other = User.objects.create_user('other', password='pw12345!')
        othertodo = Todo.objects.create(user=other, title='x')
        resp = self.client.post(reverse('todo_toggle', args=[othertodo.pk]))
        self.assertEqual(resp.status_code, 404)

    def test_delete_removes_todo(self):
        resp = self.client.post(reverse('todo_delete', args=[self.todo.pk]))
        self.assertEqual(resp.status_code, 302)
        self.assertFalse(Todo.objects.filter(pk=self.todo.pk).exists())


class TodoEditViewTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user('u', password='pw12345!')
        self.client.force_login(self.user)
        self.todo = Todo.objects.create(user=self.user, title='original')

    def test_get_renders_full_page(self):
        resp = self.client.get(reverse('todo_edit', args=[self.todo.pk]))
        self.assertEqual(resp.status_code, 200)
        self.assertTemplateUsed(resp, 'todos/edit.html')

    def test_get_modal_renders_partial(self):
        resp = self.client.get(reverse('todo_edit', args=[self.todo.pk]),
                               HTTP_X_REQUESTED_WITH='fetch')
        self.assertEqual(resp.status_code, 200)
        self.assertTemplateUsed(resp, 'todos/edit_partial.html')

    def test_post_valid_updates_and_redirects(self):
        resp = self.client.post(reverse('todo_edit', args=[self.todo.pk]), {'title': 'updated'})
        self.assertEqual(resp.status_code, 302)
        self.todo.refresh_from_db()
        self.assertEqual(self.todo.title, 'updated')
        # No project set -> falls back to catchall.
        self.assertTrue(self.todo.project.is_catchall)

    def test_post_valid_modal_returns_204(self):
        resp = self.client.post(reverse('todo_edit', args=[self.todo.pk]), {'title': 'updated'},
                                HTTP_X_REQUESTED_WITH='fetch')
        self.assertEqual(resp.status_code, 204)

    def test_post_invalid_returns_400_full(self):
        resp = self.client.post(reverse('todo_edit', args=[self.todo.pk]), {'title': ''})
        self.assertEqual(resp.status_code, 400)
        self.assertTemplateUsed(resp, 'todos/edit.html')

    def test_post_invalid_modal_returns_400_partial(self):
        resp = self.client.post(reverse('todo_edit', args=[self.todo.pk]), {'title': ''},
                                HTTP_X_REQUESTED_WITH='fetch')
        self.assertEqual(resp.status_code, 400)
        self.assertTemplateUsed(resp, 'todos/edit_partial.html')


class ProjectViewTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user('u', password='pw12345!')
        self.client.force_login(self.user)

    def test_add_valid(self):
        resp = self.client.post(reverse('project_add'), {'name': 'Fresh'})
        self.assertEqual(resp.status_code, 302)
        self.assertTrue(self.user.projects.filter(name='Fresh').exists())

    def test_add_sets_sort_order(self):
        Project.objects.create(user=self.user, name='Existing', sort_order=3)
        self.client.post(reverse('project_add'), {'name': 'Next'})
        self.assertEqual(self.user.projects.get(name='Next').sort_order, 4)

    def test_add_invalid_returns_400(self):
        resp = self.client.post(reverse('project_add'), {'name': ''})
        self.assertEqual(resp.status_code, 400)

    def test_edit_get_renders_partial(self):
        p = Project.objects.create(user=self.user, name='P')
        resp = self.client.get(reverse('project_edit', args=[p.pk]))
        self.assertEqual(resp.status_code, 200)
        self.assertTemplateUsed(resp, 'todos/project_edit_partial.html')

    def test_edit_post_valid_modal_returns_204(self):
        p = Project.objects.create(user=self.user, name='P')
        resp = self.client.post(reverse('project_edit', args=[p.pk]), {'name': 'Renamed'},
                                HTTP_X_REQUESTED_WITH='fetch')
        self.assertEqual(resp.status_code, 204)
        p.refresh_from_db()
        self.assertEqual(p.name, 'Renamed')

    def test_edit_post_valid_non_modal_redirects(self):
        p = Project.objects.create(user=self.user, name='P')
        resp = self.client.post(reverse('project_edit', args=[p.pk]), {'name': 'Renamed2'})
        self.assertEqual(resp.status_code, 302)

    def test_edit_post_invalid_modal_returns_400(self):
        Project.objects.create(user=self.user, name='Taken')
        p = Project.objects.create(user=self.user, name='Mine')
        resp = self.client.post(reverse('project_edit', args=[p.pk]), {'name': 'Taken'},
                                HTTP_X_REQUESTED_WITH='fetch')
        self.assertEqual(resp.status_code, 400)

    def test_edit_post_invalid_non_modal_redirects(self):
        Project.objects.create(user=self.user, name='Taken')
        p = Project.objects.create(user=self.user, name='Mine')
        resp = self.client.post(reverse('project_edit', args=[p.pk]), {'name': 'Taken'})
        self.assertEqual(resp.status_code, 302)


class ProjectReorderViewTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user('u', password='pw12345!')
        self.client.force_login(self.user)
        self.p1 = Project.objects.create(user=self.user, name='One', sort_order=0)
        self.p2 = Project.objects.create(user=self.user, name='Two', sort_order=1)

    def test_valid_reorder(self):
        resp = self.client.post(reverse('project_reorder'),
                                {'order': [str(self.p2.pk), str(self.p1.pk)]})
        self.assertEqual(resp.status_code, 204)
        self.p1.refresh_from_db()
        self.p2.refresh_from_db()
        self.assertEqual(self.p2.sort_order, 0)
        self.assertEqual(self.p1.sort_order, 1)

    def test_non_integer_id_bad_request(self):
        resp = self.client.post(reverse('project_reorder'), {'order': ['abc']})
        self.assertEqual(resp.status_code, 400)

    def test_mismatched_ids_bad_request(self):
        resp = self.client.post(reverse('project_reorder'), {'order': [str(self.p1.pk)]})
        self.assertEqual(resp.status_code, 400)


class RecurringViewTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user('u', password='pw12345!')
        self.client.force_login(self.user)

    def test_list_get(self):
        resp = self.client.get(reverse('recurring_list'))
        self.assertEqual(resp.status_code, 200)
        self.assertTemplateUsed(resp, 'todos/recurring_list.html')

    def test_list_post_creates_template(self):
        resp = self.client.post(reverse('recurring_list'), {'title': 'Weekly', 'day_of_week': 6})
        self.assertRedirects(resp, reverse('recurring_list'))
        tpl = RecurringTodo.objects.get(title='Weekly')
        self.assertTrue(tpl.project.is_catchall)

    def test_list_post_with_project(self):
        proj = Project.objects.create(user=self.user, name='Work')
        resp = self.client.post(reverse('recurring_list'),
                                {'title': 'W', 'day_of_week': 6, 'project': proj.pk})
        self.assertRedirects(resp, reverse('recurring_list'))
        self.assertEqual(RecurringTodo.objects.get(title='W').project, proj)

    def test_edit_get(self):
        tpl = RecurringTodo.objects.create(user=self.user, title='T', day_of_week=6)
        resp = self.client.get(reverse('recurring_edit', args=[tpl.pk]))
        self.assertEqual(resp.status_code, 200)
        self.assertTemplateUsed(resp, 'todos/recurring_edit.html')

    def test_edit_post_valid(self):
        tpl = RecurringTodo.objects.create(user=self.user, title='T', day_of_week=6)
        resp = self.client.post(reverse('recurring_edit', args=[tpl.pk]),
                                {'title': 'Renamed', 'day_of_week': 1})
        self.assertRedirects(resp, reverse('recurring_list'))
        tpl.refresh_from_db()
        self.assertEqual(tpl.title, 'Renamed')
        self.assertEqual(tpl.day_of_week, 1)

    def test_edit_post_invalid_returns_400(self):
        tpl = RecurringTodo.objects.create(user=self.user, title='T', day_of_week=6)
        resp = self.client.post(reverse('recurring_edit', args=[tpl.pk]),
                                {'title': '', 'day_of_week': 1})
        self.assertEqual(resp.status_code, 400)

    def test_delete(self):
        tpl = RecurringTodo.objects.create(user=self.user, title='T', day_of_week=6)
        resp = self.client.post(reverse('recurring_delete', args=[tpl.pk]))
        self.assertRedirects(resp, reverse('recurring_list'))
        self.assertFalse(RecurringTodo.objects.filter(pk=tpl.pk).exists())
