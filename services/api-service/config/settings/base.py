from pathlib import Path

import environ

BASE_DIR = Path(__file__).resolve().parent.parent.parent

env = environ.Env(
    DEBUG=(bool, False),
)
environ.Env.read_env(BASE_DIR / ".env")

SECRET_KEY = env("DJANGO_SECRET_KEY", default="unsafe-dev-secret-key")
DEBUG = env("DEBUG")
ALLOWED_HOSTS = ["*"]

INSTALLED_APPS = [
    "django.contrib.admin",
    "django.contrib.auth",
    "django.contrib.contenttypes",
    "django.contrib.sessions",
    "django.contrib.messages",
    "django.contrib.staticfiles",
    "rest_framework",
    "drf_spectacular",
    "apps.facebook_api",
]

MIDDLEWARE = [
    "django.middleware.security.SecurityMiddleware",
    "django.contrib.sessions.middleware.SessionMiddleware",
    "django.middleware.common.CommonMiddleware",
    "django.middleware.csrf.CsrfViewMiddleware",
    "django.contrib.auth.middleware.AuthenticationMiddleware",
    "django.contrib.messages.middleware.MessageMiddleware",
    "django.middleware.clickjacking.XFrameOptionsMiddleware",
]

ROOT_URLCONF = "config.urls"

TEMPLATES = [
    {
        "BACKEND": "django.template.backends.django.DjangoTemplates",
        "DIRS": [BASE_DIR / "templates"],
        "APP_DIRS": True,
        "OPTIONS": {
            "context_processors": [
                "django.template.context_processors.request",
                "django.contrib.auth.context_processors.auth",
                "django.contrib.messages.context_processors.messages",
            ],
        },
    },
]

WSGI_APPLICATION = "config.wsgi.application"
ASGI_APPLICATION = "config.asgi.application"

DATABASES = {
    "default": {
        "ENGINE": env("DB_ENGINE", default="django.db.backends.sqlite3"),
        "NAME": env("DB_NAME", default=str(BASE_DIR / "db.sqlite3")),
    }
}

AUTH_PASSWORD_VALIDATORS = [
    {"NAME": "django.contrib.auth.password_validation.UserAttributeSimilarityValidator"},
    {"NAME": "django.contrib.auth.password_validation.MinimumLengthValidator"},
    {"NAME": "django.contrib.auth.password_validation.CommonPasswordValidator"},
    {"NAME": "django.contrib.auth.password_validation.NumericPasswordValidator"},
]

LANGUAGE_CODE = "en-us"
TIME_ZONE = env("TIME_ZONE", default="Asia/Ho_Chi_Minh")
USE_I18N = True
USE_TZ = True

STATIC_URL = "static/"
STATIC_ROOT = BASE_DIR / "staticfiles"
MEDIA_URL = "media/"
MEDIA_ROOT = BASE_DIR / "media"

DEFAULT_AUTO_FIELD = "django.db.models.BigAutoField"

REST_FRAMEWORK = {
    "DEFAULT_SCHEMA_CLASS": "drf_spectacular.openapi.AutoSchema",
    "DEFAULT_RENDERER_CLASSES": [
        "rest_framework.renderers.JSONRenderer",
    ],
}

SPECTACULAR_SETTINGS = {
    "TITLE": "API Service – Facebook Page Management",
    "DESCRIPTION": "Microservice: REST APIs for Facebook Page management via Graph API",
    "VERSION": "1.0.0",
}

FACEBOOK_GRAPH_API_VERSION = env("FACEBOOK_GRAPH_API_VERSION", default="v22.0")
FACEBOOK_PAGE_ACCESS_TOKEN = env("FACEBOOK_PAGE_ACCESS_TOKEN", default="")
FACEBOOK_APP_ID = env("FACEBOOK_APP_ID", default="")
FACEBOOK_APP_SECRET = env("FACEBOOK_APP_SECRET", default="")

# Kafka command worker
KAFKA_BOOTSTRAP_SERVERS = env.list("KAFKA_BOOTSTRAP_SERVERS", default=["localhost:9092"])
KAFKA_REPLY_COMMANDS_TOPIC = env("KAFKA_REPLY_COMMANDS_TOPIC", default="reply_commands")
KAFKA_SEND_FAILED_TOPIC = env("KAFKA_SEND_FAILED_TOPIC", default="send_failed")
KAFKA_CONSUMER_GROUP_ID = env("KAFKA_CONSUMER_GROUP_ID", default="api-service")
KAFKA_CLIENT_ID = env("KAFKA_CLIENT_ID", default="api-service")
KAFKA_AUTO_OFFSET_RESET = env("KAFKA_AUTO_OFFSET_RESET", default="earliest")
KAFKA_MAX_RETRIES = env.int("KAFKA_MAX_RETRIES", default=3)
KAFKA_MAX_POLL_RECORDS = env.int("KAFKA_MAX_POLL_RECORDS", default=20)
KAFKA_POLL_TIMEOUT_MS = env.int("KAFKA_POLL_TIMEOUT_MS", default=3000)
KAFKA_CONSUMER_TIMEOUT_MS = env.int("KAFKA_CONSUMER_TIMEOUT_MS", default=5000)
KAFKA_CONNECT_MAX_RETRIES = env.int("KAFKA_CONNECT_MAX_RETRIES", default=0)
KAFKA_CONNECT_BACKOFF_SECONDS = env.int("KAFKA_CONNECT_BACKOFF_SECONDS", default=5)
KAFKA_API_VERSION_AUTO_TIMEOUT_MS = env.int("KAFKA_API_VERSION_AUTO_TIMEOUT_MS", default=10000)
KAFKA_PRODUCER_SEND_TIMEOUT_SECONDS = env.int("KAFKA_PRODUCER_SEND_TIMEOUT_SECONDS", default=10)
