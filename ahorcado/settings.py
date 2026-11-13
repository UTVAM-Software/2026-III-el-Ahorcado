import json
import mimetypes
import os

from pathlib import Path
from urllib.parse import parse_qs, unquote, urlparse
from dotenv import dotenv_values, load_dotenv

BASE_DIR = Path(__file__).resolve().parent.parent
if not os.getenv('VERCEL'):
    dotenv_path = BASE_DIR / '.env'
    load_dotenv(dotenv_path)
    LOCAL_DOTENV = dotenv_values(dotenv_path)
else:
    LOCAL_DOTENV = {}
mimetypes.add_type("text/javascript", ".mjs")

SECRET_KEY = os.getenv('DJANGO_SECRET_KEY', os.getenv('JWT_SECRET', ''))
if not SECRET_KEY:
    raise RuntimeError('Configura DJANGO_SECRET_KEY (o JWT_SECRET).')
DEBUG = os.getenv('DEBUG', '').lower() == 'true'
ALLOWED_HOSTS = [host.strip() for host in os.getenv('ALLOWED_HOSTS', 'localhost,127.0.0.1').split(',') if host.strip()]
if '.vercel.app' not in ALLOWED_HOSTS:
    ALLOWED_HOSTS.extend(['.vercel.app', 'localhost', '127.0.0.1', '*'])

CSRF_TRUSTED_ORIGINS = [origin.strip() for origin in os.getenv('CSRF_TRUSTED_ORIGINS', '').split(',') if origin.strip()]
CSRF_TRUSTED_ORIGINS.extend(['https://*.vercel.app', 'https://*.now.sh', 'http://localhost:4000', 'http://127.0.0.1:4000'])
WHITENOISE_USE_FINDERS = True
INSTALLED_APPS = [
    'django.contrib.auth',
    'django.contrib.contenttypes',
    'django.contrib.sessions',
    'django.contrib.messages',
    'django.contrib.staticfiles',
    'nucleo.apps.CoreConfig',
]
MIDDLEWARE = [
    'django.middleware.security.SecurityMiddleware',
    'whitenoise.middleware.WhiteNoiseMiddleware',
    'nucleo.middleware.SecurityHeadersMiddleware',
    'django.contrib.sessions.middleware.SessionMiddleware',
    'django.middleware.common.CommonMiddleware',
    'django.middleware.csrf.CsrfViewMiddleware',
    'django.contrib.auth.middleware.AuthenticationMiddleware',
    'django.contrib.messages.middleware.MessageMiddleware',
    'django.middleware.clickjacking.XFrameOptionsMiddleware',
]
ROOT_URLCONF = 'ahorcado.urls'
TEMPLATES = [
    {
        'BACKEND': 'django.template.backends.django.DjangoTemplates',
        'DIRS': [BASE_DIR / 'templates'],
        'APP_DIRS': True,
        'OPTIONS': {
            'context_processors': [
                'django.template.context_processors.debug',
                'django.template.context_processors.request',
                'django.contrib.auth.context_processors.auth',
                'django.contrib.messages.context_processors.messages',
            ],
        },
    },
]
WSGI_APPLICATION = 'ahorcado.wsgi.application'
ASGI_APPLICATION = 'ahorcado.asgi.application'
LOGIN_URL = '/gestion/login/'
LOGIN_REDIRECT_URL = '/gestion/'
LOGOUT_REDIRECT_URL = '/gestion/login/'
AUTH_PASSWORD_VALIDATORS = [
    {'NAME': 'django.contrib.auth.password_validation.UserAttributeSimilarityValidator'},
    {'NAME': 'django.contrib.auth.password_validation.MinimumLengthValidator'},
    {'NAME': 'django.contrib.auth.password_validation.CommonPasswordValidator'},
    {'NAME': 'django.contrib.auth.password_validation.NumericPasswordValidator'},
]
AUTHENTICATION_BACKENDS = [
    'nucleo.auth_backends.PlayerAuthBackend',
    'django.contrib.auth.backends.ModelBackend',
]
SESSION_ENGINE = 'django.contrib.sessions.backends.signed_cookies'


def setting(name, default=''):
    return os.getenv(name) or LOCAL_DOTENV.get(name) or default


database_engine_setting = setting('DB_ENGINE').strip()
database_url = setting('DATABASE_URL').strip('"\' \n\r')
if database_url and not database_engine_setting:
    parsed = urlparse(database_url)
    scheme = parsed.scheme.lower()
    database_backends = {
        'postgres': 'django.db.backends.postgresql',
        'postgresql': 'django.db.backends.postgresql',
        'mysql': 'django.db.backends.mysql',
        'oracle': 'django.db.backends.oracle',
    }

    if scheme == 'sqlite':
        database_name = unquote(parsed.path)
        if parsed.netloc:
            database_name = f'{parsed.netloc}{database_name}'
        elif database_name.startswith('//'):
            database_name = database_name[1:]
        elif database_name.startswith('/'):
            database_name = database_name[1:]
        if database_name != ':memory:' and not Path(database_name).is_absolute():
            database_name = str(BASE_DIR / database_name)
        DATABASES = {'default': {
            'ENGINE': 'django.db.backends.sqlite3',
            'NAME': database_name or str(BASE_DIR / 'db.sqlite3'),
        }}
    elif scheme in database_backends:
        database = {
            'ENGINE': database_backends[scheme],
            'NAME': unquote(parsed.path.lstrip('/')),
            'USER': unquote(parsed.username or ''),
            'PASSWORD': unquote(parsed.password or ''),
            'HOST': parsed.hostname or '',
            'PORT': parsed.port or '',
        }
        if scheme in ('postgres', 'postgresql'):
            sslmode = parse_qs(parsed.query).get('sslmode', [None])[0]
            if sslmode:
                database['OPTIONS'] = {'sslmode': sslmode}
            elif os.getenv('VERCEL') or 'supabase' in (parsed.hostname or ''):
                database['OPTIONS'] = {'sslmode': 'require'}
        DATABASES = {'default': database}
    else:
        raise ValueError(f'Esquema de DATABASE_URL no compatible: {scheme or "(vacío)"}')
