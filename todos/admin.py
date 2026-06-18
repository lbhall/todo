from django.contrib import admin

from .models import Project, Tag, Todo


@admin.register(Project)
class ProjectAdmin(admin.ModelAdmin):
    list_display = ('id', 'user', 'name', 'created_at')
    list_filter = ('user',)
    search_fields = ('name',)


@admin.register(Tag)
class TagAdmin(admin.ModelAdmin):
    list_display = ('id', 'user', 'name', 'created_at')
    list_filter = ('user',)
    search_fields = ('name',)


@admin.register(Todo)
class TodoAdmin(admin.ModelAdmin):
    list_display = ('id', 'user', 'project', 'title', 'done', 'created_at')
    list_filter = ('done', 'user', 'project', 'tags')
    search_fields = ('title',)
    filter_horizontal = ('tags',)
