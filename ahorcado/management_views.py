from django.contrib.auth import get_user_model
from django.contrib.auth.mixins import LoginRequiredMixin, PermissionRequiredMixin
from django.contrib.auth.models import Group, Permission
from django.http import Http404, HttpResponseRedirect
from django.urls import reverse_lazy
from django.views.generic import CreateView, DeleteView, DetailView, ListView, TemplateView, UpdateView

from ahorcado.forms import PermissionForm
from ahorcado.management_forms import GroupManagementForm, PlayerManagementForm, UserManagementForm
from nucleo.auth_integration import (
    ROLE_LABELS,
    MANAGEMENT_READ_ONLY_GROUP,
    has_management_permission,
    is_management_read_only,
    sync_all_players_to_django_users,
)
from nucleo import models as core_models

User = get_user_model()


class ProtectedManagementView(LoginRequiredMixin, PermissionRequiredMixin):
    login_url = '/gestion/login/'
    raise_exception = False

    def has_permission(self):
        return all(
            has_management_permission(self.request.user, permission)
            for permission in self.get_permission_required()
        )

    def handle_no_permission(self):
        if is_management_read_only(self.request.user):
            self.raise_exception = True
        return super().handle_no_permission()

    def get_form_kwargs(self):
        kwargs = super().get_form_kwargs()
        if self.form_class is UserManagementForm:
            kwargs['actor'] = self.request.user
        return kwargs

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        app_label = getattr(self, 'management_app_label', None)
        model_name = getattr(self, 'management_model_name', None)
        if app_label and model_name:
            context.update({
                f'can_{action}': has_management_permission(
                    self.request.user, f'{app_label}.{action}_{model_name}'
                )
                for action in ('view', 'add', 'change', 'delete')
            })
        if getattr(self, 'object', None) is not None:
            context['object_fields'] = [
                (field.verbose_name, getattr(self.object, field.name))
                for field in self.object._meta.fields
                if field.name not in {'password', 'token_hash', 'supabase_user_id'}
            ]
            if isinstance(self.object, User):
                player = core_models.Player.objects.filter(django_user=self.object).first()
                if player:
                    context['object_fields'].extend([
                        ('Rol principal', ROLE_LABELS.get(player.role, '—')),
                        ('Grado', player.grade or '—'),
                        ('Grupo escolar', player.group_name or '—'),
                    ])
        return context


class ManagementHomeView(LoginRequiredMixin, TemplateView):
    template_name = 'management/home.html'

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['resources'] = [
            {'slug': slug, 'label': label, 'app_label': app_label, 'model_name': model_name,
             'list_url': resource_url_name(slug, 'list')}
            for slug, label, model, app_label, model_name, form_class in RESOURCE_SPECS
            if self.has_management_access(f'{app_label}.view_{model_name}')
        ]
        return context

    def has_management_access(self, permission):
        return has_management_permission(self.request.user, permission)


class ManagementListView(ListView):
    paginate_by = 25

    def get_queryset(self):
        queryset = super().get_queryset()
        return queryset if queryset.ordered else queryset.order_by('pk')

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['fields'] = [field for field in self.model._meta.fields
                             if field.name not in {'password', 'token_hash', 'supabase_user_id'}]
        if self.model is User:
            role_names = ROLE_LABELS
            profiles = {player.django_user_id: player for player in core_models.Player.objects.filter(
                django_user_id__in=[row.pk for row in context['object_list']]
            )}
            context['extra_column_labels'] = ['Rol principal', 'Acceso']
        context['rows'] = [
            (row, [getattr(row, field.name) for field in context['fields']] + (
                [
                    role_names.get(profiles[row.pk].role, '—') if row.pk in profiles else 'Cuenta de gestión',
                    'Superusuario' if row.is_superuser else 'Usuario estándar',
                ]
                if self.model is User else []
            ))
            for row in context['object_list']
        ]
        return context


class ManagementUserListView(ManagementListView):
    def get_queryset(self):
        if not is_management_read_only(self.request.user):
            sync_all_players_to_django_users()
        return super().get_queryset()


