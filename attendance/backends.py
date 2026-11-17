from django.contrib.auth import get_user_model
from django.contrib.auth.backends import ModelBackend
from django.db.models import Q


class EmailOrUsernameModelBackend(ModelBackend):
    """
    Allows authentication with username, roll number, or registered email address.
    Preserves all standard Django permissions and authorization checks.
    """

    def authenticate(self, request, username=None, password=None, **kwargs):
        user_model = get_user_model()
        if username is None:
            username = kwargs.get(user_model.USERNAME_FIELD)

        if not username or not password:
            return None

        clean_identifier = username.strip()
        try:
            user = user_model.objects.filter(
                Q(username__iexact=clean_identifier) |
                Q(email__iexact=clean_identifier) |
                Q(roll_number__iexact=clean_identifier)
            ).first()

            if user and user.check_password(password) and self.user_can_authenticate(user):
                return user
        except Exception:
            return None

        return None

