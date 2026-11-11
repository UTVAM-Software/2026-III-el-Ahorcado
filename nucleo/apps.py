import logging

from django.apps import AppConfig
from django.contrib.auth.signals import user_login_failed
from django.db.models.signals import post_migrate

logger = logging.getLogger('nucleo.auth')


def _ensure_role_groups(sender, **kwargs):
    from .auth_integration import ensure_role_groups

    ensure_role_groups()


def _log_failed_login(sender, credentials, request=None, **kwargs):
    """Record why a management login failed, without logging the password."""
    from django.contrib.auth import get_user_model

    from .models import find_player_by_credential

    username = str(credentials.get('username') or '')
    user = get_user_model().objects.filter(username__iexact=username.strip()).first()
    player = find_player_by_credential(username)
    logger.warning(
        'Login de gestión fallido: usuario=%r existe_usuario=%s activo=%s existe_jugador=%s',
        username, bool(user), getattr(user, 'is_active', None), bool(player),
    )


class CoreConfig(AppConfig):
    default_auto_field = 'django.db.models.AutoField'
    name = 'nucleo'
    # Conserva la etiqueta de la app para mantener el historial de migraciones existente.
    label = 'core'

    def ready(self):
        # Runs after every `migrate`, once all permissions exist.
        post_migrate.connect(_ensure_role_groups, sender=self, dispatch_uid='core_ensure_role_groups')
        user_login_failed.connect(_log_failed_login, dispatch_uid='core_log_failed_login')
