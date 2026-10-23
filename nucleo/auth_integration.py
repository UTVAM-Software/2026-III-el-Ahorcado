"""Keep the main Player accounts and Django Auth identities in sync."""
from django.contrib.auth import get_user_model
from django.contrib.auth.models import Group
from django.db import transaction

ROLE_GROUPS = {'student': 'Alumno', 'teacher': 'Profesor'}


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
        role_group, _ = Group.objects.get_or_create(name=role_name)
        user.groups.remove(*Group.objects.filter(name__in=ROLE_GROUPS.values()).exclude(pk=role_group.pk))
        user.groups.add(role_group)

    return user


def sync_all_players_to_django_users():
    from .models import Player

    return [sync_player_to_django_user(player) for player in Player.objects.order_by('pk')]
