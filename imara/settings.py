import os
from pathlib import Path
import dj_database_url
from django.core.exceptions import ImproperlyConfigured

BASE_DIR = Path(__file__).resolve().parent.parent

# Security: This should be False in your .env for production
# UV handles environment loading automatically in 2026
DEBUG = os.environ.get('DEBUG', 'False').lower() == 'true'

# Security: Always keep secret key in .env - REQUIRED in production
SECRET_KEY = os.environ.get('SECRET_KEY')
if not SECRET_KEY:
    if DEBUG:
        SECRET_KEY = 'django-dev-key-for-local-development-only'
    else:
        raise ImproperlyConfigured("SECRET_KEY environment variable is required in production")

# ALLOWED_HOSTS: Dynamic configuration
if DEBUG:
    ALLOWED_HOSTS = ['*']
else:
    env_hosts = os.environ.get('ALLOWED_HOSTS', '').split(',')
    ALLOWED_HOSTS = [host.strip() for host in env_hosts if host.strip()]
    if not ALLOWED_HOSTS:
        ALLOWED_HOSTS = ['localhost', '127.0.0.1', 'imara.africa', 'www.imara.africa']

# CSRF Protection
CSRF_TRUSTED_ORIGINS = ['https://imara.africa', 'https://www.imara.africa']
for host in ALLOWED_HOSTS:
    if host not in ['*', 'localhost', '127.0.0.1'] and not host.startswith('http'):
        CSRF_TRUSTED_ORIGINS.append(f'https://{host}')

INSTALLED_APPS = [
    'django.contrib.admin',
    'django.contrib.auth',
    'django.contrib.contenttypes',
    'django.contrib.sessions',
    'django.contrib.messages',
    'django.contrib.staticfiles',
    'django.contrib.sitemaps',
    # Your Apps
    'cases.apps.CasesConfig',
    'dispatch.apps.DispatchConfig',
    'intake.apps.IntakeConfig',
    'triage.apps.TriageConfig',
    'partners.apps.PartnersConfig',
    'publications.apps.PublicationsConfig',
    'django_tasks_db',
]

MIDDLEWARE = [
    'django.middleware.security.SecurityMiddleware',
    'whitenoise.middleware.WhiteNoiseMiddleware',
    'django.contrib.sessions.middleware.SessionMiddleware',
    'django.middleware.common.CommonMiddleware',
    'django.middleware.csrf.CsrfViewMiddleware',
    'django.contrib.auth.middleware.AuthenticationMiddleware',
    'django.contrib.messages.middleware.MessageMiddleware',
    'django.middleware.clickjacking.XFrameOptionsMiddleware',
]

ROOT_URLCONF = 'imara.urls'

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
                'imara.context_processors.turnstile_context',
            ],
        },
    },
]

WSGI_APPLICATION = 'imara.wsgi.application'
ASGI_APPLICATION = 'imara.asgi.application'

# Database
DATABASES = {
    'default': dj_database_url.config(
        default=f"sqlite:///{BASE_DIR / 'db.sqlite3'}",
        conn_max_age=600,
        conn_health_checks=True,
    )
}

# SQLite Optimization (1GB RAM tuned)
from django.db.backends.signals import connection_created
from django.dispatch import receiver

@receiver(connection_created)
def configure_sqlite_pragmas(sender, connection, **kwargs):
    if connection.vendor == 'sqlite':
        cursor = connection.cursor()
        cursor.execute('PRAGMA journal_mode=WAL;')
        cursor.execute('PRAGMA synchronous=NORMAL;')
        cursor.execute('PRAGMA busy_timeout=5000;')
        cursor.execute('PRAGMA mmap_size=134217728;')

# Django 6 Native Tasks
TASKS = {
    'default': {
        'BACKEND': 'django_tasks_db.backend.DatabaseBackend',
    },
}

AUTH_PASSWORD_VALIDATORS = [
    {'NAME': 'django.contrib.auth.password_validation.UserAttributeSimilarityValidator'},
    {'NAME': 'django.contrib.auth.password_validation.MinimumLengthValidator'},
    {'NAME': 'django.contrib.auth.password_validation.CommonPasswordValidator'},
    {'NAME': 'django.contrib.auth.password_validation.NumericPasswordValidator'},
]

AUTHENTICATION_BACKENDS = [
    'utils.auth.EmailOrUsernameBackend',
    'django.contrib.auth.backends.ModelBackend',
]

LANGUAGE_CODE = 'en-us'
TIME_ZONE = 'UTC'
USE_I18N = True
USE_TZ = True

STATIC_URL = '/static/'
STATICFILES_DIRS = [BASE_DIR / 'static']
STATIC_ROOT = BASE_DIR / 'staticfiles'

STORAGES = {
    "default": {
        "BACKEND": "django.core.files.storage.FileSystemStorage",
    },
    "staticfiles": {
        "BACKEND": "whitenoise.storage.CompressedManifestStaticFilesStorage",
    },
}

# Retention & Upload Limits
DATA_UPLOAD_MAX_MEMORY_SIZE = 10 * 1024 * 1024
FILE_UPLOAD_MAX_MEMORY_SIZE = 5 * 1024 * 1024
TRIAGE_MESSAGE_RETENTION_DAYS = int(os.environ.get('TRIAGE_MESSAGE_RETENTION_DAYS', '90'))

DEFAULT_AUTO_FIELD = 'django.db.models.BigAutoField'

# API Keys (Loaded from OS environment by UV)
GROQ_API_KEY = os.environ.get('GROQ_API_KEY')
GEMINI_API_KEY = os.environ.get('GEMINI_API_KEY')
BREVO_API_KEY = os.environ.get('BREVO_API_KEY')
BREVO_SENDER_EMAIL = os.environ.get('BREVO_SENDER_EMAIL', 'imara-alerts@projectimara.org')
ADMIN_NOTIFICATION_EMAIL = os.environ.get('ADMIN_NOTIFICATION_EMAIL', 'projectimarahq@gmail.com')
TURNSTILE_SITE_KEY = os.environ.get('TURNSTILE_SITE_KEY', '')
TURNSTILE_SECRET_KEY = os.environ.get('TURNSTILE_SECRET_KEY', '')

# Platform Integration
TELEGRAM_BOT_TOKEN = os.environ.get('TELEGRAM_BOT_TOKEN')
TELEGRAM_SECRET_TOKEN = os.environ.get('TELEGRAM_SECRET_TOKEN')
META_APP_SECRET = os.environ.get('META_APP_SECRET')
META_PAGE_ACCESS_TOKEN = os.environ.get('META_PAGE_ACCESS_TOKEN')
META_VERIFY_TOKEN = os.environ.get('META_VERIFY_TOKEN')

LOGGING = {
    'version': 1,
    'disable_existing_loggers': False,
    'formatters': {'verbose': {'format': '{levelname} {asctime} {module} {message}', 'style': '{'}},
    'handlers': {'console': {'class': 'logging.StreamHandler', 'formatter': 'verbose'}},
    'root': {'handlers': ['console'], 'level': 'INFO'},
}
