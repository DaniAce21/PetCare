"""Configuración exclusivamente PostgreSQL. .env nunca se versiona."""
import os
from pathlib import Path
from django.core.exceptions import ImproperlyConfigured
from dotenv import load_dotenv

BASE_DIR = Path(__file__).resolve().parent.parent
load_dotenv(BASE_DIR / '.env')
def boolean(name, default=False):
    return os.getenv(name, str(default)).lower() in ('1', 'true', 'yes')
DEBUG = boolean('DEBUG')
SECRET_KEY = os.getenv('SECRET_KEY', '')
if len(SECRET_KEY) < 50:
    raise ImproperlyConfigured('Configura SECRET_KEY con al menos 50 caracteres en .env.')
ALLOWED_HOSTS = [v.strip() for v in os.getenv('ALLOWED_HOSTS', 'localhost,127.0.0.1').split(',') if v.strip()]
INSTALLED_APPS = ['django.contrib.admin','django.contrib.auth','django.contrib.contenttypes',
                  'django.contrib.sessions','django.contrib.messages','django.contrib.staticfiles',
                  'django.contrib.postgres','rest_framework','clinica.apps.ClinicaConfig']
MIDDLEWARE = ['django.middleware.security.SecurityMiddleware','django.contrib.sessions.middleware.SessionMiddleware',
              'django.middleware.common.CommonMiddleware','django.middleware.csrf.CsrfViewMiddleware',
              'django.contrib.auth.middleware.AuthenticationMiddleware','django.contrib.messages.middleware.MessageMiddleware',
              'django.middleware.clickjacking.XFrameOptionsMiddleware','clinica.middleware.SecurityGate']
ROOT_URLCONF = 'petcare.urls'
TEMPLATES = [{'BACKEND':'django.template.backends.django.DjangoTemplates','DIRS':[BASE_DIR/'templates'],
              'APP_DIRS':True,'OPTIONS':{'context_processors':['django.template.context_processors.request',
              'django.contrib.auth.context_processors.auth','django.contrib.messages.context_processors.messages']}}]
WSGI_APPLICATION = 'petcare.wsgi.application'
DATABASES = {'default': {'ENGINE':'django.db.backends.postgresql', 'NAME':os.getenv('DB_NAME','petcare'),
             'USER':os.getenv('DB_USER','petcare'), 'PASSWORD':os.getenv('DB_PASSWORD',''),
             'HOST':os.getenv('DB_HOST','127.0.0.1'), 'PORT':os.getenv('DB_PORT','5432'),
             'CONN_MAX_AGE':60, 'OPTIONS':{'connect_timeout':5},
             'TEST':{'NAME':os.getenv('DB_TEST_NAME','test_petcare')}}}
AUTH_PASSWORD_VALIDATORS = [
 {'NAME':'django.contrib.auth.password_validation.UserAttributeSimilarityValidator'},
 {'NAME':'django.contrib.auth.password_validation.MinimumLengthValidator','OPTIONS':{'min_length':10}},
 {'NAME':'django.contrib.auth.password_validation.CommonPasswordValidator'},
 {'NAME':'django.contrib.auth.password_validation.NumericPasswordValidator'}]
