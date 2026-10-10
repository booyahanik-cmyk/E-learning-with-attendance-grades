import random
import string

from django.conf import settings
from django.db import models


class LSCourse(models.Model):
    """A learning course on the LearnSphere platform."""
    title = models.CharField(max_length=200)
    category = models.CharField(max_length=50, default='General')
    icon = models.CharField(max_length=10, default='')
    description = models.TextField(blank=True)
    is_published = models.BooleanField(default=True)
    instructor = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='ls_courses_created',
    )
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-id']

    def __str__(self):
        return self.title

    def lesson_count(self):
        return self.lessons.count()

    def enrolled_count(self):
        return self.enrollments.count()


class LSLesson(models.Model):
    """A lesson within a LearnSphere course."""
    course = models.ForeignKey(LSCourse, on_delete=models.CASCADE, related_name='lessons')
    title = models.CharField(max_length=200)
    content = models.TextField(blank=True)
    position = models.PositiveIntegerField(default=1)

    class Meta:
        ordering = ['position']

    def __str__(self):
        return f"{self.position}. {self.title}"


class LSEnrollment(models.Model):
    """Tracks which users are enrolled in which courses."""
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='ls_enrollments',
    )
    course = models.ForeignKey(LSCourse, on_delete=models.CASCADE, related_name='enrollments')
    enrolled_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        constraints = [
            models.UniqueConstraint(fields=['user', 'course'], name='unique_ls_enrollment'),
        ]

    def __str__(self):
        return f"{self.user.username} -> {self.course.title}"


class LSProgress(models.Model):
    """Tracks completed lessons for a user."""
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='ls_progress',
    )
    lesson = models.ForeignKey(LSLesson, on_delete=models.CASCADE, related_name='completions')
    completed_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        constraints = [
            models.UniqueConstraint(fields=['user', 'lesson'], name='unique_ls_progress'),
        ]

    def __str__(self):
        return f"{self.user.username} completed {self.lesson.title}"


class LSVoucher(models.Model):
    """Reward voucher awarded on course completion."""
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='ls_vouchers',
    )
    course = models.ForeignKey(LSCourse, on_delete=models.CASCADE, related_name='vouchers')
    brand = models.CharField(max_length=50)
    discount = models.CharField(max_length=50)
    code = models.CharField(max_length=30)

    class Meta:
        constraints = [
            models.UniqueConstraint(fields=['user', 'course'], name='unique_ls_voucher'),
        ]

    def __str__(self):
        return f"{self.brand} {self.discount} - {self.code}"

    @classmethod
    def generate_for_user(cls, user, course):
        """Create a random reward voucher if none exists."""
        PARTNERS = [
            ("Flipkart", "10% OFF"),
            ("Amazon", "5% OFF"),
            ("Swiggy", "15% OFF"),
            ("Myntra", "10% OFF"),
            ("Zomato", "20% OFF"),
        ]
        if cls.objects.filter(user=user, course=course).exists():
            return cls.objects.get(user=user, course=course)
        brand, disc = random.choice(PARTNERS)
        code = brand[:3].upper() + ''.join(random.choices(string.ascii_uppercase + string.digits, k=6))
        return cls.objects.create(user=user, course=course, brand=brand, discount=disc, code=code)
