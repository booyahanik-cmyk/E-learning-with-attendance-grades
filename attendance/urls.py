from django.contrib.auth.views import LogoutView
from django.urls import path

from . import views

urlpatterns = [
    path('', views.RoleLoginView.as_view(), name='login'),
    path('register/', views.register, name='register'),
    path('logout/', LogoutView.as_view(), name='logout'),  # POST only, per Django 5+
    path('me/', views.student_home, name='student_home'),
    path('dashboard/', views.faculty_dashboard, name='faculty_dashboard'),
    path('attendance/', views.attendance_register, name='attendance_register'),
    path('reports/', views.reports, name='reports'),
    path('reports/export/', views.reports_export, name='reports_export'),
]
