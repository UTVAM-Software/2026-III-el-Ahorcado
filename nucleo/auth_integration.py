"""Keep the main Player accounts and Django Auth identities in sync."""
from django.contrib.auth import get_user_model
from django.contrib.auth.models import Group, Permission
from django.core.exceptions import ObjectDoesNotExist
from django.db import transaction

ROLE_GROUPS = {'student': 'Alumno', 'teacher': 'Profesor', 'supervisor': 'Supervisor'}
ROLE_LABELS = {'student': 'Alumno', 'teacher': 'Profesor', 'supervisor': 'Supervisor'}
MANAGEMENT_READ_ONLY_GROUP = 'Gestión - Solo lectura'

# Apps whose permissions can be managed from the management panel.
MANAGED_PERMISSION_APPS = ('core', 'auth')


def managed_permissions():
    return Permission.objects.filter(
        content_type__app_label__in=MANAGED_PERMISSION_APPS
    ).select_related('content_type')


def read_only_permissions():
    """Permissions a supervisor may hold: only `view_*` (lectura)."""
    return managed_permissions().filter(codename__startswith='view_')


def is_management_read_only(user):
    if not user.is_authenticated or user.is_superuser:
        return False
    if user.groups.filter(name=MANAGEMENT_READ_ONLY_GROUP).exists():
        return True
    try:
        return user.player_profile.role == 'supervisor'
    except ObjectDoesNotExist:
        return False


def has_explicit_management_view_permission(user, permission):
    app_label, codename = permission.split('.', 1)
    return user.user_permissions.filter(
        content_type__app_label=app_label, codename=codename
    ).exists()


def has_management_permission(user, permission):
    if is_management_read_only(user):
        if permission.rsplit('.', 1)[-1].split('_', 1)[0] != 'view':
            return False
        if user.groups.filter(name=MANAGEMENT_READ_ONLY_GROUP).exists():
            return has_explicit_management_view_permission(user, permission)
    return user.has_perm(permission)


def ensure_role_groups():
    """Create the role groups; the Supervisor group always gets every read permission."""
    groups = {role: Group.objects.get_or_create(name=name)[0] for role, name in ROLE_GROUPS.items()}
    supervisor = groups['supervisor']
    supervisor.permissions.set(read_only_permissions())
    return groups


@transaction.atomic
def sync_player_to_django_user(player, raw_password=None):
    """Create/update the linked Django user and mirror the app role as a Group."""
    User = get_user_model()
    user = player.django_user if player.django_user_id else None
    if user is None:
        username = player.name[:150]
        if User.objects.filter(username=username).exists():
            username = f'player_{player.pk}'
        user = User(username=username)
        user.set_unusable_password()

    if user.username != player.name and not User.objects.filter(username=player.name).exclude(pk=user.pk).exists():
        user.username = player.name
    user.email = player.email
    user.first_name = player.first_name
    user.last_name = player.last_name
    user.is_active = player.is_active
    if raw_password:
        user.set_password(raw_password)
    user.save()

    if player.django_user_id != user.pk:
        player.django_user = user
        player.save(update_fields=['django_user'])

    role_name = ROLE_GROUPS.get(player.role)
    if role_name:
        role_group, created = Group.objects.get_or_create(name=role_name)
        if created and player.role == 'supervisor':
            role_group.permissions.set(read_only_permissions())
        user.groups.remove(*Group.objects.filter(name__in=ROLE_GROUPS.values()).exclude(pk=role_group.pk))
        user.groups.add(role_group)
        if player.role == 'supervisor':
            # A supervisor is read-only: drop any direct write permission.
            user.user_permissions.remove(*user.user_permissions.exclude(codename__startswith='view_'))

    return user


def sync_all_players_to_django_users():
    from .models import Player

    return [sync_player_to_django_user(player) for player in Player.objects.order_by('pk')]
