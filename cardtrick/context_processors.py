"""Dev convenience: append a changing version to static asset URLs so a
normal browser refresh always picks up the latest CSS/JS during active
development, instead of silently serving a stale cached copy."""

import time


def asset_version(request):
    return {"ASSET_VERSION": int(time.time())}
