from django.urls import path

from . import views

urlpatterns = [
    path('', views.todo_list, name='todo_list'),
    path('add/', views.todo_add, name='todo_add'),
    path('edit/<int:pk>/', views.todo_edit, name='todo_edit'),
    path('toggle/<int:pk>/', views.todo_toggle, name='todo_toggle'),
    path('delete/<int:pk>/', views.todo_delete, name='todo_delete'),
    path('projects/add/', views.project_add, name='project_add'),
]
