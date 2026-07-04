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

CACHE_DIR = os.path.join(os.path.dirname(os.path.dirname(
    os.path.dirname(os.path.abspath(__file__)))), ".cache", "live")

USER_AGENT = "worldcup-predictor/1.0 (class project)"


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
    try:
        with urllib.request.urlopen(req, timeout=timeout) as r:
            data = json.load(r)
    except Exception:
        return None
    try:
        with open(path, "w") as f:
            json.dump(data, f)
    except OSError:
        pass
    return data
