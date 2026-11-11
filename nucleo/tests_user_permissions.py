from django.contrib.auth import get_user_model
from django.contrib.auth.models import Group, Permission
from django.test import TestCase
from django.urls import reverse

from ahorcado.management_forms import UserManagementForm
from nucleo.auth_integration import (
    MANAGEMENT_READ_ONLY_GROUP,
    ensure_role_groups,
    sync_player_to_django_user,
)
from nucleo.models import Player, Word

User = get_user_model()


def make_player(name, role, **extra):
    player = Player.objects.create(
        name=name, first_name=name.title(), last_name='Prueba', email=f'{name}@example.com',
        role=role, grade='1' if role == 'student' else '', group_name='A' if role == 'student' else '', **extra,
    )
    return player, sync_player_to_django_user(player)


class UserPermissionsPanelTests(TestCase):
    def setUp(self):
        ensure_role_groups()
        self.admin = User.objects.create_superuser('admin', 'admin@example.com', 'Admin-Pass-12345')
        self.teacher_player, self.teacher = make_player('docente', 'teacher')
        self.student_player, self.student = make_player('alumno', 'student')
        self.supervisor_player, self.supervisor = make_player('supervisor', 'supervisor')
        self.view_word = Permission.objects.get(codename='view_word')
        self.delete_word = Permission.objects.get(codename='delete_word')

    def test_supervisor_group_is_read_only(self):
        group = Group.objects.get(name='Supervisor')
        codenames = set(group.permissions.values_list('codename', flat=True))
        self.assertIn('view_word', codenames)
        self.assertTrue(all(code.startswith('view_') for code in codenames))
        self.assertTrue(self.supervisor.groups.filter(name='Supervisor').exists())
        self.assertTrue(self.supervisor.has_perm('core.view_word'))
        self.assertFalse(self.supervisor.has_perm('core.delete_word'))

    def test_list_filters_by_role(self):
        self.client.force_login(self.admin)
        url = reverse('user_permissions_list')
        response = self.client.get(url, {'rol': 'supervisor'})
        self.assertContains(response, '@supervisor')
        self.assertNotContains(response, '@docente')
        response = self.client.get(url, {'rol': 'teacher'})
        self.assertContains(response, '@docente')
        self.assertNotContains(response, '@alumno')
        response = self.client.get(url, {'q': 'alum'})
        self.assertContains(response, '@alumno')
        self.assertNotContains(response, '@docente')

    def test_superuser_assigns_permissions(self):
        self.client.force_login(self.admin)
        url = reverse('user_permissions_edit', args=[self.teacher.pk])
        self.assertContains(self.client.get(url), 'perm-search')
        response = self.client.post(url, {'permissions': [self.view_word.pk, self.delete_word.pk]})
        self.assertRedirects(response, url)
        self.assertEqual(
            set(self.teacher.user_permissions.values_list('codename', flat=True)), {'view_word', 'delete_word'}
        )
        self.client.post(url, {'permissions': [self.view_word.pk]})
        self.assertEqual(list(self.teacher.user_permissions.values_list('codename', flat=True)), ['view_word'])

    def test_supervisor_cannot_receive_write_permissions(self):
        self.client.force_login(self.admin)
        url = reverse('user_permissions_edit', args=[self.supervisor.pk])
        self.client.post(url, {'permissions': [self.view_word.pk, self.delete_word.pk]})
        self.assertFalse(self.supervisor.user_permissions.exists())
        self.client.post(url, {'permissions': [self.view_word.pk]})
        self.assertEqual(list(self.supervisor.user_permissions.values_list('codename', flat=True)), ['view_word'])

    def test_supervisor_can_view_but_not_assign(self):
        self.client.force_login(self.supervisor)
        self.assertEqual(self.client.get(reverse('user_permissions_list')).status_code, 200)
        url = reverse('user_permissions_edit', args=[self.teacher.pk])
        self.assertContains(self.client.get(url), 'Vista de solo lectura')
        self.client.post(url, {'permissions': [self.delete_word.pk]})
        self.assertFalse(self.teacher.user_permissions.exists())
        # Read-only role cannot use the write views of the CRUD.
        self.assertNotEqual(self.client.get(reverse('manage_words_create')).status_code, 200)

    def test_configurable_read_only_access_blocks_writes_and_unselected_modules(self):
        writer_group = Group.objects.create(name='Escritores de palabras')
        writer_group.permissions.add(Permission.objects.get(codename='add_word'))
        self.teacher.groups.add(writer_group)

        self.client.force_login(self.admin)
        edit_url = reverse('user_permissions_edit', args=[self.teacher.pk])
        response = self.client.post(edit_url, {
            'permissions': [self.view_word.pk],
            'management_read_only': 'on',
        })
        self.assertRedirects(response, edit_url)
        self.assertTrue(self.teacher.groups.filter(name=MANAGEMENT_READ_ONLY_GROUP).exists())
        self.assertTrue(self.teacher.has_perm('core.add_word'))

        self.client.force_login(self.teacher)
        list_response = self.client.get(reverse('manage_words_list'))
        self.assertEqual(list_response.status_code, 200)
        self.assertContains(list_response, '>Ver</a>')
        self.assertNotContains(list_response, '>Editar</a>')
        self.assertNotContains(list_response, '>Eliminar</a>')
        self.assertNotContains(list_response, 'Crear palabra')
        self.assertEqual(self.client.get(reverse('manage_players_list')).status_code, 403)
        word_count = Word.objects.count()
        response = self.client.post(reverse('manage_words_create'), {})
        self.assertEqual(response.status_code, 403)
        self.assertEqual(Word.objects.count(), word_count)

    def test_student_without_permissions_is_redirected(self):
        self.client.force_login(self.student)
        response = self.client.get(reverse('user_permissions_list'))
        self.assertNotEqual(response.status_code, 200)

    def test_changing_role_to_supervisor_drops_write_permissions(self):
        self.teacher.user_permissions.add(self.view_word, self.delete_word)
        self.teacher_player.role = 'supervisor'
        self.teacher_player.save()
        sync_player_to_django_user(self.teacher_player)
        self.assertEqual(list(self.teacher.user_permissions.values_list('codename', flat=True)), ['view_word'])
        self.assertEqual(list(self.teacher.groups.values_list('name', flat=True)), ['Supervisor'])

    def test_public_registration_rejects_supervisor_role(self):
        response = self.client.post('/api/auth/register', {
            'name': 'nuevo_sup', 'first_name': 'Nuevo', 'last_name': 'Sup', 'email': 'nuevo@example.com',
            'password': 'Password-Segura-123', 'role': 'supervisor',
        }, content_type='application/json')
        self.assertEqual(response.status_code, 400)
        self.assertFalse(Player.objects.filter(name='nuevo_sup').exists())

    def test_superuser_can_create_superuser_from_management(self):
        self.client.force_login(self.admin)
        response = self.client.post(reverse('manage_users_create'), {
            'username': 'new_admin',
            'email': 'new-admin@example.com',
            'first_name': 'New',
            'last_name': 'Admin',
            'password': 'Strong-River-291-Cloud',
            'player_role': 'teacher',
            'is_active': 'on',
            'is_superuser': 'on',
        })
        self.assertRedirects(response, reverse('manage_users_list'))
        new_admin = User.objects.get(username='new_admin')
        self.assertTrue(new_admin.is_superuser)
        self.assertTrue(new_admin.is_staff)
        self.assertTrue(new_admin.check_password('Strong-River-291-Cloud'))
        self.assertTrue(Player.objects.filter(django_user=new_admin, role='teacher').exists())

    def test_superuser_can_edit_existing_superuser(self):
        target = User.objects.create_superuser('other_admin', 'other-admin@example.com', 'Original-Pass-12345')
        self.client.force_login(self.admin)
        url = reverse('manage_users_update', args=[target.pk])
        response = self.client.get(url)
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'Superusuario')
        response = self.client.post(url, {
            'username': target.username,
            'email': 'updated-admin@example.com',
            'first_name': 'Updated',
            'last_name': 'Admin',
            'is_active': 'on',
            'is_staff': 'on',
            'is_superuser': 'on',
            'player_role': 'teacher',
        })
        self.assertRedirects(response, reverse('manage_users_list'))
        target.refresh_from_db()
        self.assertEqual(target.email, 'updated-admin@example.com')
        self.assertTrue(target.is_superuser)
        self.assertTrue(target.is_staff)

    def test_non_superuser_cannot_edit_or_escalate_to_superuser(self):
        editor = User.objects.create_user('editor', password='Editor-Pass-12345')
        editor.user_permissions.add(
            Permission.objects.get(codename='view_user'),
            Permission.objects.get(codename='add_user'),
            Permission.objects.get(codename='change_user'),
        )
        self.client.force_login(editor)
        target = User.objects.create_superuser('protected_admin', 'protected-admin@example.com', 'Original-Pass-12345')
        self.assertEqual(
            self.client.get(reverse('manage_users_update', args=[target.pk])).status_code,
            404,
        )

        form = UserManagementForm(actor=editor)
        self.assertNotIn('is_superuser', form.fields)
        response = self.client.post(reverse('manage_users_create'), {
            'username': 'ordinary_user',
            'email': 'ordinary@example.com',
            'password': 'Strong-River-291-Cloud',
            'player_grade': '1',
            'player_group': 'A',
            'is_superuser': 'on',
        })
        self.assertRedirects(response, reverse('manage_users_list'))
        ordinary_user = User.objects.get(username='ordinary_user')
        self.assertFalse(ordinary_user.is_superuser)
