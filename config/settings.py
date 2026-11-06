"""
Django settings for config project.
"""

from pathlib import Path
import os
import secrets

BASE_DIR = Path(__file__).resolve().parent.parent

# ── Security: SECRET_KEY ──────────────────────────────────────────────────────
# PRODUCTION: Set a strong SECRET_KEY via environment variable.
# NEVER commit a real secret key to source control.
# Generate one with: python -c "import secrets; print(secrets.token_urlsafe(60))"
_default_secret = os.environ.get('DJANGO_SECRET_KEY_DEFAULT', '')
SECRET_KEY = os.environ.get('SECRET_KEY', _default_secret or secrets.token_urlsafe(60))

DEBUG = os.environ.get('DEBUG', 'True') == 'True'

# ── Security: ALLOWED_HOSTS ───────────────────────────────────────────────────
# PRODUCTION: Set ALLOWED_HOSTS env var to your real domain(s).
# e.g. ALLOWED_HOSTS=connectifyu.college.ac.in,www.connectifyu.college.ac.in
_raw_hosts = os.environ.get('ALLOWED_HOSTS', '')
if _raw_hosts:
    ALLOWED_HOSTS = [h.strip() for h in _raw_hosts.split(',') if h.strip()]
elif DEBUG:
    ALLOWED_HOSTS = ['127.0.0.1', 'localhost', '.localhost', '[::1]']
else:
    ALLOWED_HOSTS = ['127.0.0.1', 'localhost']

# ── Accounts: Student signup email domain whitelist ─────────────────────────
# Set in .env as ALLOWED_EMAIL_DOMAINS=college.ac.in,university.ac.in
_raw_domains = os.environ.get('ALLOWED_EMAIL_DOMAINS', 'college.ac.in')
ALLOWED_EMAIL_DOMAINS = [d.strip() for d in _raw_domains.split(',') if d.strip()]

INSTALLED_APPS = [
    'django.contrib.admin',
    'django.contrib.auth',
    'django.contrib.contenttypes',
    'django.contrib.sessions',
    'django.contrib.messages',
    'django.contrib.staticfiles',
    'events',
]

MIDDLEWARE = [
    'django.middleware.security.SecurityMiddleware',
    'django.contrib.sessions.middleware.SessionMiddleware',
    'django.middleware.common.CommonMiddleware',
    'django.middleware.csrf.CsrfViewMiddleware',
    'django.contrib.auth.middleware.AuthenticationMiddleware',
    'django.contrib.messages.middleware.MessageMiddleware',
    'django.middleware.clickjacking.XFrameOptionsMiddleware',
]

ROOT_URLCONF = 'config.urls'

TEMPLATES = [
    {
        'BACKEND': 'django.template.backends.django.DjangoTemplates',
        'DIRS': [BASE_DIR / 'templates'],
        'APP_DIRS': True,
        'OPTIONS': {
            'context_processors': [
                'django.template.context_processors.request',
                'django.contrib.auth.context_processors.auth',
                'django.contrib.messages.context_processors.messages',
                'events.context_processors.demo_roles_processor',
            ],
        },
    },
]

WSGI_APPLICATION = 'config.wsgi.application'

DATABASES = {
    'default': {
        'ENGINE': 'django.db.backends.sqlite3',
        'NAME': BASE_DIR / 'db.sqlite3',
    }
}

AUTH_PASSWORD_VALIDATORS = [
    {
        'NAME': 'django.contrib.auth.password_validation.UserAttributeSimilarityValidator',
    },
    {
        'NAME': 'django.contrib.auth.password_validation.MinimumLengthValidator',
    },
    {
        'NAME': 'django.contrib.auth.password_validation.CommonPasswordValidator',
    },
    {
        'NAME': 'django.contrib.auth.password_validation.NumericPasswordValidator',
    },
]

LANGUAGE_CODE = 'en-us'

TIME_ZONE = 'UTC'

USE_I18N = True

USE_TZ = True

STATIC_URL = '/static/'
STATICFILES_DIRS = [BASE_DIR / 'static']

MEDIA_URL = '/media/'
MEDIA_ROOT = BASE_DIR / 'media'

DEFAULT_AUTO_FIELD = 'django.db.models.BigAutoField'

LOGIN_URL = 'login'
LOGIN_REDIRECT_URL = 'dashboard'
LOGOUT_REDIRECT_URL = 'login'

EMAIL_BACKEND = 'django.core.mail.backends.console.EmailBackend'
DEFAULT_FROM_EMAIL = os.environ.get('DEFAULT_FROM_EMAIL', 'noreply-events@college.ac.in')
