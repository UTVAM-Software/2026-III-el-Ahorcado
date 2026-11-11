"""Gestión de permisos por usuario: listado filtrable por rol y asignación con buscador."""
from itertools import groupby

from django.contrib import messages
from django.contrib.auth import get_user_model
from django.contrib.auth.mixins import LoginRequiredMixin, PermissionRequiredMixin
from django.contrib.auth.models import Group
from django.db import transaction
from django.db.models import Count, Q
from django.shortcuts import get_object_or_404, redirect
from django.views.generic import ListView, TemplateView

from nucleo.auth_integration import (
    ROLE_GROUPS,
    ROLE_LABELS,
    MANAGEMENT_READ_ONLY_GROUP,
    has_management_permission,
    is_management_read_only,
    managed_permissions,
    read_only_permissions,
    sync_all_players_to_django_users,
)

User = get_user_model()

ROLE_FILTERS = (
    ('', 'Todos'),
    ('teacher', 'Docentes'),
    ('student', 'Alumnos'),
    ('supervisor', 'Supervisores'),
    ('gestion', 'Solo gestión'),
)

ACTION_LABELS = {'view': 'Ver', 'add': 'Crear', 'change': 'Editar', 'delete': 'Eliminar'}

MODULE_LABELS = {
    'player': 'Jugadores', 'word': 'Palabras', 'assignedgame': 'Actividades asignadas', 'game': 'Partidas',
    'dailyword': 'Palabras del día', 'dailywordanswer': 'Respuestas diarias',
    'passwordresettoken': 'Tokens de recuperación', 'user': 'Usuarios', 'group': 'Grupos', 'permission': 'Permisos',
}
SECTION_LABELS = {'core': 'Juego', 'auth': 'Cuentas y acceso'}
SECTION_DESCRIPTIONS = {
    'core': 'Datos del juego: jugadores, palabras, actividades y resultados.',
    'auth': 'Acceso al panel de gestión: cuentas, roles y permisos.',
}
MODULE_DESCRIPTIONS = {
    'player': 'Cuentas de alumnos, profesores y supervisores.',
    'word': 'Banco de palabras con su dificultad y tema.',
    'assignedgame': 'Actividades que los profesores asignan a sus alumnos.',
    'game': 'Historial de partidas jugadas.',
    'dailyword': 'Palabra del día publicada para todos.',
    'dailywordanswer': 'Respuestas de los alumnos a la palabra del día.',
    'passwordresettoken': 'Enlaces de recuperación de contraseña. Información sensible.',
    'user': 'Cuentas que pueden entrar al panel de gestión.',
    'group': 'Roles y los permisos que heredan sus miembros.',
    'permission': 'Catálogo de permisos del sistema.',
}
ACTION_HELP = {
    'view': 'Consultar registros',
    'add': 'Crear registros nuevos',
    'change': 'Modificar registros existentes',
    'delete': 'Borrar registros',
}


def user_role(user):
    profile = getattr(user, 'player_profile', None)
    return profile.role if profile else None


def filter_by_role(queryset, role):
    if role in ROLE_GROUPS:
        return queryset.filter(player_profile__role=role)
    if role == 'gestion':
        return queryset.filter(player_profile__isnull=True)
    return queryset


class UserPermissionAccessMixin(LoginRequiredMixin, PermissionRequiredMixin):
    login_url = '/gestion/login/'
    permission_required = 'auth.view_user'

    def has_permission(self):
        return has_management_permission(self.request.user, self.permission_required)

    def handle_no_permission(self):
        if is_management_read_only(self.request.user):
            self.raise_exception = True
        return super().handle_no_permission()


class UserPermissionListView(UserPermissionAccessMixin, ListView):
    template_name = 'management/user_permissions_list.html'
    paginate_by = 25
    context_object_name = 'users'

    def get(self, request, *args, **kwargs):
        if not is_management_read_only(request.user):
            sync_all_players_to_django_users()
        return super().get(request, *args, **kwargs)

    def get_queryset(self):
        queryset = User.objects.select_related('player_profile').prefetch_related('groups').annotate(
            direct_permission_count=Count('user_permissions', distinct=True)
        )
        query = self.request.GET.get('q', '').strip()
        if query:
            queryset = queryset.filter(
                Q(username__icontains=query) | Q(email__icontains=query)
                | Q(first_name__icontains=query) | Q(last_name__icontains=query)
            )
        return filter_by_role(queryset, self.request.GET.get('rol', '')).order_by(
            '-is_superuser', 'first_name', 'last_name', 'username'
        )

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        current_role = self.request.GET.get('rol', '')
        context['current_role'] = current_role
        context['query'] = self.request.GET.get('q', '').strip()
        context['role_tabs'] = [
            {'value': value, 'label': label, 'count': filter_by_role(User.objects.all(), value).count(),
             'active': value == current_role}
            for value, label in ROLE_FILTERS
        ]
        context['rows'] = [
            {'user': user, 'role': user_role(user),
             'role_label': ROLE_LABELS.get(user_role(user), 'Gestión'),
             'read_only_mode': any(
                 group.name == MANAGEMENT_READ_ONLY_GROUP for group in user.groups.all()
             )}
            for user in context['users']
        ]
        return context


