from django.urls import path
from . import views

urlpatterns = [
    path('', views.student_grades, name='student_grades'),
    path('manage/', views.faculty_grades, name='faculty_grades'),
    path('save-marks/', views.save_student_marks, name='save_student_marks'),
    path('api/sem/<int:sem_id>/', views.api_semester_grades, name='api_semester_grades'),
]
