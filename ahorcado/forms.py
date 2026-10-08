from django import forms
from django.contrib.auth.models import Permission
from django.contrib.contenttypes.models import ContentType
from django.core.exceptions import ValidationError

# Diccionario de traducción de modelos para una presentación 100% en español
MODELOS_ESPANOL = {
    'player': 'Jugador (Player)',
    'word': 'Palabra (Word)',
    'assignedgame': 'Actividad Asignada (AssignedGame)',
    'game': 'Partida (Game)',
    'dailyword': 'Palabra del Día (DailyWord)',
    'dailywordanswer': 'Respuesta de Palabra Diaria (DailyWordAnswer)',
    'permission': 'Permiso del Sistema (Permission)',
    'group': 'Grupo de Usuarios (Group)',
    'user': 'Usuario Administrador (User)',
    'contenttype': 'Tipo de Contenido (ContentType)',
    'session': 'Sesión (Session)',
}


from django.forms.models import ModelChoiceIterator


class SafeModelChoiceIterator(ModelChoiceIterator):
    """Iterador seguro para opciones de ModelChoiceField ante caídas de la base de datos."""
    def __iter__(self):
        try:
            yield from super().__iter__()
        except Exception:
            yield ('', '-- Base de datos en pausa o no disponible --')


class SpanishContentTypeChoiceField(forms.ModelChoiceField):
    """Campo de selección para ContentType con etiquetas formateadas en español y tolerancia a fallos."""
    iterator = SafeModelChoiceIterator

    def label_from_instance(self, obj):
        try:
            app = 'Núcleo' if obj.app_label in ('nucleo', 'core') else obj.app_label.capitalize()
            modelo = MODELOS_ESPANOL.get(obj.model.lower(), obj.model.capitalize())
            return f"{app} ➔ {modelo}"
        except Exception:
            return str(obj)


class PermissionForm(forms.ModelForm):
    """
    ModelForm unificado para las 4 vistas del CRUD:
    1. Nuevo (Crear)       -> read_only=False (editable)
    2. Mostrar (Detalle)   -> read_only=True  (bloqueado/solo lectura)
    3. Actualizar (Editar) -> read_only=False (editable con datos existentes)
    4. Eliminar (Borrar)   -> read_only=True  (bloqueado para confirmación segura)
    """

    content_type = SpanishContentTypeChoiceField(
        queryset=ContentType.objects.all().order_by('app_label', 'model'),
        label='Modelo o entidad del sistema',
        empty_label='-- Selecciona un modelo o entidad --',
        widget=forms.Select(attrs={
            'class': 'form-select',
        }),
        help_text='Módulo o tabla a la que pertenecerá este permiso.'
    )

    class Meta:
        model = Permission
        fields = ['name', 'content_type', 'codename']
        labels = {
            'name': 'Nombre descriptivo',
            'content_type': 'Modelo o entidad del sistema',
            'codename': 'Código del permiso (Identificador)',
        }
        widgets = {
            'name': forms.TextInput(attrs={
                'class': 'form-control',
                'placeholder': 'Ej. Puede crear actividades para alumnos',
                'autocomplete': 'off',
            }),
            'codename': forms.TextInput(attrs={
                'class': 'form-control',
                'placeholder': 'Ej. crear_actividades_alumnos',
                'autocomplete': 'off',
            }),
        }
        help_texts = {
            'name': 'Nombre claro y legible para mostrar en listas y paneles de usuario.',
            'codename': 'Identificador único en minúsculas y sin espacios (convención: accion_modelo).',
        }

    def __init__(self, *args, read_only=False, **kwargs):
        super().__init__(*args, **kwargs)
        self.read_only = read_only

        # Modo Sólo Lectura: bloquea los campos para las vistas "Mostrar" y "Eliminar"
        if read_only:
            for field in self.fields.values():
                field.disabled = True
                field.required = False
                field.help_text = ''

    def clean_codename(self):
        """Valida que el código del permiso no tenga espacios y sea único por modelo."""
        codename = self.cleaned_data.get('codename', '').strip().lower()
        if not codename:
            raise ValidationError('El código del permiso es obligatorio y no puede estar vacío.')
        if ' ' in codename:
            raise ValidationError('El código del permiso no debe contener espacios. Utiliza guiones bajos (_).')

        content_type = self.cleaned_data.get('content_type')
        if content_type:
            qs = Permission.objects.filter(content_type=content_type, codename=codename)
            if self.instance and self.instance.pk:
                qs = qs.exclude(pk=self.instance.pk)
            if qs.exists():
                raise ValidationError(f"Ya existe un permiso con el código '{codename}' para la entidad seleccionada.")

        return codename

    def clean_name(self):
        """Valida longitud mínima del nombre descriptivo."""
        name = self.cleaned_data.get('name', '').strip()
        if len(name) < 3:
            raise ValidationError('El nombre descriptivo debe tener al menos 3 caracteres.')
        return name


class PermissionFilterForm(forms.Form):
    """Formulario auxiliar para filtrar y buscar permisos en la lista."""
    q = forms.CharField(
        required=False,
        label='Búsqueda por texto',
        widget=forms.TextInput(attrs={
            'class': 'form-control',
            'placeholder': 'Buscar por nombre o código...',
        })
    )
    content_type = SpanishContentTypeChoiceField(
        queryset=ContentType.objects.all().order_by('app_label', 'model'),
        required=False,
        label='Filtrar por entidad o modelo',
        empty_label='-- Todas las entidades y modelos --',
        widget=forms.Select(attrs={
            'class': 'form-select',
        })
    )