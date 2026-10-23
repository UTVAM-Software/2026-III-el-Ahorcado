from django.contrib.auth import get_user_model
from django.contrib.auth.mixins import LoginRequiredMixin, PermissionRequiredMixin
from django.contrib.auth.models import Group, Permission
from django.urls import reverse_lazy
from django.views.generic import CreateView, DeleteView, DetailView, ListView, TemplateView, UpdateView

from ahorcado.forms import PermissionForm
from ahorcado.management_forms import GroupManagementForm, PlayerManagementForm, UserManagementForm
from nucleo import models as core_models

User = get_user_model()


class ProtectedManagementView(LoginRequiredMixin, PermissionRequiredMixin):
    login_url = '/gestion/login/'
    raise_exception = False

    def get_form_kwargs(self):
        kwargs = super().get_form_kwargs()
        if self.form_class is UserManagementForm:
            kwargs['actor'] = self.request.user
        return kwargs

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        if getattr(self, 'object', None) is not None:
            context['object_fields'] = [
                (field.verbose_name, getattr(self.object, field.name))
                for field in self.object._meta.fields
                if field.name not in {'password', 'token_hash', 'supabase_user_id'}
            ]
        return context


class ManagementHomeView(LoginRequiredMixin, TemplateView):
    template_name = 'management/home.html'

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['resources'] = [
            {'slug': slug, 'label': label, 'app_label': app_label, 'model_name': model_name,
             'list_url': resource_url_name(slug, 'list')}
            for slug, label, model, app_label, model_name, form_class in RESOURCE_SPECS
            if self.request.user.has_perm(f'{app_label}.view_{model_name}')
        ]
        return context


class ManagementListView(ListView):
    paginate_by = 25

    def get_queryset(self):
        queryset = super().get_queryset()
        return queryset if queryset.ordered else queryset.order_by('pk')

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['fields'] = [field for field in self.model._meta.fields
                             if field.name not in {'password', 'token_hash', 'supabase_user_id'}]
        context['rows'] = [
            (row, [getattr(row, field.name) for field in context['fields']])
            for row in context['object_list']
        ]
        return context


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


def resource_url_name(slug, action):
    return f'manage_{slug.replace("-", "_")}_{action}'


def build_resource_patterns():
    """Build permission-protected CRUD CBVs for each application and Django Auth model."""
    patterns = []
    for slug, label, model, app_label, model_name, form_class in RESOURCE_SPECS:
        base_name = slug.replace('-', '_')
        for action, path, parent, permission_suffix in (
            ('list', f'gestion/{slug}/', ManagementListView, 'view'),
            ('detail', f'gestion/{slug}/<int:pk>/', DetailView, 'view'),
            ('create', f'gestion/{slug}/nuevo/', CreateView, 'add'),
            ('update', f'gestion/{slug}/<int:pk>/editar/', UpdateView, 'change'),
            ('delete', f'gestion/{slug}/<int:pk>/eliminar/', DeleteView, 'delete'),
        ):
            attrs = {
                'model': model,
                'template_name': 'management/list.html' if action == 'list' else 'management/form.html',
                'permission_required': f'{app_label}.{permission_suffix}_{model_name}',
                'extra_context': {
                    'resource_label': label, 'resource_slug': slug, 'mode': action,
                    'list_url': resource_url_name(slug, 'list'),
                },
            }
            if action in ('create', 'update'):
                if form_class:
                    attrs['form_class'] = form_class
                else:
                    attrs['fields'] = '__all__'
            if action in ('create', 'update', 'delete'):
                attrs['success_url'] = reverse_lazy(resource_url_name(slug, 'list'))
            view_class = type(f'{base_name.title().replace("_", "")} {action.title()} View',
                              (ProtectedManagementView, parent), attrs)
            patterns.append((path, view_class.as_view(), resource_url_name(slug, action)))
    return patterns


management_home = ManagementHomeView.as_view()