PASSWORD_HASHERS = ['django.contrib.auth.hashers.PBKDF2PasswordHasher']
LANGUAGE_CODE = 'es-cl'
TIME_ZONE = 'America/Santiago'
USE_I18N = True
USE_TZ = True
STATIC_URL = '/static/'
STATIC_ROOT = BASE_DIR/'staticfiles'
STATICFILES_DIRS = [BASE_DIR/'static']
DEFAULT_AUTO_FIELD = 'django.db.models.BigAutoField'
LOGIN_URL = '/login/'
LOGIN_REDIRECT_URL = '/'
LOGOUT_REDIRECT_URL = '/login/'
SESSION_COOKIE_AGE = 8*3600
SESSION_COOKIE_HTTPONLY = True
SESSION_COOKIE_SAMESITE = 'Lax'
CSRF_COOKIE_SAMESITE = 'Lax'
HTTPS_ENABLED = boolean('HTTPS_ENABLED')
SESSION_COOKIE_SECURE = HTTPS_ENABLED
CSRF_COOKIE_SECURE = HTTPS_ENABLED
SECURE_SSL_REDIRECT = HTTPS_ENABLED
SECURE_HSTS_SECONDS = int(os.getenv('HSTS_SECONDS','0')) if HTTPS_ENABLED else 0
SECURE_HSTS_INCLUDE_SUBDOMAINS = False
SECURE_HSTS_PRELOAD = False
# Nginx reemplaza este encabezado; no exponer Gunicorn directamente.
SECURE_PROXY_SSL_HEADER = ('HTTP_X_FORWARDED_PROTO','https')
CSRF_TRUSTED_ORIGINS = [v.strip() for v in os.getenv('CSRF_TRUSTED_ORIGINS','').split(',') if v.strip()]
SECURE_CONTENT_TYPE_NOSNIFF = True
X_FRAME_OPTIONS = 'DENY'
REST_FRAMEWORK = {
 'DEFAULT_AUTHENTICATION_CLASSES':['rest_framework.authentication.SessionAuthentication'],
 'DEFAULT_PERMISSION_CLASSES':['rest_framework.permissions.IsAuthenticated'],
 'DEFAULT_PAGINATION_CLASS':'rest_framework.pagination.PageNumberPagination','PAGE_SIZE':20,
 'DEFAULT_FILTER_BACKENDS':['rest_framework.filters.SearchFilter','rest_framework.filters.OrderingFilter'],
 'DEFAULT_THROTTLE_CLASSES':['rest_framework.throttling.UserRateThrottle'],
 'DEFAULT_THROTTLE_RATES':{'user':'600/min','login':'10/min'},
 'EXCEPTION_HANDLER':'clinica.exceptions.exception_handler',
 'DEFAULT_RENDERER_CLASSES':['rest_framework.renderers.JSONRenderer','rest_framework.renderers.BrowsableAPIRenderer'],
}
EMAIL_BACKEND = 'django.core.mail.backends.smtp.EmailBackend' if os.getenv('SMTP_HOST') else 'django.core.mail.backends.console.EmailBackend'
EMAIL_HOST = os.getenv('SMTP_HOST','localhost')
EMAIL_PORT = int(os.getenv('SMTP_PORT','587'))
EMAIL_HOST_USER = os.getenv('SMTP_USER','')
EMAIL_HOST_PASSWORD = os.getenv('SMTP_PASSWORD','')
EMAIL_USE_TLS = True
EMAIL_TIMEOUT = 15
DEFAULT_FROM_EMAIL = os.getenv('SMTP_FROM','petcare@example.invalid')
SMTP_CONFIGURED = bool(os.getenv('SMTP_HOST'))
LOGGING = {'version':1,'disable_existing_loggers':False,'handlers':{'console':{'class':'logging.StreamHandler'}},
           'root':{'handlers':['console'],'level':'INFO'}}
CSRF_FAILURE_VIEW = 'clinica.views.csrf_failure'

# Solo Nginx local puede aportar X-Real-IP; Gunicorn debe enlazar loopback.
TRUSTED_PROXY_IPS = [v for v in os.getenv('TRUSTED_PROXY_IPS','').split(',') if v]
PASSWORD_RESET_TIMEOUT = 3600
DATA_UPLOAD_MAX_MEMORY_SIZE = 1048576
SESSION_SAVE_EVERY_REQUEST = False

if DATABASES['default']['TEST']['NAME'] == DATABASES['default']['NAME']:
    raise ImproperlyConfigured('DB_TEST_NAME debe ser distinta de DB_NAME para conservar los datos clínicos.')
