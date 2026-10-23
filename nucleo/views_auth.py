import hashlib
import json
import re
import secrets
import smtplib
from datetime import timedelta
from logging import getLogger
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen
from urllib.parse import urlparse

import bcrypt
from django.conf import settings
from django.core.cache import cache
from django.core.exceptions import ValidationError
from django.core.mail import send_mail
from django.core.validators import validate_email
from django.db import IntegrityError, transaction
from django.db.models import Q
from django.http import JsonResponse
from django.utils import timezone
from django.views.decorators.cache import never_cache

from .api import body, endpoint, error, player_data, token_for
from .auth_integration import sync_player_to_django_user
from .models import PasswordResetToken, Player

logger = getLogger(__name__)

PASSWORD_RESET_LIFETIME = timedelta(hours=1)
PASSWORD_RESET_REQUEST_LIMIT = 5
PASSWORD_RESET_CONFIRM_LIMIT = 10
PASSWORD_RESET_RATE_WINDOW = 900
GOOGLE_AUTH_RATE_LIMIT = 10
GOOGLE_AUTH_RATE_WINDOW = 300


def rate_limited(request):
    key = f'login:{request.META.get("REMOTE_ADDR", "unknown")}'
    attempts = cache.get(key, 0)
    if attempts >= 5:
        return True
    return False


def google_auth_rate_limited(request):
    ip = request.META.get('REMOTE_ADDR', 'unknown')
    key = f'google-login:{ip}'
    attempts = cache.get(key, 0)
    if attempts >= GOOGLE_AUTH_RATE_LIMIT:
        return True
    cache.set(key, attempts + 1, GOOGLE_AUTH_RATE_WINDOW)
    return False


def check_password(raw, stored):
    if not isinstance(raw, str):
        return False
    if stored.startswith('$2'):
        return bcrypt.checkpw(raw.encode(), stored.encode())
    return raw == stored


def strong_password(password):
    if len(password) < 12:
        return False
    try:
        if len(password.encode()) > 72:
            return False
    except UnicodeEncodeError:
        return False
    if not re.search(r'[A-Z]', password):
        return False
    if not re.search(r'[a-z]', password):
        return False
    if not re.search(r'\d', password):
        return False
    return True


def password_reset_rate_limited(request, action, limit):
    ip = request.META.get('REMOTE_ADDR', 'unknown')
    key = f'password-reset:{action}:{ip}'
    attempts = cache.get(key, 0)
    if attempts >= limit:
        return True
    if attempts:
        cache.incr(key)
    else:
        cache.add(key, 1, PASSWORD_RESET_RATE_WINDOW)
    return False


@endpoint(['POST'])
def register(request):
    data = body(request)
    name = str(data.get('name') or '').strip()[:30]
    first_name = str(data.get('first_name') or '').strip()[:50]
    last_name = str(data.get('last_name') or '').strip()[:50]
    email = str(data.get('email') or '').strip().lower()
    role = str(data.get('role') or '').strip().lower()
    password = str(data.get('password') or '')
    grade = str(data.get('grade') or '').strip()
    group_name = str(data.get('group_name') or '').strip()
    if not all((name, first_name, last_name, email, password)):
        return error('Todos los campos del formulario son obligatorios.')
    if role not in ('student', 'teacher'):
        return error('Selecciona explícitamente si la cuenta será Alumno o Profesor.')
    if role == 'student' and (not grade or not group_name):
        return error('Los alumnos deben indicar su grado y grupo.')
    if len(grade) > 30 or len(group_name) > 20:
        return error('El grado debe tener hasta 30 caracteres y el grupo hasta 20.')
    if len(email) > 100:
        return error('El correo electrónico no puede superar los 100 caracteres.')
    try:
        validate_email(email)
    except ValidationError:
        return error('El formato del correo electrónico no es válido.')
    if not strong_password(password):
        return error('La contraseña debe tener entre 12 y 72 bytes e incluir mayúsculas, minúsculas y números.')
    try:
        player = Player.objects.create(name=name, first_name=first_name, last_name=last_name,
                                       email=email, role=role,
                                       grade=grade.upper(), group_name=group_name.upper(),
                                       password=bcrypt.hashpw(password.encode(), bcrypt.gensalt()).decode())
        sync_player_to_django_user(player, raw_password=password)
    except IntegrityError:
        return error('El nombre de usuario o el correo electrónico ya están en uso.')
    return JsonResponse({'token': token_for(player), 'user': player_data(player)})