class UserPermissionEditView(UserPermissionAccessMixin, TemplateView):
    template_name = 'management/user_permissions_edit.html'

    def dispatch(self, request, *args, **kwargs):
        self.target = get_object_or_404(User.objects.select_related('player_profile'), pk=kwargs['pk'])
        self.role = user_role(self.target)
        return super().dispatch(request, *args, **kwargs)

    def can_edit(self):
        # Only superusers grant permissions, so nobody can escalate their own access.
        return self.request.user.is_superuser and not self.target.is_superuser

    def allowed_permissions(self):
        return read_only_permissions() if self.role == 'supervisor' else managed_permissions()

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        direct_ids = set(self.target.user_permissions.values_list('pk', flat=True))
        inherited = {
            perm.pk: group_name
            for group_name, perm in (
                (group.name, perm)
                for group in self.target.groups.prefetch_related('permissions')
                for perm in group.permissions.all()
            )
        }
        allowed_ids = set(self.allowed_permissions().values_list('pk', flat=True))
        permissions = managed_permissions().order_by('content_type__app_label', 'content_type__model')
        module_order = list(MODULE_LABELS)
        sections = {app: {'label': label, 'description': SECTION_DESCRIPTIONS[app], 'modules': []}
                    for app, label in SECTION_LABELS.items()}
        for content_type, perms in groupby(permissions, key=lambda perm: perm.content_type):
            module_label = MODULE_LABELS.get(content_type.model, content_type.model.capitalize())
            by_action = {perm.codename.split('_', 1)[0]: perm for perm in perms}
            cells = []
            for action, action_label in ACTION_LABELS.items():
                perm = by_action.get(action)
                cells.append(perm and {
                    'perm': perm,
                    'action': action,
                    'short': action_label,
                    'help': ACTION_HELP[action],
                    'label': f'{action_label} {module_label.lower()}',
                    'checked': perm.pk in direct_ids,
                    'inherited_from': inherited.get(perm.pk),
                    'allowed': perm.pk in allowed_ids,
                })
            sections.setdefault(content_type.app_label,
                                {'label': content_type.app_label, 'description': '', 'modules': []})
            sections[content_type.app_label]['modules'].append({
                'label': module_label, 'model': content_type.model, 'cells': cells,
                'description': MODULE_DESCRIPTIONS.get(content_type.model, ''),
                'has_allowed': any(cell and cell['allowed'] for cell in cells),
                'full_allowed': all(cell and cell['allowed'] for cell in cells),
                'inherited_any': any(cell and cell['inherited_from'] for cell in cells),
            })
        for section in sections.values():
            section['modules'].sort(key=lambda module: (
                module_order.index(module['model']) if module['model'] in module_order else len(module_order)
            ))

        context.update({
            'target': self.target,
            'role': self.role,
            'role_label': ROLE_LABELS.get(self.role, 'Gestión'),
            'sections': [section for section in sections.values() if section['modules']],
            'actions': [{'label': label, 'help': ACTION_HELP[key]} for key, label in ACTION_LABELS.items()],
            'total_permissions': permissions.count(),
            'module_count': sum(len(section['modules']) for section in sections.values()),
            'can_edit': self.can_edit(),
            'read_only_mode': is_management_read_only(self.target),
            'direct_count': len(direct_ids),
            'inherited_count': len(inherited),
            'groups': list(self.target.groups.values_list('name', flat=True)),
        })
        return context

    def post(self, request, *args, **kwargs):
        if not self.can_edit():
            messages.error(request, 'Solo un superusuario puede asignar permisos a otras cuentas.')
            return redirect('user_permissions_edit', pk=self.target.pk)

        requested = {int(pk) for pk in request.POST.getlist('permissions') if pk.isdigit()}
        read_only_mode = request.POST.get('management_read_only') == 'on'
        allowed_permissions = self.allowed_permissions()
        if read_only_mode:
            allowed_permissions = allowed_permissions.filter(codename__startswith='view_')
        allowed = allowed_permissions.filter(pk__in=requested)
        if len(allowed) != len(requested):
            messages.error(
                request,
                'Algunos permisos no se pueden asignar a esta cuenta. '
                'Los supervisores solo pueden tener permisos de lectura.',
            )
            return redirect('user_permissions_edit', pk=self.target.pk)

        with transaction.atomic():
            # Keep permissions outside the managed apps untouched.
            unmanaged = self.target.user_permissions.exclude(
                pk__in=managed_permissions().values_list('pk', flat=True)
            )
            self.target.user_permissions.set(list(unmanaged) + list(allowed))
            read_only_group, _ = Group.objects.get_or_create(name=MANAGEMENT_READ_ONLY_GROUP)
            if read_only_mode:
                self.target.groups.add(read_only_group)
            else:
                self.target.groups.remove(read_only_group)
        messages.success(
            request, f'Permisos de {self.target.get_username()} actualizados ({len(allowed)} directos).'
        )
        return redirect('user_permissions_edit', pk=self.target.pk)


user_permission_list = UserPermissionListView.as_view()
user_permission_edit = UserPermissionEditView.as_view()
