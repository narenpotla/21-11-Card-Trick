"""
Production settings. Activate with DJANGO_SETTINGS_MODULE=config.settings.prod.

Every value that must differ per-deployment (secret key, allowed hosts) is
read from the environment in base.py — this file only turns on the
hardening that dev.py deliberately skips for convenience.
"""

from .base import *  # noqa: F401,F403

DEBUG = False

if not SECRET_KEY:
    raise RuntimeError(
        "DJANGO_SECRET_KEY environment variable must be set in production."
    )

if not ALLOWED_HOSTS:
    raise RuntimeError(
        "DJANGO_ALLOWED_HOSTS environment variable must be set in production."
    )

STORAGES = {
    "staticfiles": {
        "BACKEND": "whitenoise.storage.CompressedManifestStaticFilesStorage",
    },
}

SECURE_SSL_REDIRECT = True
SESSION_COOKIE_SECURE = True
CSRF_COOKIE_SECURE = True
SECURE_HSTS_SECONDS = 31536000
SECURE_HSTS_INCLUDE_SUBDOMAINS = True
SECURE_HSTS_PRELOAD = True
SECURE_CONTENT_TYPE_NOSNIFF = True
X_FRAME_OPTIONS = "DENY"