def verify_supabase_access_token(access_token):
    if not settings.SUPABASE_URL or not settings.SUPABASE_KEY:
        return None, 503

    request = Request(
        f'{settings.SUPABASE_URL.rstrip("/")}/auth/v1/user',
        headers={
            'apikey': settings.SUPABASE_KEY,
            'Authorization': f'Bearer {access_token}',
        },
    )
    try:
        with urlopen(request, timeout=8) as response:
            user = json.loads(response.read())
    except HTTPError as exc:
        if exc.code in (400, 401, 403):
            return None, 401
        logger.exception('Supabase rechazó la verificación de identidad.')
        return None, 503
    except (URLError, TimeoutError, OSError, ValueError):
        logger.exception('No se pudo verificar la identidad con Supabase.')
        return None, 503

    if not isinstance(user, dict):
        logger.error('Supabase devolvió un usuario con formato inesperado.')
        return None, 503
    return user, None


@never_cache
@endpoint(['GET'])
def google_auth_config(request):
    configured = (
        bool(settings.SUPABASE_URL and settings.SUPABASE_KEY)
        and settings.SUPABASE_KEY != 'tu_anon_key_publica_de_supabase'
    )
    return JsonResponse({
        'enabled': configured,
        'supabase_url': settings.SUPABASE_URL if configured else '',
        'supabase_key': settings.SUPABASE_KEY if configured else '',
    })


@endpoint(['POST'])
def google_auth(request):
    if google_auth_rate_limited(request):
        return error('Demasiados intentos con Google. Inténtalo de nuevo en unos minutos.', 429)

    data = body(request)
    access_token = str(data.get('access_token') or '').strip()
    if not access_token or len(access_token) > 4096:
        return error('La respuesta de Google no es válida. Inténtalo de nuevo.')

    supabase_user, status = verify_supabase_access_token(access_token)
    if status:
        if status == 401:
            return error('La sesión de Google no es válida o expiró. Inténtalo de nuevo.', 401)
        return error('El inicio de sesión con Google no está disponible por el momento.', 503)

    app_metadata = supabase_user.get('app_metadata')
    app_metadata = app_metadata if isinstance(app_metadata, dict) else {}
    identities = supabase_user.get('identities')
    has_google_identity = (
        isinstance(identities, list)
        and any(isinstance(identity, dict) and identity.get('provider') == 'google' for identity in identities)
    )
    if app_metadata.get('provider') != 'google' and not has_google_identity:
        return error('Esta opción solo permite iniciar sesión con una cuenta de Google.', 401)

    user_id = str(supabase_user.get('id') or '').strip()
    email = str(supabase_user.get('email') or '').strip().lower()
    email_confirmed = supabase_user.get('email_confirmed_at') or supabase_user.get('confirmed_at')
    if not user_id or len(user_id) > 255 or not email or not email_confirmed:
        return error('Google debe confirmar tu correo antes de continuar.', 401)
    if len(email) > 100:
        return error('El correo de Google supera el límite permitido para una cuenta.')
    try:
        validate_email(email)
    except ValidationError:
        return error('Google no devolvió un correo electrónico válido.', 401)

    player = Player.objects.filter(supabase_user_id=user_id).first()
    if player:
        if player.email.lower() != email:
            return error('El correo de esta cuenta de Google cambió. Contacta al administrador.', 409)
        if not player.is_active:
            return error('Esta cuenta está desactivada. Contacta al administrador.', 403)
        sync_player_to_django_user(player)
        cache.delete(f'google-login:{request.META.get("REMOTE_ADDR", "unknown")}')
        return JsonResponse({'token': token_for(player), 'user': player_data(player)})

    if Player.objects.filter(email__iexact=email).exists():
        return error(
            'Ya existe una cuenta con este correo. Inicia sesión con tu método actual; '
            'por seguridad no se vinculan cuentas automáticamente.',
            409,
        )

    metadata = supabase_user.get('user_metadata')
    metadata = metadata if isinstance(metadata, dict) else {}
    full_name = str(metadata.get('full_name') or metadata.get('name') or '').strip()
    name_parts = full_name.split()
    first_name = str(metadata.get('given_name') or '').strip()
    last_name = str(metadata.get('family_name') or '').strip()
    if not first_name:
        first_name = name_parts[0] if name_parts else email.split('@', 1)[0]
    if not last_name and len(name_parts) > 1:
        last_name = ' '.join(name_parts[1:])
    first_name = first_name[:50]
    last_name = (last_name or first_name)[:50]

    if data.get('intent') == 'register' and not data.get('role'):
        return JsonResponse({
            'requires_registration': True,
            'profile': {
                'email': email,
                'first_name': first_name,
                'last_name': last_name,
            },
        })

    if data.get('intent') == 'login' and not data.get('role'):
        return error('No existe una cuenta registrada con esta cuenta de Google. Regístrate primero.', 404)

    role = str(data.get('role') or '').strip().lower()
    grade = str(data.get('grade') or '').strip()
    group_name = str(data.get('group_name') or '').strip()
    if role not in ('student', 'teacher'):
        return error('Selecciona Alumno o Profesor en el formulario de registro.')
    if role == 'student' and (not grade or not group_name):
        return error('Los alumnos deben indicar su grado y grupo.')
    if len(grade) > 30 or len(group_name) > 20:
        return error('El grado debe tener hasta 30 caracteres y el grupo hasta 20.')

    password = str(data.get('password') or '')
    if not strong_password(password):
        return error('La contraseña debe tener entre 12 y 72 bytes e incluir mayúsculas, minúsculas y números.')

    first_name = str(data.get('first_name') or first_name).strip()
    last_name = str(data.get('last_name') or last_name).strip()
    if not first_name or not last_name:
        return error('Completa tu nombre y apellidos para continuar.')
    if len(first_name) > 50 or len(last_name) > 50:
        return error('El nombre y los apellidos no pueden superar los 50 caracteres.')

    username = str(data.get('name') or '').strip()
    if username and not re.fullmatch(r'[a-zA-Z0-9_]{3,30}', username):
        return error('El nombre de usuario debe tener entre 3 y 30 caracteres y usar solo letras, números o guion bajo.')
    if username and Player.objects.filter(name__iexact=username).exists():
        return error('Ese nombre de usuario ya está en uso. Elige otro.')
    if not username:
        username_base = re.sub(r'[^a-zA-Z0-9_]', '', email.split('@', 1)[0]).lower()[:21] or 'google'
        username = f'{username_base}_{secrets.token_hex(4)}'
    hashed_password = bcrypt.hashpw(password.encode(), bcrypt.gensalt()).decode()

    try:
        with transaction.atomic():
            player = Player.objects.create(
                name=username,
                first_name=first_name,
                last_name=last_name,
                email=email,
                supabase_user_id=user_id,
                password=hashed_password,
                role=role,
                grade=grade.upper() if role == 'student' else '',
                group_name=group_name.upper() if role == 'student' else '',
            )
            sync_player_to_django_user(player, raw_password=password)
    except IntegrityError:
        player = Player.objects.filter(supabase_user_id=user_id).first()
        if player and player.email.lower() == email:
            if not player.is_active:
                return error('Esta cuenta está desactivada. Contacta al administrador.', 403)
            sync_player_to_django_user(player)
            cache.delete(f'google-login:{request.META.get("REMOTE_ADDR", "unknown")}')
            return JsonResponse({'token': token_for(player), 'user': player_data(player)})
        if player:
            return error('Esta cuenta de Google ya está vinculada a otro correo. Contacta al administrador.', 409)
        if Player.objects.filter(email__iexact=email).exists():
            return error(
                'Este correo ya tiene una cuenta. Regresa al inicio e inicia sesión con el método usado al registrarte.',
                409,
            )
        if Player.objects.filter(name__iexact=username).exists():
            return error('Ese nombre de usuario acaba de ser ocupado. Elige otro e inténtalo de nuevo.', 409)
        logger.exception('No se pudo crear el perfil vinculado a Google por un conflicto de base de datos.')
        return error('No se pudo guardar el perfil. Inténtalo de nuevo o contacta al administrador.', 409)

    cache.delete(f'google-login:{request.META.get("REMOTE_ADDR", "unknown")}')
    return JsonResponse({'token': token_for(player), 'user': player_data(player)})


