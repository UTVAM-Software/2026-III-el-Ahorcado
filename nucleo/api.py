"""Autenticación JWT y validación JSON compartidas por la API."""
import json
import os
from functools import wraps

import jwt
from django.conf import settings
from django.http import JsonResponse
from django.views.decorators.csrf import csrf_exempt

from .models import Player


def error(message, status=400):
    return JsonResponse({'error': message}, status=status)


def body(request):
    try:
        value = json.loads(request.body or b'{}')
        return value if isinstance(value, dict) else {}
    except (ValueError, UnicodeDecodeError):
        return {}


def integer(value):
    try:
        return int(value)
    except (TypeError, ValueError, OverflowError):
        return None


def id_list(values):
    return list(dict.fromkeys(number for value in values for number in [integer(value)] if number and number > 0)) if isinstance(values, list) else []


def current_player(request):
    header = request.headers.get('Authorization', '')
    if not header.startswith('Bearer '):
        return None
    try:
        payload = jwt.decode(header[7:], os.getenv('JWT_SECRET', settings.SECRET_KEY), algorithms=['HS256'])
        return Player.objects.filter(pk=payload['id']).first()
    except (jwt.PyJWTError, KeyError, TypeError):
        return None


def token_for(player):
    from datetime import datetime, timedelta, timezone
    return jwt.encode({'id': player.id, 'name': player.name, 'role': player.role,
                       'exp': datetime.now(timezone.utc) + timedelta(hours=8)},
                      os.getenv('JWT_SECRET', settings.SECRET_KEY), algorithm='HS256')


from django.db import DatabaseError, OperationalError


def endpoint(methods, auth=False, teacher=False):
    def decorate(view):
        @csrf_exempt
        @wraps(view)
        def wrapper(request, *args, **kwargs):
            if request.method not in methods:
                return error('Método no permitido.', 405)
            try:
                if auth:
                    request.player = current_player(request)
                    if request.player is None:
                        return error('Sesión no válida o expirada.', 401)
                    if teacher and request.player.role != 'teacher':
                        return error('Acceso denegado. Se requiere rol de profesor.', 403)
                return view(request, *args, **kwargs)
            except (OperationalError, DatabaseError):
                return error('La base de datos se encuentra temporalmente inaccesible. Si el proyecto en Supabase está pausado, reanúdalo en el dashboard.', 503)
        return wrapper
    return decorate


def player_data(player):
    return {key: getattr(player, key) for key in ('id', 'name', 'first_name', 'last_name', 'email', 'role', 'score')}


def word_data(word):
    return {key: getattr(word, key) for key in ('id', 'word', 'difficulty', 'theme')}
