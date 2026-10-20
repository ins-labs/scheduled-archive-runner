"""Notifiers for the slot engine. Stdlib only. Notifications carry the slot id
and a short hash only - never content.

cfg["notify"] syntax: "webhook:<https-url>" posts a small JSON body to the URL
(secret webhook URLs arrive via the slot config, which itself is a secret).
Unknown or empty notifier names are a no-op that reports success.
"""
import json, urllib.request

MAX_BODY = 4096


def notify(name, message, opener=None):
    if not name:
        return True
    if not name.startswith("webhook:"):
        return False
    url = name[len("webhook:"):]
    if not url.startswith("https://"):
        return False
    body = json.dumps({"text": message}).encode()[:MAX_BODY]
    req = urllib.request.Request(url, data=body,
                                 headers={"Content-Type": "application/json"})
    op = opener or urllib.request.build_opener()
    try:
        with op.open(req, timeout=30) as r:
            return 200 <= r.status < 300
    except Exception:
        return False
