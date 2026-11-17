from django.contrib.auth.views import LogoutView
from django.urls import path

from . import views

urlpatterns = [
    path('', views.RoleLoginView.as_view(), name='login'),
    path('register/', views.register, name='register'),
    path('logout/', LogoutView.as_view(), name='logout'),  # POST only
    path('me/', views.student_home, name='student_home'),
    path('dashboard/', views.faculty_dashboard, name='faculty_dashboard'),
    path('attendance/', views.attendance_register, name='attendance_register'),
    path('reports/', views.reports, name='reports'),
    path('reports/export/', views.reports_export, name='reports_export'),

    # Attendance Correction System URLs
    path('corrections/request/', views.request_correction, name='request_correction'),
    path('corrections/my/', views.my_correction_requests, name='my_correction_requests'),
    path('corrections/cancel/<int:request_id>/', views.cancel_correction_request, name='cancel_correction_request'),
    path('corrections/', views.faculty_corrections_inbox, name='faculty_corrections'),
    path('review/', views.review_corrections, name='review_corrections'),
    path('review/approve/<int:request_id>/', views.approve_correction_request, name='approve_correction_request'),
    path('review/reject/<int:request_id>/', views.reject_correction_request, name='reject_correction_request'),
    path('api/student-report/<int:student_id>/<int:course_id>/', views.api_student_attendance_report, name='api_student_attendance_report'),

    # Compatibility routes for already-sent links and legacy prefixes
    path('attendance/review/', views.review_corrections, name='review_corrections_compat'),
    path('attendance/review/approve/<int:request_id>/', views.approve_correction_request, name='approve_correction_request_compat'),
    path('attendance/review/reject/<int:request_id>/', views.reject_correction_request, name='reject_correction_request_compat'),
    path('attendance/api/student-report/<int:student_id>/<int:course_id>/', views.api_student_attendance_report, name='api_student_attendance_report_compat'),
]
