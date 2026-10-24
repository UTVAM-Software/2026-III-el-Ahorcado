import hashlib
import io
import re
from contextlib import redirect_stdout
from datetime import timedelta
from types import SimpleNamespace
from unittest.mock import patch

from django.core.cache import cache
from django.core import mail
from django.db import IntegrityError
from django.test import SimpleTestCase, TestCase, override_settings
from django.utils import timezone

from ahorcado.management_views import build_resource_patterns, resource_url_name
from .models import AssignedGame, PasswordResetToken, Player, Word


class ManagementSafetyTests(SimpleTestCase):
    def test_password_reset_tokens_are_read_only_in_management(self):
        route_names = {
            name for _, _, name in build_resource_patterns()
            if name.startswith('manage_password_reset_tokens_')
        }

        self.assertEqual(
            route_names,
            {
                resource_url_name('password-reset-tokens', 'list'),
                resource_url_name('password-reset-tokens', 'detail'),
            },
        )

    def test_password_reset_token_string_does_not_expose_hash(self):
        player = Player(name='test-player')
        token = PasswordResetToken(
            player=player,
            token_hash='sensitive-hash',
            expires_at=timezone.now(),
        )

        self.assertIn(player.name, str(token))
        self.assertNotIn(token.token_hash, str(token))


