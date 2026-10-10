from django.contrib import admin
from .models import LSCourse, LSLesson, LSEnrollment, LSProgress, LSVoucher


class LSLessonInline(admin.TabularInline):
    model = LSLesson
    extra = 1


@admin.register(LSCourse)
class LSCourseAdmin(admin.ModelAdmin):
    list_display = ['title', 'category', 'instructor', 'lesson_count', 'enrolled_count']
    list_filter = ['category']
    search_fields = ['title', 'description']
    inlines = [LSLessonInline]


@admin.register(LSEnrollment)
class LSEnrollmentAdmin(admin.ModelAdmin):
    list_display = ['user', 'course', 'enrolled_at']
    list_filter = ['course']


@admin.register(LSProgress)
class LSProgressAdmin(admin.ModelAdmin):
    list_display = ['user', 'lesson', 'completed_at']


@admin.register(LSVoucher)
class LSVoucherAdmin(admin.ModelAdmin):
    list_display = ['user', 'course', 'brand', 'discount', 'code']
