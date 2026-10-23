import bcrypt
from django import forms
from django.contrib.auth import get_user_model
from django.contrib.auth.password_validation import validate_password
from django.contrib.auth.models import Group
from django.core.exceptions import ValidationError
from django.db import transaction

from nucleo.auth_integration import ROLE_GROUPS, sync_player_to_django_user
from nucleo.models import Player

User = get_user_model()


class UserManagementForm(forms.ModelForm):
    username = forms.CharField(max_length=30, label='Nombre de usuario')
    email = forms.EmailField(max_length=100, label='Correo electrónico')
    player_role = forms.ChoiceField(
        label='Rol principal', choices=(('student', 'Alumno'), ('teacher', 'Profesor')),
        help_text='Este rol se aplica a la cuenta principal y a su grupo de Django.',
    )
    player_grade = forms.CharField(label='Grado', max_length=30, required=False)
    player_group = forms.CharField(label='Grupo escolar', max_length=20, required=False)
    password = forms.CharField(
        label='Contraseña', required=False,
        widget=forms.PasswordInput(attrs={'autocomplete': 'new-password'}),
        help_text='Obligatoria al crear. Déjala vacía al editar para conservar la actual.',
    )

    class Meta:
        model = User
        fields = ('username', 'email', 'first_name', 'last_name', 'is_active',
                  'is_staff', 'groups', 'user_permissions')

    def __init__(self, *args, actor=None, **kwargs):
        super().__init__(*args, **kwargs)
        self.actor = actor
        self.player_profile = None
        if self.instance.pk:
            self.player_profile = Player.objects.filter(django_user=self.instance).first()
        if self.player_profile:
            self.initial.setdefault('player_role', self.player_profile.role)
            self.initial.setdefault('player_grade', self.player_profile.grade)
            self.initial.setdefault('player_group', self.player_profile.group_name)
        else:
            self.initial.setdefault('player_role', 'student')
        if not actor or not actor.is_superuser:
            for field_name in ('is_staff', 'groups', 'user_permissions', 'player_role'):
                self.fields.pop(field_name, None)

    def clean_username(self):
        username = self.cleaned_data['username'].strip()
        qs = Player.objects.filter(name__iexact=username)
        if self.player_profile:
            qs = qs.exclude(pk=self.player_profile.pk)
        if qs.exists():
            raise ValidationError('Ese nombre de usuario ya está ligado a una cuenta principal.')
        return username

    def clean_email(self):
        email = self.cleaned_data['email'].strip().lower()
        qs = Player.objects.filter(email__iexact=email)
        if self.player_profile:
            qs = qs.exclude(pk=self.player_profile.pk)
        if qs.exists():
            raise ValidationError('Ese correo ya está ligado a una cuenta principal.')
        return email

    def clean(self):
        cleaned = super().clean()
        role = cleaned.get('player_role') or (self.player_profile.role if self.player_profile else 'student')
        if role == 'student':
            if not cleaned.get('player_grade'):
                self.add_error('player_grade', 'El grado es obligatorio para alumnos.')
            if not cleaned.get('player_group'):
                self.add_error('player_group', 'El grupo escolar es obligatorio para alumnos.')
        return cleaned

    def clean_password(self):
        password = self.cleaned_data.get('password')
        if not password and not self.instance.pk:
            raise ValidationError('La contraseña es obligatoria para crear un usuario.')
        if password:
            validate_password(password, self.instance)
        return password

    @transaction.atomic
    def save(self, commit=True):
        user = super().save(commit=False)
        password = self.cleaned_data.get('password')
        if password:
            user.set_password(password)
        if not commit:
            return user

        user.save()
        self.save_m2m()
        profile = self.player_profile or Player(django_user=user)
        profile.django_user = user
        profile.name = self.cleaned_data['username']
        profile.email = self.cleaned_data['email']
        profile.first_name = self.cleaned_data.get('first_name', '')
        profile.last_name = self.cleaned_data.get('last_name', '')
        profile.is_active = user.is_active
        profile.role = self.cleaned_data.get('player_role') or (profile.role if self.player_profile else 'student')
        grade = self.cleaned_data.get('player_grade', profile.grade)
        group_name = self.cleaned_data.get('player_group', profile.group_name)
        profile.grade = grade.strip().upper() if profile.role == 'student' else ''
        profile.group_name = group_name.strip().upper() if profile.role == 'student' else ''
        if password:
            profile.password = bcrypt.hashpw(password.encode(), bcrypt.gensalt()).decode()
        profile.save()
        sync_player_to_django_user(profile, raw_password=password)
        return user


class PlayerManagementForm(forms.ModelForm):
    password = forms.CharField(
        label='Contraseña (opcional)', required=False,
        widget=forms.PasswordInput(attrs={'autocomplete': 'new-password'}),
        help_text='Si se define, se almacenará con bcrypt. Vacía para conservar la contraseña actual.',
    )

    class Meta:
        model = Player
        exclude = ('password', 'django_user')

    @transaction.atomic
    def save(self, commit=True):
        player = super().save(commit=False)
        raw_password = self.cleaned_data.get('password')
        if raw_password:
            player.password = bcrypt.hashpw(raw_password.encode(), bcrypt.gensalt()).decode()
        if commit:
            player.save()
            self.save_m2m()
            sync_player_to_django_user(player, raw_password=raw_password)
        return player


class GroupManagementForm(forms.ModelForm):
    class Meta:
        model = Group
        fields = ('name', 'permissions')

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        if self.instance.pk and self.instance.name in ROLE_GROUPS.values():
            self.fields['name'].disabled = True
            self.fields['name'].help_text = 'Este grupo está vinculado al rol de la cuenta principal.'
