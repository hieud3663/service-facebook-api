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
    "apps.core",
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

# ── SQLite for Django admin/auth internals only ──
DATABASES = {
    "default": {
        "ENGINE": "django.db.backends.sqlite3",
        "NAME": str(BASE_DIR / "db.sqlite3"),
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
    "TITLE": "Core Service – Event Processing Pipeline",
    "DESCRIPTION": "Microservice: Kafka consumer, AI classification (Dify), spam detection, and auto-moderation",
    "VERSION": "1.0.0",
}

# ── MongoDB (pymongo direct) ──
MONGO_DB_NAME = env("MONGO_DB_NAME", default="core_service_db")
MONGO_HOST = env("MONGO_HOST", default="mongodb")
MONGO_PORT = env.int("MONGO_PORT", default=27017)

# ── Kafka ──
KAFKA_BOOTSTRAP_SERVERS = env.list("KAFKA_BOOTSTRAP_SERVERS", default=["localhost:9092"])
KAFKA_RAW_EVENTS_TOPIC = env("KAFKA_RAW_EVENTS_TOPIC", default="raw_events")
KAFKA_DEAD_LETTER_TOPIC = env("KAFKA_DEAD_LETTER_TOPIC", default="dead_letter")
KAFKA_SEND_FAILED_TOPIC = env("KAFKA_SEND_FAILED_TOPIC", default="send_failed")
KAFKA_SEND_RETRY_TOPIC = env("KAFKA_SEND_RETRY_TOPIC", default="send_retry")
KAFKA_REPLY_COMMANDS_TOPIC = env("KAFKA_REPLY_COMMANDS_TOPIC", default="reply_commands")
KAFKA_CONSUMER_GROUP_ID = env("KAFKA_CONSUMER_GROUP_ID", default="core-service")
KAFKA_CLIENT_ID = env("KAFKA_CLIENT_ID", default="core-service")
KAFKA_AUTO_OFFSET_RESET = env("KAFKA_AUTO_OFFSET_RESET", default="earliest")
KAFKA_MAX_RETRIES = env.int("KAFKA_MAX_RETRIES", default=3)
KAFKA_PRODUCER_SEND_TIMEOUT_SECONDS = env.int("KAFKA_PRODUCER_SEND_TIMEOUT_SECONDS", default=10)
KAFKA_CONSUMER_FAST_RETRIES = env.int("KAFKA_CONSUMER_FAST_RETRIES", default=1)
KAFKA_MAX_POLL_RECORDS = env.int("KAFKA_MAX_POLL_RECORDS", default=20)
KAFKA_POLL_TIMEOUT_MS = env.int("KAFKA_POLL_TIMEOUT_MS", default=3000)
KAFKA_CONSUMER_TIMEOUT_MS = env.int("KAFKA_CONSUMER_TIMEOUT_MS", default=5000)
KAFKA_CONNECT_MAX_RETRIES = env.int("KAFKA_CONNECT_MAX_RETRIES", default=0)  # 0 = retry forever
KAFKA_CONNECT_BACKOFF_SECONDS = env.int("KAFKA_CONNECT_BACKOFF_SECONDS", default=5)
KAFKA_API_VERSION_AUTO_TIMEOUT_MS = env.int("KAFKA_API_VERSION_AUTO_TIMEOUT_MS", default=10000)

# ── Internal API security ──
CORE_INTERNAL_API_KEY = env("CORE_INTERNAL_API_KEY", default="")

# ── Dify AI ──
DIFY_API_URL = env("DIFY_API_URL", default="https://api.dify.ai/v1")
DIFY_API_KEY = env("DIFY_API_KEY", default="")

# Core moderation policy
CORE_RATE_LIMIT_WINDOW_SECONDS = env.int("CORE_RATE_LIMIT_WINDOW_SECONDS", default=60)
CORE_RATE_LIMIT_MAX_EVENTS = env.int("CORE_RATE_LIMIT_MAX_EVENTS", default=20)
CORE_AUTO_REPLY_POSITIVE = env.bool("CORE_AUTO_REPLY_POSITIVE", default=True)
CORE_AUTO_REPLY_NEGATIVE = env.bool("CORE_AUTO_REPLY_NEGATIVE", default=True)
CORE_AI_MIN_CONFIDENCE = env.float("CORE_AI_MIN_CONFIDENCE", default=0.6)
CORE_POSITIVE_REPLY_MESSAGE = env(
    "CORE_POSITIVE_REPLY_MESSAGE",
    default="Cam on ban da ung ho shop!",
)
CORE_NEGATIVE_REPLY_MESSAGE = env(
    "CORE_NEGATIVE_REPLY_MESSAGE",
    default="Rat xin loi vi trai nghiem chua tot, ben minh se kiem tra ngay.",
)

# Circuit breaker
CIRCUIT_BREAKER_FAILURE_THRESHOLD = env.int("CIRCUIT_BREAKER_FAILURE_THRESHOLD", default=5)
CIRCUIT_BREAKER_RESET_TIMEOUT_SECONDS = env.int("CIRCUIT_BREAKER_RESET_TIMEOUT_SECONDS", default=30)