@override_settings(
    EMAIL_BACKEND='django.core.mail.backends.locmem.EmailBackend',
    EMAIL_HOST='smtp.test',
    DEFAULT_FROM_EMAIL='no-reply@example.com',
    PUBLIC_APP_URL='https://ahorcado.test',
)
class SecurityHardeningTests(TestCase):
    def setUp(self):
        cache.clear()
        mail.outbox.clear()

    def register(self, name='testuser', email='test@example.com', password='SecurePass123',
                 role='student', grade='1° secundaria', group_name='A'):
        return self.client.post(
            '/api/auth/register',
            {
                'name': name,
                'first_name': 'Test',
                'last_name': 'User',
                'email': email,
                'role': role,
                'grade': grade,
                'group_name': group_name,
                'password': password,
            },
            content_type='application/json',
        )

    def test_google_auth_config_is_not_cached(self):
        response = self.client.get('/api/auth/google/config')

        self.assertEqual(response.status_code, 200)
        self.assertIn('no-store', response['Cache-Control'])

    def test_registration_creates_account_directly(self):
        response = self.register()

        self.assertEqual(response.status_code, 200)
        self.assertIn('token', response.json())
        self.assertEqual(response.json()['user']['email'], 'test@example.com')
        self.assertEqual(response.json()['user']['grade'], '1° SECUNDARIA')
        self.assertEqual(response.json()['user']['group_name'], 'A')
        self.assertTrue(Player.objects.filter(email='test@example.com').exists())
        login = self.client.post(
            '/api/auth/login',
            {'credential': 'testuser', 'password': 'SecurePass123'},
            content_type='application/json',
        )
        self.assertEqual(login.status_code, 200)

    def test_google_auth_creates_a_verified_student_account(self):
        supabase_user = {
            'id': 'supabase-user-123',
            'email': 'google@example.com',
            'email_confirmed_at': '2026-10-21T12:00:00Z',
            'app_metadata': {'provider': 'google'},
            'user_metadata': {'full_name': 'Google Student'},
        }
        with patch('nucleo.views_auth.verify_supabase_access_token', return_value=(supabase_user, None)):
            response = self.client.post(
                '/api/auth/google',
                {
                    'access_token': 'verified-access-token',
                    'password': 'GooglePass123',
                    'role': 'student',
                    'grade': '2° secundaria',
                    'group_name': 'B',
                },
                content_type='application/json',
            )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()['user']['email'], 'google@example.com')
        self.assertEqual(response.json()['user']['role'], 'student')
        self.assertEqual(response.json()['user']['grade'], '2° SECUNDARIA')
        player = Player.objects.get(supabase_user_id='supabase-user-123')
        self.assertNotEqual(player.password, '')
        self.assertTrue(player.is_active)

    def test_google_registration_returns_verified_profile_before_creating_account(self):
        supabase_user = {
            'id': 'supabase-user-pending-registration',
            'email': 'pending@example.com',
            'email_confirmed_at': '2026-10-21T12:00:00Z',
            'app_metadata': {'provider': 'google'},
            'user_metadata': {
                'given_name': 'Google',
                'family_name': 'Student',
                'full_name': 'Google Student',
            },
        }
        with patch('nucleo.views_auth.verify_supabase_access_token', return_value=(supabase_user, None)):
            response = self.client.post(
                '/api/auth/google',
                {'access_token': 'verified-access-token', 'intent': 'register'},
                content_type='application/json',
            )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json(), {
            'requires_registration': True,
            'profile': {
                'email': 'pending@example.com',
                'first_name': 'Google',
                'last_name': 'Student',
            },
        })
        self.assertFalse(Player.objects.filter(email='pending@example.com').exists())

    def test_google_registration_saves_chosen_password_for_email_or_username_login(self):
        supabase_user = {
            'id': 'supabase-user-registration-complete',
            'email': 'completed@example.com',
            'email_confirmed_at': '2026-10-21T12:00:00Z',
            'app_metadata': {'provider': 'google'},
            'user_metadata': {'full_name': 'Google Student'},
        }
        with patch('nucleo.views_auth.verify_supabase_access_token', return_value=(supabase_user, None)):
            response = self.client.post(
                '/api/auth/google',
                {
                    'access_token': 'verified-access-token',
                    'intent': 'register',
                    'name': 'google_student',
                    'first_name': 'Nombre elegido',
                    'last_name': 'Apellido elegido',
                    'password': 'GooglePass123',
                    'role': 'student',
                    'grade': '2° secundaria',
                    'group_name': 'B',
                },
                content_type='application/json',
            )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()['user']['email'], 'completed@example.com')
        self.assertEqual(response.json()['user']['name'], 'google_student')
        self.assertEqual(response.json()['user']['first_name'], 'Nombre elegido')
        self.assertEqual(response.json()['user']['last_name'], 'Apellido elegido')
        self.assertEqual(response.json()['user']['grade'], '2° SECUNDARIA')
        player = Player.objects.get(
            email='completed@example.com',
            supabase_user_id='supabase-user-registration-complete',
        )
        self.assertTrue(player.is_active)
        login_by_email = self.client.post(
            '/api/auth/login',
            {'credential': 'completed@example.com', 'password': 'GooglePass123'},
            content_type='application/json',
        )
        login_by_username = self.client.post(
            '/api/auth/login',
            {'credential': 'google_student', 'password': 'GooglePass123'},
            content_type='application/json',
        )
        self.assertEqual(login_by_email.status_code, 200)
        self.assertEqual(login_by_username.status_code, 200)

    def test_google_registration_requires_a_strong_password(self):
        supabase_user = {
            'id': 'supabase-user-weak-password',
            'email': 'weak-password@example.com',
            'email_confirmed_at': '2026-10-21T12:00:00Z',
            'app_metadata': {'provider': 'google'},
            'user_metadata': {'full_name': 'Google Student'},
        }
        with patch('nucleo.views_auth.verify_supabase_access_token', return_value=(supabase_user, None)):
            response = self.client.post(
                '/api/auth/google',
                {
                    'access_token': 'verified-access-token',
                    'intent': 'register',
                    'name': 'weak_password',
                    'role': 'teacher',
                    'password': 'weak',
                },
                content_type='application/json',
            )

        self.assertEqual(response.status_code, 400)
        self.assertIn('contraseña', response.json()['error'])
        self.assertFalse(Player.objects.filter(email='weak-password@example.com').exists())

    def test_google_registration_retry_after_concurrent_create_logs_in_created_account(self):
        supabase_user = {
            'id': 'supabase-user-registration-race',
            'email': 'race@example.com',
            'email_confirmed_at': '2026-10-21T12:00:00Z',
            'app_metadata': {'provider': 'google'},
            'user_metadata': {'full_name': 'Race Student'},
        }
        original_filter = Player.objects.filter
        user_filter_calls = 0
        concurrent_player = Player(
            id=999,
            name='race_student',
            first_name='Race',
            last_name='Student',
            email='race@example.com',
            supabase_user_id='supabase-user-registration-race',
            role='teacher',
        )

        def filter_with_concurrent_player(*args, **kwargs):
            nonlocal user_filter_calls
            if kwargs.get('supabase_user_id') == 'supabase-user-registration-race':
                user_filter_calls += 1
                if user_filter_calls == 1:
                    return SimpleNamespace(first=lambda: None)
                return SimpleNamespace(first=lambda: concurrent_player)
            return original_filter(*args, **kwargs)

        with (
            patch('nucleo.views_auth.verify_supabase_access_token', return_value=(supabase_user, None)),
            patch.object(Player.objects, 'filter', side_effect=filter_with_concurrent_player),
            patch.object(Player.objects, 'create', side_effect=IntegrityError('concurrent unique insert')),
        ):
            response = self.client.post(
                '/api/auth/google',
                {
                    'access_token': 'verified-access-token',
                    'password': 'GooglePass123',
                    'intent': 'register',
                    'name': 'race_student',
                    'role': 'teacher',
                },
                content_type='application/json',
            )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()['user']['email'], 'race@example.com')
        self.assertEqual(user_filter_calls, 2)

    def test_google_auth_rejects_unverified_email(self):
        supabase_user = {
            'id': 'supabase-user-unverified',
            'email': 'unverified@example.com',
            'app_metadata': {'provider': 'google'},
            'user_metadata': {'full_name': 'Unverified User'},
        }
        with patch('nucleo.views_auth.verify_supabase_access_token', return_value=(supabase_user, None)):
            response = self.client.post(
                '/api/auth/google',
                {'access_token': 'verified-access-token', 'role': 'teacher'},
                content_type='application/json',
            )

        self.assertEqual(response.status_code, 401)
        self.assertFalse(Player.objects.filter(email='unverified@example.com').exists())

    def test_google_auth_rejects_a_different_supabase_provider(self):
        supabase_user = {
            'id': 'supabase-user-email-provider',
            'email': 'email-login@example.com',
            'email_confirmed_at': '2026-10-21T12:00:00Z',
            'app_metadata': {'provider': 'email'},
            'user_metadata': {'full_name': 'Email Login'},
        }
        with patch('nucleo.views_auth.verify_supabase_access_token', return_value=(supabase_user, None)):
            response = self.client.post(
                '/api/auth/google',
                {'access_token': 'verified-access-token', 'role': 'teacher'},
                content_type='application/json',
            )

        self.assertEqual(response.status_code, 401)
        self.assertFalse(Player.objects.filter(email='email-login@example.com').exists())

    def test_google_auth_is_rate_limited_before_contacting_supabase(self):
        cache.set('google-login:127.0.0.1', 10, 300)
        with patch('nucleo.views_auth.verify_supabase_access_token') as verify:
            response = self.client.post(
                '/api/auth/google',
                {'access_token': 'fake-token'},
                content_type='application/json',
            )

        self.assertEqual(response.status_code, 429)
        verify.assert_not_called()

    def test_google_auth_does_not_automatically_link_existing_email(self):
        self.register()
        supabase_user = {
            'id': 'different-supabase-user',
            'email': 'test@example.com',
            'email_confirmed_at': '2026-10-21T12:00:00Z',
            'app_metadata': {'provider': 'google'},
            'user_metadata': {'full_name': 'Test User'},
        }
        with patch('nucleo.views_auth.verify_supabase_access_token', return_value=(supabase_user, None)):
            response = self.client.post(
                '/api/auth/google',
                {'access_token': 'verified-access-token', 'role': 'teacher'},
                content_type='application/json',
            )

        self.assertEqual(response.status_code, 409)
        self.assertIn('no se vinculan', response.json()['error'])
        self.assertEqual(Player.objects.filter(email='test@example.com').count(), 1)

    def test_google_auth_logs_in_existing_linked_account_without_profile_draft(self):
        supabase_user = {
            'id': 'supabase-user-existing',
            'email': 'linked@example.com',
            'email_confirmed_at': '2026-10-21T12:00:00Z',
            'app_metadata': {'provider': 'google'},
            'user_metadata': {'full_name': 'Linked User'},
        }
        with patch('nucleo.views_auth.verify_supabase_access_token', return_value=(supabase_user, None)):
            self.client.post(
                '/api/auth/google',
                {
                    'access_token': 'verified-access-token',
                    'intent': 'register',
                    'password': 'GooglePass123',
                    'role': 'teacher',
                },
                content_type='application/json',
            )
            response = self.client.post(
                '/api/auth/google',
                {'access_token': 'verified-access-token'},
                content_type='application/json',
            )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()['user']['email'], 'linked@example.com')

    def test_student_registration_requires_grade_and_group(self):
        response = self.register(grade='', group_name='')

        self.assertEqual(response.status_code, 400)
        self.assertIn('grado y grupo', response.json()['error'])
        self.assertFalse(Player.objects.filter(email='test@example.com').exists())

    def test_teacher_registration_does_not_require_student_group(self):
        response = self.register(
            name='teacheruser',
            email='teacher@example.com',
            role='teacher',
            grade='',
            group_name='',
        )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()['user']['role'], 'teacher')
        self.assertEqual(response.json()['user']['grade'], '')

    def test_teacher_student_list_includes_grade_and_group_for_filtering(self):
        teacher_response = self.register(
            name='teacheruser',
            email='teacher@example.com',
            role='teacher',
            grade='',
            group_name='',
        )
        self.register(name='studentone', email='student@example.com', grade='2° secundaria', group_name='B')

        response = self.client.get(
            '/api/assignments/students',
            HTTP_AUTHORIZATION=f"Bearer {teacher_response.json()['token']}",
        )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(len(response.json()), 1)
        self.assertEqual(response.json()[0]['grade'], '2° SECUNDARIA')
        self.assertEqual(response.json()[0]['group_name'], 'B')

    def test_teacher_can_assign_the_same_word_set_to_all_students_in_a_group(self):
        teacher_response = self.register(
            name='teacheruser',
            email='teacher@example.com',
            role='teacher',
            grade='',
            group_name='',
        )
        first_student = self.register(name='studentone', email='student1@example.com')
        second_student = self.register(
            name='studenttwo',
            email='student2@example.com',
            grade='1° secundaria',
            group_name='A',
        )
        words = [
            Word.objects.create(word=f'Palabra{i}', difficulty='easy')
            for i in range(3)
        ]

        response = self.client.post(
            '/api/assignments',
            {
                'studentIds': [
                    first_student.json()['user']['id'],
                    second_student.json()['user']['id'],
                ],
                'wordIds': [word.id for word in words],
                'theme': 'Ciencias',
                'difficulty': 'easy',
            },
            content_type='application/json',
            HTTP_AUTHORIZATION=f"Bearer {teacher_response.json()['token']}",
        )

        self.assertEqual(response.status_code, 201)
        self.assertEqual(response.json()['assignedStudents'], 2)
        assignments = AssignedGame.objects.order_by('student_id')
        self.assertEqual(assignments.count(), 2)
        self.assertEqual(assignments[0].word_ids, assignments[1].word_ids)
        self.assertEqual(set(assignments[0].word_ids), {word.id for word in words})

    def test_prepare_game_matches_theme_without_case_sensitivity(self):
        teacher_response = self.register(
            name='animalteacher',
            email='animalteacher@example.com',
            role='teacher',
            grade='',
            group_name='',
        )
        for i in range(5):
            Word.objects.create(word=f'animal{i}', difficulty='easy', theme='Animales')

        response = self.client.post(
            '/api/words/prepare-game',
            {
                'theme': 'animales',
                'count': 5,
                'source': 'random',
                'difficulty': 'easy',
            },
            content_type='application/json',
            HTTP_AUTHORIZATION=f"Bearer {teacher_response.json()['token']}",
        )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()['theme'], 'animales')
        returned_ids = {item['id'] for item in response.json()['words']}
        available_ids = set(
            Word.objects.filter(theme__iexact='animales', difficulty='easy')
            .values_list('id', flat=True)
        )
        self.assertEqual(len(returned_ids), 5)
        self.assertTrue(returned_ids.issubset(available_ids))

    def test_register_rejects_malformed_email(self):
        response = self.register(name='invalidemail', email='student@invalid_domain.com')

        self.assertEqual(response.status_code, 400)
        self.assertIn('correo', response.json()['error'].lower())

    def test_register_rejects_email_longer_than_model_limit(self):
        response = self.register(name='longemail', email=f'{"a" * 90}@example.com')

        self.assertEqual(response.status_code, 400)
        self.assertIn('100 caracteres', response.json()['error'])

    def test_register_rejects_weak_password(self):
        response = self.register(name='alice', email='alice@example.com', password='abc123')

        self.assertEqual(response.status_code, 400)
        self.assertIn('contraseña', response.json()['error'].lower())

    def test_login_bruteforce_is_rate_limited(self):
        self.register(name='bob', email='bob@example.com')

        responses = []
        for _ in range(6):
            response = self.client.post(
                '/api/auth/login',
                {'credential': 'bob', 'password': 'wrong-password'},
                content_type='application/json',
            )
            responses.append(response.status_code)

        self.assertIn(429, responses)

    def test_password_reset_email_and_token_can_change_password_once(self):
        self.register()

        response = self.client.post(
            '/api/auth/password-reset',
            {'email': 'test@example.com'},
            content_type='application/json',
        )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(len(mail.outbox), 1)
        self.assertIn('password-recovery.html?token=', mail.outbox[0].body)
        reset_token = re.search(
            r'password-recovery\.html\?token=([A-Za-z0-9_-]+)',
            mail.outbox[0].body,
        ).group(1)
        stored_reset = PasswordResetToken.objects.get(player__email='test@example.com')
        self.assertNotEqual(stored_reset.token_hash, reset_token)

        changed = self.client.post(
            '/api/auth/password-reset/confirm',
            {'token': reset_token, 'password': 'NewSecurePass456'},
            content_type='application/json',
        )

        self.assertEqual(changed.status_code, 200)
        self.assertFalse(PasswordResetToken.objects.filter(player__email='test@example.com').exists())
        old_login = self.client.post(
            '/api/auth/login',
            {'credential': 'testuser', 'password': 'SecurePass123'},
            content_type='application/json',
        )
        new_login = self.client.post(
            '/api/auth/login',
            {'credential': 'testuser', 'password': 'NewSecurePass456'},
            content_type='application/json',
        )
        self.assertEqual(old_login.status_code, 401)
        self.assertEqual(new_login.status_code, 200)

        reused = self.client.post(
            '/api/auth/password-reset/confirm',
            {'token': reset_token, 'password': 'AnotherSecure789'},
            content_type='application/json',
        )
        self.assertEqual(reused.status_code, 400)

    @override_settings(
        DEBUG=True,
        EMAIL_BACKEND='django.core.mail.backends.console.EmailBackend',
        EMAIL_HOST='',
        DEFAULT_FROM_EMAIL='',
        PUBLIC_APP_URL='',
    )
    def test_password_reset_works_in_local_console_mode_without_smtp(self):
        self.register()
        output = io.StringIO()
        with redirect_stdout(output):
            response = self.client.post(
                '/api/auth/password-reset',
                {'email': 'test@example.com'},
                content_type='application/json',
            )

        self.assertEqual(response.status_code, 200)
        self.assertIn('enlace de recuperación aparecerá en la consola', response.json()['message'])
        match = re.search(
            r'password-recovery\.html\?token=([A-Za-z0-9_-]+)',
            output.getvalue(),
        )
        self.assertIsNotNone(match)
        self.assertIn('http://testserver/password-recovery.html?token=', output.getvalue())
        self.assertTrue(
            PasswordResetToken.objects.filter(player__email='test@example.com').exists()
        )
        changed = self.client.post(
            '/api/auth/password-reset/confirm',
            {'token': match.group(1), 'password': 'ConsoleResetPass789'},
            content_type='application/json',
        )
        self.assertEqual(changed.status_code, 200)
        login = self.client.post(
            '/api/auth/login',
            {'credential': 'testuser', 'password': 'ConsoleResetPass789'},
            content_type='application/json',
        )
        self.assertEqual(login.status_code, 200)

    def test_password_reset_request_does_not_disclose_unknown_email(self):
        self.register()
        known_email_response = self.client.post(
            '/api/auth/password-reset',
            {'email': 'test@example.com'},
            content_type='application/json',
        )
        unknown_email_response = self.client.post(
            '/api/auth/password-reset',
            {'email': 'missing@example.com'},
            content_type='application/json',
        )

        self.assertEqual(known_email_response.status_code, unknown_email_response.status_code)
        self.assertEqual(known_email_response.json(), unknown_email_response.json())
        self.assertEqual(len(mail.outbox), 1)

    def test_expired_password_reset_token_is_rejected(self):
        player = Player.objects.create(
            name='expireduser',
            first_name='Expired',
            last_name='User',
            email='expired@example.com',
            password='old-password',
        )
        reset_token = 'expired-reset-token'
        PasswordResetToken.objects.create(
            player=player,
            token_hash=hashlib.sha256(reset_token.encode()).hexdigest(),
            expires_at=timezone.now() - timedelta(seconds=1),
        )

        response = self.client.post(
            '/api/auth/password-reset/confirm',
            {'token': reset_token, 'password': 'NewSecurePass456'},
            content_type='application/json',
        )

        self.assertEqual(response.status_code, 400)
        player.refresh_from_db()
        self.assertEqual(player.password, 'old-password')

    def test_password_reset_rejects_passwords_over_bcrypt_limit(self):
        player = Player.objects.create(
            name='longpassworduser',
            first_name='Long',
            last_name='Password',
            email='longpassword@example.com',
            password='old-password',
        )
        reset_token = 'long-password-reset-token'
        PasswordResetToken.objects.create(
            player=player,
            token_hash=hashlib.sha256(reset_token.encode()).hexdigest(),
            expires_at=timezone.now() + timedelta(hours=1),
        )

        response = self.client.post(
            '/api/auth/password-reset/confirm',
            {'token': reset_token, 'password': f'NewSecurePass456{"x" * 60}'},
            content_type='application/json',
        )

        self.assertEqual(response.status_code, 400)
        self.assertIn('72 bytes', response.json()['error'])
        self.assertTrue(PasswordResetToken.objects.filter(player=player).exists())

    @patch('nucleo.views_auth.send_mail', side_effect=OSError('SMTP unavailable'))
    def test_password_reset_email_failure_is_logged_without_exposing_account(self, send_mail_mock):
        self.register()

        response = self.client.post(
            '/api/auth/password-reset',
            {'email': 'test@example.com'},
            content_type='application/json',
        )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()['message'], (
            'Si el correo corresponde a una cuenta, recibirás instrucciones para recuperar tu contraseña.'
        ))
        self.assertFalse(PasswordResetToken.objects.exists())
        send_mail_mock.assert_called_once()


class LeaderboardFilterTests(TestCase):
    def setUp(self):
        for score in range(12):
            Player.objects.create(
                name=f'Player{score}',
                first_name='Test',
                last_name='Player',
                email=f'player{score}@example.com',
                score=120 - score,
            )
        Player.objects.create(
            name='Joshua',
            first_name='Joshua',
            last_name='Torres',
            email='joshua@example.com',
            score=1,
        )

    def test_search_is_applied_before_limit_and_limit_is_respected(self):
        filtered = self.client.get('/api/leaderboard?q=Josh&limit=10')
        top_ten = self.client.get('/api/leaderboard?limit=10')
        all_players = self.client.get('/api/leaderboard?limit=all')

        self.assertEqual(filtered.status_code, 200)
        self.assertEqual(filtered.json(), [{'name': 'Joshua', 'score': 1}])
        self.assertEqual(len(top_ten.json()), 10)
        self.assertEqual(len(all_players.json()), 13)
        self.assertEqual(top_ten.json()[0]['score'], 120)
