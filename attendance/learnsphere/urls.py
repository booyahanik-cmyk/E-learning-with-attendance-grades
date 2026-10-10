from django.urls import path
from . import views

urlpatterns = [
    path('', views.course_catalog, name='ls_catalog'),
    path('course/<int:course_id>/', views.course_detail, name='ls_course_detail'),
    path('enroll/<int:course_id>/', views.enroll, name='ls_enroll'),
    path('complete/<int:lesson_id>/', views.complete_lesson, name='ls_complete_lesson'),
    path('my-learning/', views.my_learning, name='ls_my_learning'),
    path('add/', views.add_course, name='ls_add_course'),
    path('delete/<int:course_id>/', views.delete_course, name='ls_delete_course'),
    path('edit/<int:course_id>/', views.edit_course, name='ls_edit_course'),
    path('manage-lectures/<int:course_id>/', views.manage_lectures, name='ls_manage_lectures'),
    path('toggle-publish/<int:course_id>/', views.toggle_publish, name='ls_toggle_publish'),
]