else:
    engine_aliases = {
        'sqlite': 'sqlite3',
        'postgres': 'postgresql',
        'postgresql': 'postgresql',
        'mysql': 'mysql',
        'oracle': 'oracle',
    }
    configured_engine = database_engine_setting.lower()
    database_engine = engine_aliases.get(configured_engine, configured_engine)
    if not database_engine:
        database_engine = 'django.db.backends.sqlite3'
    elif '.' not in database_engine:
        database_engine = f'django.db.backends.{database_engine}'
    database_name = setting('DB_NAME', 'db.sqlite3' if database_engine == 'django.db.backends.sqlite3' else '')
    if not database_name:
        raise RuntimeError('Configura DB_NAME para el motor de base de datos seleccionado.')
    if database_engine == 'django.db.backends.sqlite3' and database_name != ':memory:':
        if not Path(database_name).is_absolute():
            database_name = str(BASE_DIR / database_name)

    database = {
        'ENGINE': database_engine,
        'NAME': database_name,
        'USER': setting('DB_USER'),
        'PASSWORD': setting('DB_PASSWORD'),
        'HOST': setting('DB_HOST'),
        'PORT': setting('DB_PORT'),
    }
    database_options = json.loads(setting('DB_OPTIONS', '{}'))
    if not isinstance(database_options, dict):
        raise ValueError('DB_OPTIONS debe contener un objeto JSON.')
    if database_options:
        database['OPTIONS'] = database_options
    DATABASES = {'default': database}

SUPABASE_URL = (
    setting('SUPABASE_URL') or 'https://vhsqyvppeljmbpizzyjp.supabase.co'
).strip().rstrip('/')
SUPABASE_KEY = setting('SUPABASE_KEY').strip()

STATIC_URL = '/static/'
STATICFILES_DIRS = [BASE_DIR / 'interfaz']
STATIC_ROOT = BASE_DIR / 'archivos_estaticos'
STORAGES = {'staticfiles': {'BACKEND': 'whitenoise.storage.CompressedManifestStaticFilesStorage'}}
DEFAULT_AUTO_FIELD = 'django.db.models.AutoField'
USE_TZ = True
TIME_ZONE = 'America/Mexico_City'
EMAIL_BACKEND = os.getenv(
    'EMAIL_BACKEND',
    'django.core.mail.backends.console.EmailBackend'
    if DEBUG and not os.getenv('EMAIL_HOST')
    else 'django.core.mail.backends.smtp.EmailBackend',
)
EMAIL_HOST = os.getenv('EMAIL_HOST', '')
EMAIL_PORT = int(os.getenv('EMAIL_PORT', '587'))
EMAIL_HOST_USER = os.getenv('EMAIL_HOST_USER', '')
EMAIL_HOST_PASSWORD = os.getenv('EMAIL_HOST_PASSWORD', '')
EMAIL_USE_TLS = os.getenv('EMAIL_USE_TLS', 'true').lower() == 'true'
EMAIL_USE_SSL = os.getenv('EMAIL_USE_SSL', 'false').lower() == 'true'
DEFAULT_FROM_EMAIL = os.getenv('DEFAULT_FROM_EMAIL', EMAIL_HOST_USER)
EMAIL_TIMEOUT = int(os.getenv('EMAIL_TIMEOUT', '10'))
PUBLIC_APP_URL = os.getenv('PUBLIC_APP_URL', '').rstrip('/')
SECURE_CONTENT_TYPE_NOSNIFF = True
SECURE_REFERRER_POLICY = 'strict-origin-when-cross-origin'
X_FRAME_OPTIONS = 'DENY'
SESSION_COOKIE_SECURE = not DEBUG
SESSION_COOKIE_HTTPONLY = True
SESSION_COOKIE_SAMESITE = 'Lax'
CSRF_COOKIE_SECURE = not DEBUG
CSRF_COOKIE_HTTPONLY = True
CSRF_COOKIE_SAMESITE = 'Lax'
SECURE_SSL_REDIRECT = os.getenv('SECURE_SSL_REDIRECT', '').lower() == 'true'
SECURE_BROWSER_XSS_FILTER = True
SECURE_CONTENT_TYPE_NOSNIFF = True
SECURE_REFERRER_POLICY = 'strict-origin-when-cross-origin'
SECURE_HSTS_SECONDS = 31536000 if not DEBUG else 0
SECURE_HSTS_INCLUDE_SUBDOMAINS = not DEBUG
SECURE_HSTS_PRELOAD = not DEBUG
SECURE_PROXY_SSL_HEADER = ('HTTP_X_FORWARDED_PROTO', 'https')
