from django.contrib import admin
from .models import Semester, Subject, GradeRecord


@admin.register(Semester)
class SemesterAdmin(admin.ModelAdmin):
    list_display = ('number', 'name', 'stamp_text')
    ordering = ('number',)


@admin.register(Subject)
class SubjectAdmin(admin.ModelAdmin):
    list_display = ('code', 'name', 'credits', 'course')
    search_fields = ('code', 'name')
    list_filter = ('credits',)


@admin.register(GradeRecord)
class GradeRecordAdmin(admin.ModelAdmin):
    list_display = ('student', 'semester', 'subject', 'internal_marks', 'external_marks', 'total_marks', 'grade', 'grade_point')
    list_filter = ('semester', 'grade', 'subject')
    search_fields = ('student__username', 'student__roll_number', 'subject__code', 'subject__name')
