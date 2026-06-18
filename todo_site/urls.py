from django.contrib import admin
from django.urls import include, path

from todos import views as todo_views

urlpatterns = [
    path('admin/', admin.site.urls),
    path('accounts/signup/', todo_views.signup, name='signup'),
    path('accounts/', include('django.contrib.auth.urls')),
    path('', include('todos.urls')),
]