@endpoint(['POST'])
def request_password_reset(request):
    if password_reset_rate_limited(request, 'request', PASSWORD_RESET_REQUEST_LIMIT):
        return error('Demasiadas solicitudes. Inténtalo de nuevo más tarde.', 429)

    local_console_email = (
        settings.DEBUG
        and settings.EMAIL_BACKEND == 'django.core.mail.backends.console.EmailBackend'
    )
    public_url = settings.PUBLIC_APP_URL
    if local_console_email and not public_url:
        public_url = request.build_absolute_uri('/').rstrip('/')
    parsed_url = urlparse(public_url)
    if not local_console_email and (not settings.EMAIL_HOST or not settings.DEFAULT_FROM_EMAIL):
        return error('La recuperación no está disponible porque el servicio de correo no está configurado.', 503)
    if parsed_url.scheme not in ('http', 'https') or not parsed_url.netloc:
        return error('La recuperación no está disponible porque el servicio de correo no está configurado.', 503)

    data = body(request)
    email = str(data.get('email') or '').strip().lower()
    if len(email) <= 100:
        try:
            validate_email(email)
        except ValidationError:
            pass
        else:
            player = Player.objects.filter(email=email).first()
            if player:
                token = secrets.token_urlsafe(32)
                token_hash = hashlib.sha256(token.encode()).hexdigest()
                now = timezone.now()
                with transaction.atomic():
                    PasswordResetToken.objects.filter(player=player).delete()
                    reset_request = PasswordResetToken.objects.create(
                        player=player,
                        token_hash=token_hash,
                        expires_at=now + PASSWORD_RESET_LIFETIME,
                    )

                reset_url = f'{public_url.rstrip("/")}/password-recovery.html?token={token}'
                try:
                    send_mail(
                        subject='Recupera tu contraseña de Ahorcado UTVAM',
                        message=(
                            f'Hola {player.first_name},\n\n'
                            'Recibimos una solicitud para cambiar la contraseña de tu cuenta. '
                            'Abre este enlace para elegir una nueva:\n\n'
                            f'{reset_url}\n\n'
                            'El enlace vence en una hora y solo puede utilizarse una vez. '
                            'Si no solicitaste el cambio, puedes ignorar este mensaje.'
                        ),
                        from_email=settings.DEFAULT_FROM_EMAIL,
                        recipient_list=[email],
                        fail_silently=False,
                    )
                except (OSError, smtplib.SMTPException, ValueError):
                    logger.exception('No se pudo enviar el correo de recuperación de contraseña.')
                    PasswordResetToken.objects.filter(pk=reset_request.pk).delete()

    message = 'Si el correo corresponde a una cuenta, recibirás instrucciones para recuperar tu contraseña.'
    if local_console_email:
        message = 'Modo local: si el correo corresponde a una cuenta, el enlace de recuperación aparecerá en la consola del servidor.'
    return JsonResponse({'message': message})


