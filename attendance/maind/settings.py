"""
Django settings for Cobra Coaching project.
"""

from pathlib import Path
import os
import sys

# Build paths inside the project like this: BASE_DIR / 'subdir'.
BASE_DIR = Path(__file__).resolve().parent.parent

# Ensure both BASE_DIR (attendance) and parent (workspace root) are in sys.path
for p in (str(BASE_DIR.parent), str(BASE_DIR)):
    if p not in sys.path:
        sys.path.insert(0, p)


# Simple helper to load key=value from .env without external dependencies
def _load_env_file(env_path):
    if env_path.is_file():
        with open(env_path, 'r', encoding='utf-8') as f:
            for line in f:
                line = line.strip()
                if not line or line.startswith('#') or '=' not in line:
                    continue
                k, v = line.split('=', 1)
                k = k.strip()
                v = v.strip().strip("'\"")
                if k not in os.environ:
                    os.environ[k] = v


_load_env_file(BASE_DIR / '.env')
_load_env_file(BASE_DIR.parent / '.env')

# Quick-start development settings - unsuitable for production
DEBUG = os.environ.get('DJANGO_DEBUG', 'True').strip().lower() in ('true', '1', 'yes')

DEV_SECRET_KEY = 'django-insecure-dev-only-change-me-cobra-coaching-academic-platform'
SECRET_KEY = os.environ.get('SECRET_KEY')

if not SECRET_KEY:
    if DEBUG:
        SECRET_KEY = DEV_SECRET_KEY
    else:
        from django.core.exceptions import ImproperlyConfigured
        raise ImproperlyConfigured("SECRET_KEY environment variable must be set in production mode.")

# ALLOWED_HOSTS configuration
raw_hosts = os.environ.get('ALLOWED_HOSTS', '')
if raw_hosts:
    ALLOWED_HOSTS = [h.strip() for h in raw_hosts.split(',') if h.strip()]
elif DEBUG:
    ALLOWED_HOSTS = ['127.0.0.1', 'localhost', 'testserver']
else:
    from django.core.exceptions import ImproperlyConfigured
    raise ImproperlyConfigured("ALLOWED_HOSTS environment variable must be explicitly configured in production.")


# Application definition

INSTALLED_APPS = [
    'django.contrib.admin',
    'django.contrib.auth',
    'django.contrib.contenttypes',
    'django.contrib.sessions',
    'django.contrib.messages',
    'django.contrib.staticfiles',
    'attendance',
    'grades',
    'learnsphere',
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

ROOT_URLCONF = 'maind.urls'

TEMPLATES = [
    {
        'BACKEND': 'django.template.backends.django.DjangoTemplates',
        'DIRS': [],
        'APP_DIRS': True,
        'OPTIONS': {
            'context_processors': [
                'django.template.context_processors.request',
                'django.contrib.auth.context_processors.auth',
                'django.contrib.messages.context_processors.messages',
                'attendance.context_processors.pending_corrections',
            ],
        },
    },
]

WSGI_APPLICATION = 'maind.wsgi.application'


# Database
# https://docs.djangoproject.com/en/6.0/ref/settings/#databases

DB_ENGINE = os.environ.get('DB_ENGINE', 'django.db.backends.mysql')
DB_NAME = os.environ.get('DB_NAME', 'attendance_db')
DB_USER = os.environ.get('DB_USER', 'root')
DB_PASSWORD = os.environ.get('DB_PASSWORD', '')
DB_HOST = os.environ.get('DB_HOST', '127.0.0.1')
DB_PORT = os.environ.get('DB_PORT', '3306')

if not DEBUG and DB_ENGINE == 'django.db.backends.mysql' and not DB_PASSWORD:
    from django.core.exceptions import ImproperlyConfigured
    raise ImproperlyConfigured("DB_PASSWORD must be configured for MySQL in production mode.")

DATABASES = {
    'default': {
        'ENGINE': DB_ENGINE,
        'NAME': DB_NAME,
        'USER': DB_USER,
        'PASSWORD': DB_PASSWORD,
        'HOST': DB_HOST,
        'PORT': DB_PORT,
        'OPTIONS': {'charset': 'utf8mb4'} if 'mysql' in DB_ENGINE else {},
    }
}

# Custom User model
AUTH_USER_MODEL = 'attendance.User'

AUTHENTICATION_BACKENDS = [
    'attendance.backends.EmailOrUsernameModelBackend',
    'django.contrib.auth.backends.ModelBackend',
]

# The login page is the site root. Role-based routing is handled in RoleLoginView.
LOGIN_URL = '/'
LOGOUT_REDIRECT_URL = '/'


# Password validation
# https://docs.djangoproject.com/en/6.0/ref/settings/#auth-password-validators

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


# Internationalization
# https://docs.djangoproject.com/en/6.0/topics/i18n/

LANGUAGE_CODE = 'en-us'

# Institutional timezone for displayed dates and deadlines
TIME_ZONE = 'Asia/Kolkata'

USE_I18N = True

USE_TZ = True


# Static files (CSS, JavaScript, Images)
# https://docs.djangoproject.com/en/6.0/howto/static-files/

STATIC_URL = 'static/'
STATIC_ROOT = BASE_DIR / 'staticfiles'
STATICFILES_DIRS = [
    BASE_DIR / 'static',
]

# Email configuration (SMTP Gmail via environment variables)
EMAIL_BACKEND = os.environ.get(
    'EMAIL_BACKEND',
    'django.core.mail.backends.smtp.EmailBackend'
).strip()
EMAIL_HOST = os.environ.get('EMAIL_HOST', 'smtp.gmail.com').strip()
EMAIL_PORT = int(os.environ.get('EMAIL_PORT', 587))
EMAIL_HOST_USER = os.environ.get('EMAIL_HOST_USER', 'coachingcobra@gmail.com').strip()
EMAIL_HOST_PASSWORD = os.environ.get('EMAIL_HOST_PASSWORD', '').strip()
EMAIL_USE_TLS = os.environ.get('EMAIL_USE_TLS', 'True').strip().lower() in ('true', '1', 'yes')
EMAIL_USE_SSL = os.environ.get('EMAIL_USE_SSL', 'False').strip().lower() in ('true', '1', 'yes')
DEFAULT_FROM_EMAIL = os.environ.get(
    'DEFAULT_FROM_EMAIL',
    'Cobra Coaching <coachingcobra@gmail.com>'
).strip()
EMAIL_TIMEOUT = int(os.environ.get('EMAIL_TIMEOUT', 20))
APP_BASE_URL = os.environ.get('APP_BASE_URL', '').strip().rstrip('/')

# Attendance Correction system settings
ATTENDANCE_CORRECTION_WINDOW_DAYS = int(os.environ.get('ATTENDANCE_CORRECTION_WINDOW_DAYS', 7))
ATTENDANCE_BATCH_MINUTES = int(os.environ.get('ATTENDANCE_BATCH_MINUTES', 30))
ATTENDANCE_LINK_EXPIRY_HOURS = int(os.environ.get('ATTENDANCE_LINK_EXPIRY_HOURS', 48))
REQUIRE_AUTHENTICATED_REVIEW = os.environ.get('REQUIRE_AUTHENTICATED_REVIEW', 'False').lower() in ('true', '1')
