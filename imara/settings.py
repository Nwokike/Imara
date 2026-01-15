import os
from pathlib import Path
from dotenv import load_dotenv
import dj_database_url
from django.core.exceptions import ImproperlyConfigured

load_dotenv()

BASE_DIR = Path(__file__).resolve().parent.parent

# Security: This should be False in your .env for production
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
    # Get hosts from env, default to safe list
    env_hosts = os.environ.get('ALLOWED_HOSTS', '').split(',')
    ALLOWED_HOSTS = [host.strip() for host in env_hosts if host.strip()]
    if not ALLOWED_HOSTS:
        ALLOWED_HOSTS = ['localhost', '127.0.0.1', 'imara.africa', 'www.imara.africa', '35.209.14.56']

# CSRF Protection: Allow forms to work on your domain
CSRF_TRUSTED_ORIGINS = [
    'https://imara.africa',
    'https://www.imara.africa',
]
# Add configured allowed hosts to trusted origins
for host in ALLOWED_HOSTS:
    if host not in ['*', 'localhost', '127.0.0.1']:
        if not host.startswith('http'):
            CSRF_TRUSTED_ORIGINS.append(f'https://{host}')

INSTALLED_APPS = [
    'django.contrib.admin',
    'django.contrib.auth',
    'django.contrib.contenttypes',
    'django.contrib.sessions',
    'django.contrib.messages',
    'django.contrib.staticfiles',
    # Your Apps
    'cases.apps.CasesConfig',
    'directory.apps.DirectoryConfig',
    'dispatch.apps.DispatchConfig',
    'intake.apps.IntakeConfig',
    'triage.apps.TriageConfig',
    'partners.apps.PartnersConfig',
    'publications.apps.PublicationsConfig',
    # Third-party
    'django_editorjs2',
    'django_huey',
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

# Database: Configured via DATABASE_URL
# Default to SQLite if not provided (Local Dev / Simple Prod)
DATABASES = {
    'default': dj_database_url.config(
        default=f"sqlite:///{BASE_DIR / 'db.sqlite3'}",
        conn_max_age=600,
        conn_health_checks=True,
    )
}

# SQLite Optimization: Enable WAL Mode (Only if using SQLite)
from django.db.backends.signals import connection_created
from django.dispatch import receiver

@receiver(connection_created)
def configure_sqlite_pragmas(sender, connection, **kwargs):
    """Enable WAL mode for better concurrency on SQLite"""
    if connection.vendor == 'sqlite':
        cursor = connection.cursor()
        cursor.execute('PRAGMA journal_mode=WAL;')
        cursor.execute('PRAGMA synchronous=NORMAL;')


AUTH_PASSWORD_VALIDATORS = [
    {'NAME': 'django.contrib.auth.password_validation.UserAttributeSimilarityValidator'},
    {'NAME': 'django.contrib.auth.password_validation.MinimumLengthValidator'},
    {'NAME': 'django.contrib.auth.password_validation.CommonPasswordValidator'},
    {'NAME': 'django.contrib.auth.password_validation.NumericPasswordValidator'},
]

LANGUAGE_CODE = 'en-us'
TIME_ZONE = 'UTC'
USE_I18N = True
USE_TZ = True

# Static Files (CSS/JS)
STATIC_URL = '/static/'
STATICFILES_DIRS = [BASE_DIR / 'static']
STATIC_ROOT = BASE_DIR / 'staticfiles'

# Storage Configuration: S3 (R2) for Media, Whitenoise for Static
STORAGES = {
    "default": {
        "BACKEND": "storages.backends.s3boto3.S3Boto3Storage",
        "OPTIONS": {
            "access_key": os.environ.get("R2_ACCESS_KEY_ID"),
            "secret_key": os.environ.get("R2_SECRET_ACCESS_KEY"),
            "bucket_name": os.environ.get("R2_BUCKET_NAME"),
            "endpoint_url": os.environ.get("R2_ENDPOINT_URL"),
            "custom_domain": os.environ.get("R2_CUSTOM_DOMAIN"),
            "file_overwrite": False,
        },
    },
    "staticfiles": {
        # Use CompressedStaticFilesStorage instead of CompressedManifestStaticFilesStorage
        "BACKEND": "whitenoise.storage.CompressedStaticFilesStorage",
    },
}

# Django Huey Configuration (Task Queue)
DJANGO_HUEY = {
    'default': 'dispatch',
    'queues': {
        'dispatch': {
            'huey_class': 'huey.SqliteHuey',
            'filename': BASE_DIR / 'huey.sqlite3',
            'immediate': DEBUG,  # Run synchronously in debug
        }
    }
}

MEDIA_URL = '/media/'
MEDIA_ROOT = BASE_DIR / 'media'

# File upload limits (for 1GB RAM VM)
DATA_UPLOAD_MAX_MEMORY_SIZE = 10 * 1024 * 1024  # 10MB max
FILE_UPLOAD_MAX_MEMORY_SIZE = 5 * 1024 * 1024   # 5MB before temp file

DEFAULT_AUTO_FIELD = 'django.db.models.BigAutoField'

# API Keys
GROQ_API_KEY = os.environ.get('GROQ_API_KEY')
GEMINI_API_KEY = os.environ.get('GEMINI_API_KEY')
BREVO_API_KEY = os.environ.get('BREVO_API_KEY')
TELEGRAM_BOT_TOKEN = os.environ.get('TELEGRAM_BOT_TOKEN')

# Cloudflare Turnstile (CAPTCHA)
TURNSTILE_SITE_KEY = os.environ.get('TURNSTILE_SITE_KEY', '0x4AAAAAACLro269PpnXFjvn')
TURNSTILE_SECRET_KEY = os.environ.get('TURNSTILE_SECRET_KEY', '0x4AAAAAACLro_e5H4S0hE74xyZK-9NVTEQ')

# Security Settings for Production
if not DEBUG:
    SECURE_PROXY_SSL_HEADER = ('HTTP_X_FORWARDED_PROTO', 'https')
    SECURE_SSL_REDIRECT = True
    SESSION_COOKIE_SECURE = True
    CSRF_COOKIE_SECURE = True
    SECURE_HSTS_SECONDS = 31536000
    SECURE_HSTS_INCLUDE_SUBDOMAINS = True
    SECURE_HSTS_PRELOAD = True
    SECURE_CONTENT_TYPE_NOSNIFF = True
    X_FRAME_OPTIONS = 'DENY'

LOGGING = {
    'version': 1,
    'disable_existing_loggers': False,
    'formatters': {
        'verbose': {
            'format': '{levelname} {asctime} {module} {message}',
            'style': '{',
        },
    },
    'handlers': {
        'console': {
            'class': 'logging.StreamHandler',
            'formatter': 'verbose',
        },
    },
    'root': {
        'handlers': ['console'],
        'level': 'INFO',
    },
    'loggers': {
        'django': {
            'handlers': ['console'],
            'level': os.environ.get('DJANGO_LOG_LEVEL', 'INFO'),
            'propagate': False,
        },
        'intake': {
            'handlers': ['console'],
            'level': 'DEBUG' if DEBUG else 'INFO',
            'propagate': False,
        },
        'triage': {
            'handlers': ['console'],
            'level': 'DEBUG' if DEBUG else 'INFO',
            'propagate': False,
        },
        'dispatch': {
            'handlers': ['console'],
            'level': 'DEBUG' if DEBUG else 'INFO',
            'propagate': False,
        },
    },
}