@endpoint(['POST'])
def reset_password(request):
    if password_reset_rate_limited(request, 'confirm', PASSWORD_RESET_CONFIRM_LIMIT):
        return error('Demasiados intentos. Inténtalo de nuevo más tarde.', 429)

    data = body(request)
    token = str(data.get('token') or '').strip()
    password = str(data.get('password') or '')
    if not token or len(token) > 200:
        return error('El enlace de recuperación no es válido o ya fue utilizado.')
    if not strong_password(password):
        return error('La contraseña debe tener entre 12 y 72 bytes e incluir mayúsculas, minúsculas y números.')

    token_hash = hashlib.sha256(token.encode()).hexdigest()
    with transaction.atomic():
        reset_request = (
            PasswordResetToken.objects.select_for_update()
            .select_related('player')
            .filter(token_hash=token_hash, expires_at__gt=timezone.now())
            .first()
        )
        if not reset_request:
            return error('El enlace de recuperación no es válido, venció o ya fue utilizado.')

        player = reset_request.player
        player.password = bcrypt.hashpw(password.encode(), bcrypt.gensalt()).decode()
        player.save(update_fields=['password'])
        sync_player_to_django_user(player, raw_password=password)
        PasswordResetToken.objects.filter(player=player).delete()

    return JsonResponse({'message': 'Tu contraseña se actualizó correctamente. Ya puedes iniciar sesión.'})


@endpoint(['POST'])
def login(request):
    data = body(request)
    credential = str(data.get('credential') or data.get('name') or data.get('username') or data.get('email') or '').strip()[:100]
    password = str(data.get('password') or '')
    if not credential or not password:
        return error('El usuario/correo y la contraseña son obligatorios.')
    ip_key = f'login:{request.META.get("REMOTE_ADDR", "unknown")}'
    if rate_limited(request):
        return error('Demasiados intentos. Intenta nuevamente en unos minutos.', 429)
    player = Player.objects.filter(Q(name=credential) | Q(email=credential.lower())).first()
    if not player or not player.is_active:
        attempts = cache.get(ip_key, 0) + 1
        cache.set(ip_key, attempts, 300)
        return error('Credenciales incorrectas. Por favor, verifica tu usuario y contraseña.', 401)
    django_user = player.django_user if player.django_user_id else None
    password_valid = check_password(password, player.password) or bool(
        django_user and django_user.is_active and django_user.check_password(password)
    )
    if not password_valid:
        attempts = cache.get(ip_key, 0) + 1
        cache.set(ip_key, attempts, 300)
        return error('Credenciales incorrectas. Por favor, verifica tu usuario y contraseña.', 401)
    cache.delete(ip_key)
    if not player.password.startswith('$2') or not check_password(password, player.password):
        player.password = bcrypt.hashpw(password.encode(), bcrypt.gensalt()).decode()
        player.save(update_fields=['password'])
    sync_player_to_django_user(player, raw_password=password)
    return JsonResponse({'token': token_for(player), 'user': player_data(player)})


@endpoint(['DELETE'], auth=True)
def account(request):
    password = str(body(request).get('password') or '')
    if not password:
        return error('Ingresa tu contraseña para eliminar la cuenta.')
    if not check_password(password, request.player.password):
        return error('Contraseña incorrecta.', 401)
    with transaction.atomic():
        if request.player.django_user_id:
            request.player.django_user.delete()
        else:
            request.player.delete()
    return JsonResponse({'message': 'Cuenta eliminada permanentemente.'})
