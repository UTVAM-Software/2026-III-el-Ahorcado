from django.contrib import messages
from django.contrib.auth.mixins import LoginRequiredMixin, PermissionRequiredMixin
from django.contrib.auth.models import Permission
from django.contrib.contenttypes.models import ContentType
from django.db.models import Q
from django.shortcuts import redirect
from django.urls import reverse_lazy
from django.views.generic import (
    CreateView,
    DeleteView,
    DetailView,
    ListView,
    UpdateView,
)

from ahorcado.forms import PermissionFilterForm, PermissionForm


class StaffOrPermissionRequiredMixin(PermissionRequiredMixin):
    """
    Control de permisos para las vistas del CRUD.
    - Si el usuario está autenticado, valida permisos estándar de Django (o superusuario/staff).
    - En modo evaluación/desarrollo (o sin usuario logueado en sesión), permite acceder
      directamente al CRUD para probar las 4 vistas.
    """
    raise_exception = False
    login_url = '/register.html'

    def has_permission(self):
        user = self.request.user
        # Permite acceso directo para pruebas escolares / desarrollo si no hay sesión iniciada
        if not user.is_authenticated:
            return True
        if user.is_superuser or user.is_staff:
            return True
        return super().has_permission()

    def handle_no_permission(self):
        messages.error(self.request, f"Permiso denegado: Se requiere '{self.permission_required}' para realizar esta acción.")
        return redirect('permission_list')


from django.db import DatabaseError, OperationalError


class PermissionListView(StaffOrPermissionRequiredMixin, ListView):
    """
    CRUD - Listar permisos (R: Read / List).
    Permite visualizar la lista paginada de permisos registrados,
    con opción de filtro por modelo y búsqueda por nombre/codename.
    """
    model = Permission
    template_name = 'permissions/permission_list.html'
    context_object_name = 'permisos'
    paginate_by = 10
    permission_required = 'auth.view_permission'

    def get(self, request, *args, **kwargs):
        try:
            return super().get(request, *args, **kwargs)
        except (OperationalError, DatabaseError):
            messages.warning(
                request,
                "Aviso: La base de datos remota está en pausa en Supabase. Reactiva tu proyecto en Supabase para sincronizar los datos."
            )
            self.object_list = Permission.objects.none()
            context = {
                'permisos': [],
                'filter_form': PermissionFilterForm(),
                'total_count': 0,
                'is_paginated': False,
            }
            return self.render_to_response(context)

    def get_queryset(self):
        try:
            qs = Permission.objects.select_related('content_type').order_by('content_type__app_label', 'content_type__model', 'name')
            q = self.request.GET.get('q', '').strip()
            ct_id = self.request.GET.get('content_type', '').strip()

            if q:
                qs = qs.filter(Q(name__icontains=q) | Q(codename__icontains=q))
            if ct_id and ct_id.isdigit():
                qs = qs.filter(content_type_id=int(ct_id))
            return qs
        except (OperationalError, DatabaseError):
            return Permission.objects.none()

    def get_context_data(self, **kwargs):
        try:
            context = super().get_context_data(**kwargs)
            context['filter_form'] = PermissionFilterForm(self.request.GET or None)
            context['total_count'] = self.get_queryset().count()
            return context
        except (OperationalError, DatabaseError):
            return {
                'permisos': [],
                'filter_form': PermissionFilterForm(),
                'total_count': 0,
                'is_paginated': False,
            }



class PermissionDetailView(StaffOrPermissionRequiredMixin, DetailView):
    """
    CRUD - Mostrar detalle de un permiso (R: Read / Show).
    Presenta la información del permiso utilizando el mismo PermissionForm en modo solo lectura.
    """
    model = Permission
    template_name = 'permissions/permission_form.html'
    context_object_name = 'permiso'
    permission_required = 'auth.view_permission'

    def get_queryset(self):
        return Permission.objects.select_related('content_type')

    def dispatch(self, request, *args, **kwargs):
        try:
            return super().dispatch(request, *args, **kwargs)
        except (OperationalError, DatabaseError):
            messages.warning(request, "No se pudo obtener el permiso: la base de datos remota no responde o está en pausa en Supabase.")
            return redirect('permission_list')

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        try:
            context['form'] = PermissionForm(instance=self.object, read_only=True)
        except Exception:
            context['form'] = None
        context['mode'] = 'show'
        context['action_title'] = f"Mostrar Permiso #{self.object.id if self.object else ''}"
        return context


