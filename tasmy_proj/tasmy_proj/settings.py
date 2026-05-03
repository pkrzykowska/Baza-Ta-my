from pathlib import Path

# Ścieżka bazowa projektu
BASE_DIR = Path(__file__).resolve().parent.parent

# Klucz – w realnym projekcie generuje go Django, tu może zostać taki
SECRET_KEY = 'django-insecure-zmien-mnie-na-losowy-klucz'

# Tryb debug – na czas pracy inżynierskiej może być True
DEBUG = True

ALLOWED_HOSTS = []


# Aplikacje w projekcie
INSTALLED_APPS = [
    'django.contrib.admin',
    'django.contrib.auth',
    'django.contrib.contenttypes',
    'django.contrib.sessions',
    'django.contrib.messages',
    'django.contrib.staticfiles',

    'rd',  # Twoja aplikacja z modelami taśm itp.
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


ROOT_URLCONF = 'tasmy_proj.urls'


TEMPLATES = [
    {
        'BACKEND': 'django.template.backends.django.DjangoTemplates',
        'DIRS': [],      # tu można dodać katalog templates jak będzie potrzebny
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


WSGI_APPLICATION = 'tasmy_proj.wsgi.application'


# ---------- KONFIGURACJA BAZY DANYCH POSTGRESQL ----------

DATABASES = {
    'default': {
        'ENGINE': 'django.db.backends.postgresql',
        'NAME': 'tasmy_db',
        'USER': 'postgres',
        'PASSWORD': 'Wichos18',
        'HOST': 'localhost',
        'PORT': '5432',
    }
}



# Walidatory haseł (zostaw domyślne)
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


# Ustawienia języka/czasu
LANGUAGE_CODE = 'pl'

TIME_ZONE = 'Europe/Warsaw'

USE_I18N = True

USE_TZ = True


# Pliki statyczne (CSS, JS, obrazki)
STATIC_URL = 'static/'


DEFAULT_AUTO_FIELD = 'django.db.models.BigAutoField'
