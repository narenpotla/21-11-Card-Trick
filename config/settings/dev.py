"""Local development settings. Default DJANGO_SETTINGS_MODULE — see manage.py."""

from .base import *  # noqa: F401,F403

DEBUG = True

# A throwaway fallback so `runserver` works with zero setup. Never used in
# prod.py, which requires DJANGO_SECRET_KEY to be set externally.
if not SECRET_KEY:
    SECRET_KEY = "django-insecure-dev-only-key-do-not-use-in-production"

if not ALLOWED_HOSTS:
    ALLOWED_HOSTS = ["localhost", "127.0.0.1"]
