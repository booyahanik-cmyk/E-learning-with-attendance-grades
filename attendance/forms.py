from django.contrib.auth.forms import UserCreationForm
from django.core.exceptions import ValidationError

from .models import User


class StudentRegistrationForm(UserCreationForm):
    """
    Public sign-up, students only.

    Reuses Django's UserCreationForm for the password1/password2 pair, the
    "passwords don't match" check, AUTH_PASSWORD_VALIDATORS and hashing on save.

    The roll number doubles as the College ID (``username``), which is what the
    login page asks for -- a student has one identifier, so we don't ask twice.
    ``role`` is never read from the POST: it is set here, server-side, so the
    public form cannot mint faculty or admin accounts.
    """

    class Meta(UserCreationForm.Meta):
        model = User
        fields = ('roll_number', 'email')

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        # The frontend marks these required in HTML; enforce it server-side too.
        self.fields['roll_number'].required = True
        self.fields['email'].required = True

    def clean_roll_number(self):
        """Reject a roll number already taken as a College ID (case-insensitively).
        Duplicate *roll numbers* are caught separately by the model's unique=True."""
        roll = self.cleaned_data['roll_number']
        if User.objects.filter(username__iexact=roll).exists():
            raise ValidationError('An account with that College ID already exists.')
        return roll

    def save(self, commit=True):
        user = super().save(commit=False)
        user.username = user.roll_number
        user.role = User.Role.STUDENT
        if commit:
            user.save()
        return user
