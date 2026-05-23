from pathlib import Path

import environ

BASE_DIR = Path(__file__).resolve().parent.parent.parent

env = environ.Env(DEBUG=(bool, False))
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
    "apps.retry",
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
        "ENGINE": "django.db.backends.sqlite3",
        "NAME": str(BASE_DIR / "db.sqlite3"),
    }
}

LANGUAGE_CODE = "en-us"
TIME_ZONE = env("TIME_ZONE", default="Asia/Ho_Chi_Minh")
USE_I18N = True
USE_TZ = True

STATIC_URL = "static/"
STATIC_ROOT = BASE_DIR / "staticfiles"
DEFAULT_AUTO_FIELD = "django.db.models.BigAutoField"

REST_FRAMEWORK = {
    "DEFAULT_SCHEMA_CLASS": "drf_spectacular.openapi.AutoSchema",
    "DEFAULT_RENDERER_CLASSES": ["rest_framework.renderers.JSONRenderer"],
}

SPECTACULAR_SETTINGS = {
    "TITLE": "Retry Service",
    "DESCRIPTION": "Consumes send_failed and publishes send_retry or dead_letter.",
    "VERSION": "1.0.0",
}

RETRY_RUN_MODE = env("RETRY_RUN_MODE", default="web")
RETRY_INTERNAL_API_KEY = env("RETRY_INTERNAL_API_KEY", default="")

MONGO_DB_NAME = env("MONGO_DB_NAME", default="core_service_db")
MONGO_HOST = env("MONGO_HOST", default="mongodb")
MONGO_PORT = env.int("MONGO_PORT", default=27017)

KAFKA_BOOTSTRAP_SERVERS = env.list("KAFKA_BOOTSTRAP_SERVERS", default=["localhost:9092"])
KAFKA_SEND_FAILED_TOPIC = env("KAFKA_SEND_FAILED_TOPIC", default="send_failed")
KAFKA_SEND_RETRY_TOPIC = env("KAFKA_SEND_RETRY_TOPIC", default="send_retry")
KAFKA_DEAD_LETTER_TOPIC = env("KAFKA_DEAD_LETTER_TOPIC", default="dead_letter")
KAFKA_CONSUMER_GROUP_ID = env("KAFKA_CONSUMER_GROUP_ID", default="retry-service")
KAFKA_CLIENT_ID = env("KAFKA_CLIENT_ID", default="retry-service")
KAFKA_AUTO_OFFSET_RESET = env("KAFKA_AUTO_OFFSET_RESET", default="earliest")
KAFKA_MAX_POLL_RECORDS = env.int("KAFKA_MAX_POLL_RECORDS", default=20)
KAFKA_POLL_TIMEOUT_MS = env.int("KAFKA_POLL_TIMEOUT_MS", default=3000)
KAFKA_CONSUMER_TIMEOUT_MS = env.int("KAFKA_CONSUMER_TIMEOUT_MS", default=5000)
KAFKA_CONNECT_MAX_RETRIES = env.int("KAFKA_CONNECT_MAX_RETRIES", default=0)
KAFKA_CONNECT_BACKOFF_SECONDS = env.int("KAFKA_CONNECT_BACKOFF_SECONDS", default=5)
KAFKA_API_VERSION_AUTO_TIMEOUT_MS = env.int("KAFKA_API_VERSION_AUTO_TIMEOUT_MS", default=10000)

RETRY_BASE_DELAY_SECONDS = env.int("RETRY_BASE_DELAY_SECONDS", default=1)
RETRY_MAX_DELAY_SECONDS = env.int("RETRY_MAX_DELAY_SECONDS", default=60)
RETRY_MAX_ATTEMPTS = env.int("RETRY_MAX_ATTEMPTS", default=3)

