from urllib.parse import urlencode

from django.contrib.auth import login
from django.contrib.auth.decorators import login_required
from django.db import transaction
from django.db.models import Max
from django.http import HttpResponse, HttpResponseBadRequest
from django.shortcuts import get_object_or_404, redirect, render
from django.utils import timezone
from django.views.decorators.http import require_POST

from .forms import ProjectForm, SignUpForm, TodoForm
from .models import Project, Tag, Todo


def _get_or_create_catchall(user):
    catchall = user.projects.filter(is_catchall=True).first()
    if catchall is not None:
        return catchall
    current_max = user.projects.aggregate(m=Max('sort_order'))['m']
    return Project.objects.create(
        user=user,
        name='Other',
        is_catchall=True,
        sort_order=(current_max + 1) if current_max is not None else 0,
    )


def signup(request):
    if request.user.is_authenticated:
        return redirect('todo_list')
    if request.method == 'POST':
        form = SignUpForm(request.POST)
        if form.is_valid():
            user = form.save()
            _get_or_create_catchall(user)
            login(request, user)
            return redirect('todo_list')
    else:
        form = SignUpForm()
    return render(request, 'registration/signup.html', {'form': form})


def _active_tag(request):
    raw = (request.GET.get('tag') or '').strip()
    if not raw:
        return None
    return Tag.objects.filter(user=request.user, name__iexact=raw).first()


STATUS_CHOICES = ('open', 'done')


def _active_status(request):
    raw = request.GET.get('status')
    if raw is None:
        return 'open'  # default view: open todos only
    raw = raw.strip().lower()
    if raw == 'all':
        return None
    return raw if raw in STATUS_CHOICES else 'open'


DUE_CHOICES = ('today', 'future', 'past')


def _active_due(request):
    raw = (request.GET.get('due') or '').strip().lower()
    return raw if raw in DUE_CHOICES else None


def _list_context(request, *, todo_form=None, project_form=None):
    _get_or_create_catchall(request.user)  # idempotent; protects against admin deletion
    active_tag = _active_tag(request)
    active_status = _active_status(request)
    active_due = _active_due(request)
    today = timezone.localdate()
    todos = list(request.user.todos.select_related('project').prefetch_related('tags'))
    filtered = todos
    if active_tag is not None:
        filtered = [t for t in filtered if active_tag in t.tags.all()]
    if active_status == 'open':
        filtered = [t for t in filtered if not t.done]
    elif active_status == 'done':
        filtered = [t for t in filtered if t.done]
    if active_due == 'today':
        filtered = [t for t in filtered if t.due_date == today]
    elif active_due == 'future':
        filtered = [t for t in filtered if t.due_date and t.due_date > today]
    elif active_due == 'past':
        filtered = [t for t in filtered if t.due_date and t.due_date < today]
    by_project_id = {}
    for t in filtered:
        by_project_id.setdefault(t.project_id, []).append(t)
    groups = [
        {'project': p, 'todos': by_project_id.get(p.pk, [])}
        for p in request.user.projects.all()
    ]
    used_tags = Tag.objects.filter(user=request.user, todos__isnull=False).distinct().order_by('name')
    return {
        'groups': groups,
        'used_tags': used_tags,
        'active_tag': active_tag,
        'active_status': active_status,
        'active_due': active_due,
        'todo_form': todo_form if todo_form is not None else TodoForm(user=request.user),
        'project_form': project_form if project_form is not None else ProjectForm(user=request.user),
    }


@login_required
def todo_list(request):
    return render(request, 'todos/list.html', _list_context(request))


def _list_qs(request):
    """Preserve tag + status + due across redirects."""
    params = {}
    tag = request.POST.get('next_tag') or request.GET.get('tag')
    status = request.POST.get('next_status') or request.GET.get('status')
    due = request.POST.get('next_due') or request.GET.get('due')
    if tag:
        params['tag'] = tag
    if status in STATUS_CHOICES or status == 'all':
        params['status'] = status
    if due in DUE_CHOICES:
        params['due'] = due
    return ('?' + urlencode(params)) if params else ''


def _redirect_to_list(request):
    return redirect('/' + _list_qs(request))


@login_required
@require_POST
def todo_add(request):
    form = TodoForm(request.POST, user=request.user)
    if form.is_valid():
        todo = form.save(commit=False)
        todo.user = request.user
        if todo.project is None:
            todo.project = _get_or_create_catchall(request.user)
        todo.save()
        form.apply_tags(todo, request.user)
        return _redirect_to_list(request)
    return render(request, 'todos/list.html', _list_context(request, todo_form=form), status=400)


@login_required
@require_POST
def todo_toggle(request, pk):
    todo = get_object_or_404(Todo, pk=pk, user=request.user)
    todo.done = not todo.done
    todo.completed_at = timezone.now() if todo.done else None
    todo.save(update_fields=['done', 'completed_at', 'updated_at'])
    return _redirect_to_list(request)


@login_required
@require_POST
def todo_delete(request, pk):
    todo = get_object_or_404(Todo, pk=pk, user=request.user)
    todo.delete()
    return _redirect_to_list(request)


def _is_modal_request(request):
    return request.headers.get('X-Requested-With') == 'fetch'


@login_required
def todo_edit(request, pk):
    todo = get_object_or_404(Todo, pk=pk, user=request.user)
    is_modal = _is_modal_request(request)
    if request.method == 'POST':
        form = TodoForm(request.POST, instance=todo, user=request.user)
        if form.is_valid():
            saved = form.save(commit=False)
            if saved.project is None:
                saved.project = _get_or_create_catchall(request.user)
            saved.save()
            form.apply_tags(saved, request.user)
            if is_modal:
                return HttpResponse(status=204)
            return _redirect_to_list(request)
        # form invalid: re-render with errors
        template = 'todos/edit_partial.html' if is_modal else 'todos/edit.html'
        ctx = {'form': form, 'todo': todo}
        if not is_modal:
            ctx['list_qs'] = _list_qs(request)
        return render(request, template, ctx, status=400)
    form = TodoForm(instance=todo, user=request.user)
    if is_modal:
        return render(request, 'todos/edit_partial.html', {'form': form, 'todo': todo})
    return render(request, 'todos/edit.html', {'form': form, 'todo': todo, 'list_qs': _list_qs(request)})


@login_required
@require_POST
def project_add(request):
    form = ProjectForm(request.POST, user=request.user)
    if form.is_valid():
        project = form.save(commit=False)
        project.user = request.user
        current_max = request.user.projects.aggregate(m=Max('sort_order'))['m']
        project.sort_order = (current_max + 1) if current_max is not None else 0
        project.save()
        return _redirect_to_list(request)
    return render(request, 'todos/list.html', _list_context(request, project_form=form), status=400)


@login_required
@require_POST
def project_reorder(request):
    raw_ids = request.POST.getlist('order')
    try:
        requested_ids = [int(x) for x in raw_ids]
    except (TypeError, ValueError):
        return HttpResponseBadRequest('Non-integer id in order')
    user_ids = set(request.user.projects.values_list('id', flat=True))
    if set(requested_ids) != user_ids or len(requested_ids) != len(user_ids):
        return HttpResponseBadRequest('Submitted ids do not match user projects')
    with transaction.atomic():
        for i, pk in enumerate(requested_ids):
            request.user.projects.filter(pk=pk).update(sort_order=i)
    return HttpResponse(status=204)
