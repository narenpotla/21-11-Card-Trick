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

# The free tier of most small hosts (Render included) wipes local disk on
# every redeploy/restart, which would silently drop everyone's session
# (and their in-progress game) along with db.sqlite3. Signed cookies have
# no server-side storage at all, so they're immune to that -- the trade
# is that the pile data now round-trips through the client each request.
# That's a different exposure than the hidden-form-field approach this
# project deliberately avoided (see LEARNING.md architecture section):
# a spectator would need to open devtools, find the session cookie, and
# base64-decode it -- not something "view source" reveals by accident.
# The cookie is still cryptographically signed, so it can't be tampered
# with; only read. Dev keeps the default DB-backed engine since sqlite
# there is never wiped mid-session.
SESSION_ENGINE = "django.contrib.sessions.backends.signed_cookies"

SECURE_SSL_REDIRECT = True
SESSION_COOKIE_SECURE = True
CSRF_COOKIE_SECURE = True
SECURE_HSTS_SECONDS = 31536000
SECURE_HSTS_INCLUDE_SUBDOMAINS = True
SECURE_HSTS_PRELOAD = True
SECURE_CONTENT_TYPE_NOSNIFF = True
X_FRAME_OPTIONS = "DENY"
