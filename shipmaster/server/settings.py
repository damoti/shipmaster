import os
import sys

CELERY_TASK_SERIALIZER = "json"
CELERY_RESULT_SERIALIZER = "json"
CELERY_ACCEPT_CONTENT = ["json"]
BROKER_URL = 'amqp://guest:guest@rabbitmq:5672//'
CHANNEL_LAYERS = {
    "default": {
        "BACKEND": "asgi_ipc.IPCChannelLayer",
        "ROUTING": "shipmaster.server.routing.channel_routing",
        "CONFIG": {
            "prefix": "shipmaster",
        },
    },
}

# Build paths inside the project like this: os.path.join(BASE_DIR, ...)
BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

SHIPMASTER_DATA = "/var/lib/shipmaster"

# SECURITY WARNING: keep the secret key used in production secret!
SECRET_KEY = '*z_fl)u0=5ovn-v2gp)c!=f6kux^da)h()-7y)f!7odle_+w=5'

AUTH_USER_MODEL = 'server.User'
LOGIN_URL = 'login'

# SECURITY WARNING: don't run with debug turned on in production!
DEBUG = os.environ.get('DEBUG', False)

ALLOWED_HOSTS = []


# Application definition

INSTALLED_APPS = [
    'django.contrib.admin',
    'django.contrib.auth',
    'django.contrib.contenttypes',
    'django.contrib.sessions',
    'django.contrib.messages',
    'django.contrib.staticfiles',
    'django_dartium',
    'bootstrapform',
    'channels',
    'shipmaster.server'
]

MIDDLEWARE_CLASSES = [
    'django.middleware.security.SecurityMiddleware',
    'django.contrib.sessions.middleware.SessionMiddleware',
    'django.middleware.common.CommonMiddleware',
    'django.middleware.csrf.CsrfViewMiddleware',
    'django.contrib.auth.middleware.AuthenticationMiddleware',
    'django.contrib.messages.middleware.MessageMiddleware',
    'django.middleware.clickjacking.XFrameOptionsMiddleware',
    'django_dartium.middleware.DartiumDetectionMiddleware',
    'shipmaster.server.middleware.ShipmasterMiddleware'
]

AUTHENTICATION_BACKENDS = [
    'django.contrib.auth.backends.ModelBackend',
]
GITHUB_ORG = os.environ.get('GITHUB_ORG')
OAUTH_KEY = os.environ.get('OAUTH_KEY')  # Client ID
OAUTH_SECRET = os.environ.get('OAUTH_SECRET')  # Client Secret

ROOT_URLCONF = 'shipmaster.server.urls'

TEMPLATES = [
    {
        'BACKEND': 'django.template.backends.django.DjangoTemplates',
        'DIRS': [],
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

WSGI_APPLICATION = 'shipmaster.server.wsgi.application'


# Database
# https://docs.djangoproject.com/en/1.9/ref/settings/#databases

DATABASES = {
    'default': {
        'ENGINE': 'django.db.backends.sqlite3',
        'NAME': os.path.join(BASE_DIR, 'db.sqlite3'),
    }
}


# Password validation
# https://docs.djangoproject.com/en/1.9/ref/settings/#auth-password-validators

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
# https://docs.djangoproject.com/en/1.9/topics/i18n/

LANGUAGE_CODE = 'en-us'

TIME_ZONE = 'UTC'

USE_I18N = True

USE_L10N = True

USE_TZ = True


# Static files (CSS, JavaScript, Images)
# https://docs.djangoproject.com/en/1.9/howto/static-files/

# this is where files are copied when running ./manage.py collectstatic
STATIC_ROOT = os.path.normpath(os.path.join(BASE_DIR, '..', 'static'))
STATIC_URL = '/static/'

STATICFILES_DIRS = [
    ('', 'shipmaster/server/static'),
    ('dart/build', 'shipmaster/dart/build/web'),
    ('dart/src', 'shipmaster/dart/web'),
]
