"""Tiny stdlib HTTP+JSON fetcher with a polite on-disk cache.

No third-party dependencies: urllib only. Responses are cached in
.cache/live/ (gitignored) with a per-call TTL so repeated runs during
the same session don't hammer the free APIs.
"""

import hashlib
import json
import os
import time
import urllib.request

RETRIES = 3            # total attempts per URL
BACKOFF = (0, 1.5, 4)  # seconds to wait before each attempt

CACHE_DIR = os.path.join(os.path.dirname(os.path.dirname(
    os.path.dirname(os.path.abspath(__file__)))), ".cache", "live")

USER_AGENT = "worldcup-predictor/1.0 (class project)"


from contextlib import contextmanager


@contextmanager
def flock(name):
    """Cross-process file lock so the daemon and any agent-driven run
    never process the same inbox message or send duplicate alerts."""
    import fcntl
    os.makedirs(CACHE_DIR, exist_ok=True)
    f = open(os.path.join(CACHE_DIR, name + ".lock"), "w")
    fcntl.flock(f, fcntl.LOCK_EX)
    try:
        yield
    finally:
        fcntl.flock(f, fcntl.LOCK_UN)
        f.close()


def get_json(url, ttl=900, headers=None, timeout=15):
    """GET a JSON document, serving from cache when younger than ttl (s).
    Returns the parsed object, or None on any network/parse failure —
    callers treat None as 'live data unavailable' and fall back."""
    os.makedirs(CACHE_DIR, exist_ok=True)
    key = hashlib.sha1(url.encode()).hexdigest()[:24]
    path = os.path.join(CACHE_DIR, key + ".json")
    try:
        if os.path.exists(path) and (time.time() - os.path.getmtime(path)) < ttl:
            with open(path) as f:
                return json.load(f)
    except (OSError, json.JSONDecodeError):
        pass
    req = urllib.request.Request(url, headers={"User-Agent": USER_AGENT,
                                               **(headers or {})})
    data = None
    for attempt in range(RETRIES):
        if BACKOFF[attempt]:
            time.sleep(BACKOFF[attempt])
        try:
            with urllib.request.urlopen(req, timeout=timeout) as r:
                data = json.load(r)
            break
        except Exception:
            continue
    if data is None:
        return None
    try:
        with open(path, "w") as f:
            json.dump(data, f)
    except OSError:
        pass
    return data