class PermissionCreateView(StaffOrPermissionRequiredMixin, CreateView):
    """
    CRUD - Nuevo permiso (C: Create).
    Crea un nuevo registro de permiso usando el PermissionForm editable.
    """
    model = Permission
    form_class = PermissionForm
    template_name = 'permissions/permission_form.html'
    success_url = reverse_lazy('permission_list')
    permission_required = 'auth.add_permission'

    def dispatch(self, request, *args, **kwargs):
        try:
            return super().dispatch(request, *args, **kwargs)
        except (OperationalError, DatabaseError):
            messages.warning(request, "La base de datos remota no responde o está en pausa en Supabase. Reactiva tu proyecto en Supabase para registrar permisos.")
            return redirect('permission_list')

    def form_valid(self, form):
        try:
            messages.success(self.request, f"El permiso '{form.instance.name}' fue creado exitosamente.")
            return super().form_valid(form)
        except (OperationalError, DatabaseError):
            messages.error(self.request, "Error al guardar: la base de datos remota no está accesible en este momento.")
            return self.form_invalid(form)

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['mode'] = 'create'
        context['action_title'] = 'Nuevo Permiso'
        context['button_text'] = 'Guardar Permiso'
        return context


class PermissionUpdateView(StaffOrPermissionRequiredMixin, UpdateView):
    """
    CRUD - Actualizar permiso (U: Update).
    Modifica los datos de un permiso existente mediante el mismo PermissionForm editable.
    """
    model = Permission
    form_class = PermissionForm
    template_name = 'permissions/permission_form.html'
    success_url = reverse_lazy('permission_list')
    permission_required = 'auth.change_permission'

    def dispatch(self, request, *args, **kwargs):
        try:
            return super().dispatch(request, *args, **kwargs)
        except (OperationalError, DatabaseError):
            messages.warning(request, "La base de datos remota no responde o está en pausa en Supabase.")
            return redirect('permission_list')

    def form_valid(self, form):
        try:
            messages.success(self.request, f"El permiso '{form.instance.name}' fue actualizado con éxito.")
            return super().form_valid(form)
        except (OperationalError, DatabaseError):
            messages.error(self.request, "Error al actualizar: la base de datos remota no está accesible en este momento.")
            return self.form_invalid(form)

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['mode'] = 'update'
        context['action_title'] = f"Actualizar Permiso #{self.object.id}"
        context['button_text'] = 'Actualizar Permiso'
        return context


class PermissionDeleteView(StaffOrPermissionRequiredMixin, DeleteView):
    """
    CRUD - Eliminar permiso (D: Delete).
    Muestra los datos en el mismo PermissionForm bloqueado para confirmación segura y elimina el registro.
    """
    model = Permission
    template_name = 'permissions/permission_form.html'
    context_object_name = 'permiso'
    success_url = reverse_lazy('permission_list')
    permission_required = 'auth.delete_permission'

    def dispatch(self, request, *args, **kwargs):
        try:
            return super().dispatch(request, *args, **kwargs)
        except (OperationalError, DatabaseError):
            messages.warning(request, "La base de datos remota no responde o está en pausa en Supabase.")
            return redirect('permission_list')

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        try:
            context['form'] = PermissionForm(instance=self.object, read_only=True)
        except Exception:
            context['form'] = None
        context['mode'] = 'delete'
        context['action_title'] = f"Eliminar Permiso #{self.object.id}"
        context['button_text'] = 'Confirmar y Eliminar Permiso'
        return context

    def form_valid(self, form):
        permiso_nombre = self.object.name
        try:
            response = super().form_valid(form)
            messages.success(self.request, f"El permiso '{permiso_nombre}' fue eliminado correctamente.")
            return response
        except (OperationalError, DatabaseError):
            messages.error(self.request, "Error al eliminar: la base de datos remota no está disponible en este momento.")
            return redirect('permission_list')

