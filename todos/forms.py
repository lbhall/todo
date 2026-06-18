from django import forms
from django.contrib.auth.forms import UserCreationForm

from .models import Project, Tag, Todo


class SignUpForm(UserCreationForm):
    pass


def _split_tag_text(text: str) -> list[str]:
    seen = []
    seen_ci = set()
    for raw in (text or '').split(','):
        name = raw.strip()
        if not name:
            continue
        key = name.lower()
        if key in seen_ci:
            continue
        seen_ci.add(key)
        seen.append(name)
    return seen


class TodoForm(forms.ModelForm):
    tags_text = forms.CharField(
        required=False,
        label='Tags',
        widget=forms.TextInput(attrs={'placeholder': 'tags (comma-separated)'}),
    )

    class Meta:
        model = Todo
        fields = ['title', 'project']
        widgets = {
            'title': forms.TextInput(attrs={'placeholder': 'What needs doing?', 'autofocus': True}),
        }

    def __init__(self, *args, user=None, **kwargs):
        super().__init__(*args, **kwargs)
        self._user = user
        if user is not None:
            self.fields['project'].queryset = user.projects.all()
        self.fields['project'].required = False
        self.fields['project'].empty_label = '— no project —'
        if self.instance and self.instance.pk and not self.is_bound:
            self.fields['tags_text'].initial = ', '.join(
                self.instance.tags.values_list('name', flat=True)
            )

    def apply_tags(self, todo, user):
        names = _split_tag_text(self.cleaned_data.get('tags_text', ''))
        tag_objs = []
        for name in names:
            tag = Tag.objects.filter(user=user, name__iexact=name).first()
            if tag is None:
                tag = Tag.objects.create(user=user, name=name)
            tag_objs.append(tag)
        todo.tags.set(tag_objs)


class ProjectForm(forms.ModelForm):
    class Meta:
        model = Project
        fields = ['name']
        widgets = {
            'name': forms.TextInput(attrs={'placeholder': 'New project name'}),
        }

    def __init__(self, *args, user=None, **kwargs):
        super().__init__(*args, **kwargs)
        self._user = user

    def clean_name(self):
        name = self.cleaned_data['name'].strip()
        if not name:
            raise forms.ValidationError('Name cannot be blank.')
        if self._user is not None and self._user.projects.filter(name__iexact=name).exists():
            raise forms.ValidationError(f'You already have a project named "{name}".')
        return name
