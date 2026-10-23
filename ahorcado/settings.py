import os
import mimetypes

from pathlib import Path
from urllib.parse import urlparse, unquote
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
SESSION_ENGINE = 'django.contrib.sessions.backends.signed_cookies'

SUPABASE_PROJECT_REF = 'vhsqyvppeljmbpizzyjp'
SUPABASE_URL = (
    os.getenv('SUPABASE_URL') or LOCAL_DOTENV.get('SUPABASE_URL')
    or f'https://{SUPABASE_PROJECT_REF}.supabase.co'
).strip().rstrip('/')
SUPABASE_KEY = (os.getenv('SUPABASE_KEY') or LOCAL_DOTENV.get('SUPABASE_KEY') or '').strip()
SUPABASE_DB_PASSWORD = os.getenv('SUPABASE_DB_PASSWORD', '3KWG9xby0A4FLcBf')

DEFAULT_DB_URL = (
    f'postgresql://postgres.{SUPABASE_PROJECT_REF}:{SUPABASE_DB_PASSWORD}'
    f'@aws-0-us-east-1.pooler.supabase.com:6543/postgres?sslmode=require'
)

url = (
    os.getenv('DATABASE_URL') or
    DEFAULT_DB_URL
).strip('"\' \n\r')

if not url or 'izloztttkwcdfrxkqocb' in url or 'ciassthcelqvmjdajnyt' in url:
    url = DEFAULT_DB_URL

parsed = urlparse(url)
is_ssl = (
    'sslmode=require' in (parsed.query or '') or
    'supabase' in (parsed.hostname or '') or
    bool(os.getenv('VERCEL'))
)

DATABASES = {'default': {
    'ENGINE': 'django.db.backends.postgresql',
    'NAME': unquote(parsed.path.lstrip('/')),
    'USER': unquote(parsed.username or ''),
    'PASSWORD': unquote(parsed.password or ''),
    'HOST': parsed.hostname or 'localhost',
    'PORT': parsed.port or 5432,
    'OPTIONS': {'sslmode': 'require' if is_ssl else 'prefer'},
}}

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
