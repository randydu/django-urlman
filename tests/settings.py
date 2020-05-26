import django.conf
import os

os.environ.setdefault('DJANGO_SETTINGS_MODULE', __name__)
#django.conf.settings.configure(ROOT_URLCONF=__name__)
ROOT_URLCONF = __name__

# SECURITY WARNING: keep the secret key used in production secret!
SECRET_KEY = 'y8fxqsf_v@ef!i4b()m(yes$!i!qw1-gpw&(u5h!@ul(m=j^_w'

urlpatterns = []
"""
MIDDLEWARE = [
    'django.middleware.security.SecurityMiddleware',
    'django.contrib.sessions.middleware.SessionMiddleware',
    'django.middleware.common.CommonMiddleware',
    'django.middleware.csrf.CsrfViewMiddleware',
    'django.contrib.auth.middleware.AuthenticationMiddleware',
    'django.contrib.messages.middleware.MessageMiddleware',
    'django.middleware.clickjacking.XFrameOptionsMiddleware',
]

INSTALLED_APPS = [
    'django.contrib.admin',
    'django.contrib.auth',
    'django.contrib.contenttypes',
    'django.contrib.sessions',
    'django.contrib.messages',
    'django.contrib.staticfiles',
  #  'polls.apps.PollsConfig'
]
"""