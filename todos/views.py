from urllib.parse import urlencode

from django.contrib.auth import login
from django.contrib.auth.decorators import login_required
from django.shortcuts import get_object_or_404, redirect, render
from django.views.decorators.http import require_POST

from .forms import ProjectForm, SignUpForm, TodoForm
from .models import Project, Tag, Todo


def signup(request):
    if request.user.is_authenticated:
        return redirect('todo_list')
    if request.method == 'POST':
        form = SignUpForm(request.POST)
        if form.is_valid():
            user = form.save()
            login(request, user)
            return redirect('todo_list')
    else:
        form = SignUpForm()
    return render(request, 'registration/signup.html', {'form': form})


def _active_project(request):
    raw = request.GET.get('project')
    if not raw or raw == 'all':
        return None
    return get_object_or_404(Project, pk=raw, user=request.user)


def _active_tag(request):
    raw = (request.GET.get('tag') or '').strip()
    if not raw:
        return None
    return Tag.objects.filter(user=request.user, name__iexact=raw).first()


@login_required
def todo_list(request):
    active_project = _active_project(request)
    active_tag = _active_tag(request)
    todos = request.user.todos.select_related('project').prefetch_related('tags')
    if active_project is not None:
        todos = todos.filter(project=active_project)
    if active_tag is not None:
        todos = todos.filter(tags=active_tag)
    todo_form = TodoForm(user=request.user, initial={'project': active_project} if active_project else None)
    project_form = ProjectForm(user=request.user)
    used_tags = Tag.objects.filter(user=request.user, todos__isnull=False).distinct().order_by('name')
    return render(request, 'todos/list.html', {
        'todos': todos,
        'projects': request.user.projects.all(),
        'used_tags': used_tags,
        'active_project': active_project,
        'active_tag': active_tag,
        'todo_form': todo_form,
        'project_form': project_form,
    })


def _list_qs(request):
    """Preserve project + tag across redirects."""
    params = {}
    project = request.POST.get('next_project') or request.GET.get('project')
    tag = request.POST.get('next_tag') or request.GET.get('tag')
    if project and project != 'all':
        params['project'] = project
    if tag:
        params['tag'] = tag
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
        todo.save()
        form.apply_tags(todo, request.user)
        return _redirect_to_list(request)
    todos = request.user.todos.select_related('project').prefetch_related('tags')
    used_tags = Tag.objects.filter(user=request.user, todos__isnull=False).distinct().order_by('name')
    return render(request, 'todos/list.html', {
        'todos': todos,
        'projects': request.user.projects.all(),
        'used_tags': used_tags,
        'active_project': None,
        'active_tag': None,
        'todo_form': form,
        'project_form': ProjectForm(user=request.user),
    }, status=400)


@login_required
@require_POST
def todo_toggle(request, pk):
    todo = get_object_or_404(Todo, pk=pk, user=request.user)
    todo.done = not todo.done
    todo.save(update_fields=['done'])
    return _redirect_to_list(request)


@login_required
@require_POST
def todo_delete(request, pk):
    todo = get_object_or_404(Todo, pk=pk, user=request.user)
    todo.delete()
    return _redirect_to_list(request)


@login_required
def todo_edit(request, pk):
    todo = get_object_or_404(Todo, pk=pk, user=request.user)
    if request.method == 'POST':
        form = TodoForm(request.POST, instance=todo, user=request.user)
        if form.is_valid():
            saved = form.save()
            form.apply_tags(saved, request.user)
            return _redirect_to_list(request)
    else:
        form = TodoForm(instance=todo, user=request.user)
    return render(request, 'todos/edit.html', {'form': form, 'todo': todo, 'list_qs': _list_qs(request)})


@login_required
@require_POST
def project_add(request):
    form = ProjectForm(request.POST, user=request.user)
    if form.is_valid():
        project = form.save(commit=False)
        project.user = request.user
        project.save()
        return redirect(f"/?project={project.pk}")
    todos = request.user.todos.select_related('project').prefetch_related('tags')
    used_tags = Tag.objects.filter(user=request.user, todos__isnull=False).distinct().order_by('name')
    return render(request, 'todos/list.html', {
        'todos': todos,
        'projects': request.user.projects.all(),
        'used_tags': used_tags,
        'active_project': None,
        'active_tag': None,
        'todo_form': TodoForm(user=request.user),
        'project_form': form,
    }, status=400)
