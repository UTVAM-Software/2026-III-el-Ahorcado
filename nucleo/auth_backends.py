import bcrypt

from django.contrib.auth import get_user_model
from django.contrib.auth.backends import ModelBackend
from django.db.models import Q

from .auth_integration import sync_player_to_django_user
from .models import Player


class PlayerAuthBackend(ModelBackend):
    """Accept the same username/email and bcrypt password used by the main site."""

    def authenticate(self, request, username=None, password=None, **kwargs):
        credential = username or kwargs.get('email')
        if not credential or not password:
            return None
        player = Player.objects.select_related('django_user').filter(
            Q(name=credential) | Q(email__iexact=credential)
        ).first()
        if player is None:
            return None
        if not player.is_active:
            return None

        user = player.django_user if player.django_user_id else None
        if user and not user.is_active:
            return None

        player_password_valid = False
        try:
            if player.password.startswith('$2'):
                player_password_valid = bcrypt.checkpw(password.encode(), player.password.encode())
            else:
                # Legacy unhashed credentials are upgraded as soon as they log in.
                player_password_valid = password == player.password
        except (ValueError, TypeError, UnicodeEncodeError):
            player_password_valid = False

        django_password_valid = bool(user and user.check_password(password))
        if not player_password_valid and not django_password_valid:
            return None

        user = sync_player_to_django_user(player, raw_password=password)
        return user if self.user_can_authenticate(user) else None

    def get_user(self, user_id):
        User = get_user_model()
        try:
            return User.objects.get(pk=user_id, is_active=True)
        except User.DoesNotExist:
            return None
