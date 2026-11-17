from django.contrib import admin
from django.contrib.auth.admin import UserAdmin as BaseUserAdmin

from .models import (
    User, Course, ClassSession, Attendance, AttendanceCorrectionBatch,
    AttendanceCorrectionRequest, AttendanceAuditLog, StudentNotification,
    AttendanceCorrectionWindowExtension
)

COLLEGE_FIELDS = ('College details', {'fields': ('role', 'roll_number', 'employee_id')})


@admin.register(User)
class UserAdmin(BaseUserAdmin):
    fieldsets = BaseUserAdmin.fieldsets + (COLLEGE_FIELDS,)
    add_fieldsets = BaseUserAdmin.add_fieldsets + (COLLEGE_FIELDS,)
    list_display = ('username', 'first_name', 'last_name', 'email', 'role', 'roll_number', 'employee_id', 'is_staff')
    list_filter = BaseUserAdmin.list_filter + ('role',)
    search_fields = ('username', 'first_name', 'last_name', 'email', 'roll_number', 'employee_id')


@admin.register(Course)
class CourseAdmin(admin.ModelAdmin):
    list_display = ('code', 'name', 'faculty')
    search_fields = ('code', 'name')
    filter_horizontal = ('students',)


@admin.register(ClassSession)
class ClassSessionAdmin(admin.ModelAdmin):
    list_display = ('course', 'date', 'session_identifier', 'is_published', 'created_at')
    list_filter = ('is_published', 'course', 'date')
    search_fields = ('course__code', 'session_identifier')
    date_hierarchy = 'date'


@admin.register(Attendance)
class AttendanceAdmin(admin.ModelAdmin):
    list_display = ('date', 'session', 'course', 'student', 'status', 'marked_by', 'updated_at')
    list_filter = ('status', 'course', 'date')
    search_fields = ('student__username', 'student__roll_number')
    date_hierarchy = 'date'


@admin.register(AttendanceCorrectionBatch)
class AttendanceCorrectionBatchAdmin(admin.ModelAdmin):
    list_display = ('batch_id', 'teacher', 'get_teacher_email', 'status', 'delivery_attempts', 'email_sent_at', 'created_at')
    list_filter = ('status', 'is_revoked', 'created_at')
    search_fields = ('teacher__username', 'teacher__email', 'batch_id', 'last_error')

    def get_teacher_email(self, obj):
        return obj.teacher.email or "—"
    get_teacher_email.short_description = "Teacher Email"


@admin.register(AttendanceCorrectionRequest)
class AttendanceCorrectionRequestAdmin(admin.ModelAdmin):
    list_display = ('student', 'course', 'session', 'original_status', 'requested_status', 'status', 'teacher', 'reviewed_at', 'created_at')
    list_filter = ('status', 'course', 'requested_status')
    search_fields = ('student__username', 'student__roll_number', 'course__code', 'reason')


@admin.register(AttendanceAuditLog)
class AttendanceAuditLogAdmin(admin.ModelAdmin):
    list_display = ('timestamp', 'student', 'course', 'session', 'previous_status', 'new_status', 'changed_by', 'access_method')
    list_filter = ('new_status', 'access_method', 'course')
    search_fields = ('student__username', 'changed_by__username', 'decision_reason')
    readonly_fields = ('attendance', 'student', 'session', 'course', 'previous_status', 'new_status', 'changed_by', 'decision_reason', 'access_method', 'correction_request', 'timestamp')


@admin.register(StudentNotification)
class StudentNotificationAdmin(admin.ModelAdmin):
    list_display = ('student', 'get_student_email', 'correction_request', 'email_status', 'email_delivery_attempts', 'email_sent_at', 'is_read', 'created_at')
    list_filter = ('email_status', 'is_read', 'created_at')
    search_fields = ('student__username', 'student__email', 'message', 'email_last_error')

    def get_student_email(self, obj):
        return obj.student.email or "—"
    get_student_email.short_description = "Student Email"


@admin.register(AttendanceCorrectionWindowExtension)
class AttendanceCorrectionWindowExtensionAdmin(admin.ModelAdmin):
    list_display = ('student', 'course', 'session', 'extended_until', 'created_by', 'reason')
    list_filter = ('extended_until',)
    search_fields = ('student__username', 'course__code', 'reason')
