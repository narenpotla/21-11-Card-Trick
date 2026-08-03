"""Dev convenience: append a changing version to static asset URLs so a
normal browser refresh always picks up the latest CSS/JS during active
development, instead of silently serving a stale cached copy.

Dev-only on purpose: in prod, WhiteNoise's CompressedManifestStaticFilesStorage
already content-hashes filenames, letting browsers cache assets forever and
only refetch when a file's content actually changes. A wall-clock value here
would override that and force a full re-download of every asset on every
single request -- the opposite of what caching is for."""

import time

from django.conf import settings


def asset_version(request):
    return {"ASSET_VERSION": int(time.time()) if settings.DEBUG else "1"}
