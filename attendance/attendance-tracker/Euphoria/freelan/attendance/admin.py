from django.contrib import admin
from django.contrib.auth.admin import UserAdmin as BaseUserAdmin

from .models import Attendance, Course, User

# Reuse Django's UserAdmin so password hashing, permissions and the
# add-user flow keep working; just append our college fields.
COLLEGE_FIELDS = ('College details', {'fields': ('role', 'roll_number', 'employee_id')})


@admin.register(User)
class UserAdmin(BaseUserAdmin):
    fieldsets = BaseUserAdmin.fieldsets + (COLLEGE_FIELDS,)
    add_fieldsets = BaseUserAdmin.add_fieldsets + (COLLEGE_FIELDS,)
    list_display = ('username', 'first_name', 'last_name', 'role', 'roll_number', 'employee_id', 'is_staff')
    list_filter = BaseUserAdmin.list_filter + ('role',)
    search_fields = ('username', 'first_name', 'last_name', 'email', 'roll_number', 'employee_id')


@admin.register(Course)
class CourseAdmin(admin.ModelAdmin):
    list_display = ('code', 'name', 'faculty')
    search_fields = ('code', 'name')
    filter_horizontal = ('students',)  # usable enrolment picker


@admin.register(Attendance)
class AttendanceAdmin(admin.ModelAdmin):
    list_display = ('date', 'course', 'student', 'status', 'marked_by', 'created_at')
    list_filter = ('status', 'course', 'date')
    search_fields = ('student__username', 'student__roll_number')
    date_hierarchy = 'date'
