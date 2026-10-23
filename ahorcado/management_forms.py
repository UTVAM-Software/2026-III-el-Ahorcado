import bcrypt
from django import forms
from django.contrib.auth import get_user_model
from django.contrib.auth.password_validation import validate_password
from django.contrib.auth.models import Group
from django.core.exceptions import ValidationError

from nucleo.models import Player

User = get_user_model()


class UserManagementForm(forms.ModelForm):
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
        if not actor or not actor.is_superuser:
            for field_name in ('is_staff', 'groups', 'user_permissions'):
                self.fields.pop(field_name, None)

    def clean_password(self):
        password = self.cleaned_data.get('password')
        if not password and not self.instance.pk:
            raise ValidationError('La contraseña es obligatoria para crear un usuario.')
        if password:
            validate_password(password, self.instance)
        return password

    def save(self, commit=True):
        user = super().save(commit=False)
        password = self.cleaned_data.get('password')
        if password:
            user.set_password(password)
        if commit:
            user.save()
            self.save_m2m()
        return user


class PlayerManagementForm(forms.ModelForm):
    password = forms.CharField(
        label='Contraseña (opcional)', required=False,
        widget=forms.PasswordInput(attrs={'autocomplete': 'new-password'}),
        help_text='Si se define, se almacenará con bcrypt. Vacía para conservar la contraseña actual.',
    )

    class Meta:
        model = Player
        exclude = ('password',)

    def save(self, commit=True):
        player = super().save(commit=False)
        raw_password = self.cleaned_data.get('password')
        if raw_password:
            player.password = bcrypt.hashpw(raw_password.encode(), bcrypt.gensalt()).decode()
        if commit:
            player.save()
            self.save_m2m()
        return player


class GroupManagementForm(forms.ModelForm):
    class Meta:
        model = Group
        fields = ('name', 'permissions')
