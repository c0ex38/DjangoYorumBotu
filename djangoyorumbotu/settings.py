from pathlib import Path
import os

BASE_DIR = Path(__file__).resolve().parent.parent

SECRET_KEY = 'django-insecure-lv2!xtm4dcmho=d5==nxaftc04a1ad_ze4)m*u2tmm#)gnps($'

DEBUG = True

ALLOWED_HOSTS = []

INSTALLED_APPS = [
    'rest_framework',
    'trendyol',
]

MIDDLEWARE = [
    'django.middleware.security.SecurityMiddleware',
    'django.middleware.common.CommonMiddleware',
]

ROOT_URLCONF = 'djangoyorumbotu.urls'

WSGI_APPLICATION = 'djangoyorumbotu.wsgi.application'

DATABASES = {
    'default': {
        'ENGINE': 'django.db.backends.postgresql',
        'NAME': 'trendyol_db',
        'USER': 'postgres',
        'PASSWORD': 'cgr2001ZY',
        'HOST': 'localhost',
        'PORT': '5432',
    }
}

# Dil ve zaman ayarları (Türkiye için)
LANGUAGE_CODE = 'tr'
TIME_ZONE = 'Europe/Istanbul'

USE_I18N = True
USE_TZ = True

DEFAULT_AUTO_FIELD = 'django.db.models.BigAutoField'