class ManagementUserUpdateView(UpdateView):
    def get_object(self, queryset=None):
        user = super().get_object(queryset)
        if user.is_superuser and not self.request.user.is_superuser:
            raise Http404
        return user


class ManagementPlayerDeleteView(DeleteView):
    def form_valid(self, form):
        self.object = self.get_object()
        success_url = self.get_success_url()
        if self.object.django_user_id:
            self.object.django_user.delete()
        else:
            self.object.delete()
        return HttpResponseRedirect(success_url)


RESOURCE_SPECS = [
    ('players', 'Jugadores', core_models.Player, 'core', 'player', PlayerManagementForm),
    ('password-reset-tokens', 'Tokens de recuperación', core_models.PasswordResetToken, 'core', 'passwordresettoken', None),
    ('words', 'Palabras', core_models.Word, 'core', 'word', None),
    ('assigned-games', 'Actividades asignadas', core_models.AssignedGame, 'core', 'assignedgame', None),
    ('games', 'Partidas', core_models.Game, 'core', 'game', None),
    ('daily-words', 'Palabras del día', core_models.DailyWord, 'core', 'dailyword', None),
    ('daily-word-answers', 'Respuestas diarias', core_models.DailyWordAnswer, 'core', 'dailywordanswer', None),
    ('users', 'Usuarios Django', User, 'auth', 'user', UserManagementForm),
    ('groups', 'Grupos Django', Group, 'auth', 'group', GroupManagementForm),
    ('permissions', 'Permisos Django', Permission, 'auth', 'permission', PermissionForm),
]

READ_ONLY_RESOURCES = {'password-reset-tokens'}


def resource_url_name(slug, action):
    return f'manage_{slug.replace("-", "_")}_{action}'


def build_resource_patterns():
    """Build permission-protected CRUD CBVs for each application and Django Auth model."""
    patterns = []
    for slug, label, model, app_label, model_name, form_class in RESOURCE_SPECS:
        base_name = slug.replace('-', '_')
        for action, path, parent, permission_suffix in (
            ('list', f'gestion/{slug}/', ManagementUserListView if model is User else ManagementListView, 'view'),
            ('detail', f'gestion/{slug}/<int:pk>/', DetailView, 'view'),
            ('create', f'gestion/{slug}/nuevo/', CreateView, 'add'),
            ('update', f'gestion/{slug}/<int:pk>/editar/', UpdateView, 'change'),
            ('delete', f'gestion/{slug}/<int:pk>/eliminar/', DeleteView, 'delete'),
        ):
            if slug in READ_ONLY_RESOURCES and action in {'create', 'update', 'delete'}:
                continue
            attrs = {
                'model': model,
                'template_name': 'management/list.html' if action == 'list' else 'management/form.html',
                'permission_required': f'{app_label}.{permission_suffix}_{model_name}',
                'extra_context': {
                    'resource_label': label, 'resource_slug': slug, 'mode': action,
                    'list_url': resource_url_name(slug, 'list'),
                    'read_only': slug in READ_ONLY_RESOURCES,
                },
                'management_app_label': app_label,
                'management_model_name': model_name,
            }
            if action in ('create', 'update'):
                if form_class:
                    attrs['form_class'] = form_class
                else:
                    attrs['fields'] = '__all__'
            if action in ('create', 'update', 'delete'):
                attrs['success_url'] = reverse_lazy(resource_url_name(slug, 'list'))
            parent_view = parent
            if model is core_models.Player and action == 'delete':
                parent_view = ManagementPlayerDeleteView
            elif model is User and action == 'update':
                parent_view = ManagementUserUpdateView
            view_class = type(f'{base_name.title().replace("_", "")} {action.title()} View',
                              (ProtectedManagementView, parent_view), attrs)
            patterns.append((path, view_class.as_view(), resource_url_name(slug, action)))
    return patterns


management_home = ManagementHomeView.as_view()
