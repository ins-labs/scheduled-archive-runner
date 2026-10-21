#!/usr/bin/env python3
"""Best-effort workflow-failure notification through the EXISTING slot alert
route. Stdlib only; fully generic; never prints secret material.

Route: the `notify` webhook URL already carried inside each slot config secret
("webhook:<https-url>", see engine/notifier.py). No new secret, no new route.

Sources, in order:
  1. SLOT_CONFIG_JSON  - single-slot mode (slot.yml matrix job)
  2. SLOT_<n>_CONFIG   - fan-out mode (clock.yml), n from argv or 1 2 3

Message comes from NOTIFY_MESSAGE and must stay generic (workflow name, slot
number, public run URL). Exits 0 always: notification failure never fails the
job further.
"""
import json, os, sys, urllib.request

MAX_BODY = 4096


def _webhook(raw):
    try:
        notify = str(json.loads(raw).get("notify", ""))
    except ValueError:
        return ""
    if notify.startswith("webhook:https://"):
        return notify[len("webhook:"):]
    return ""


def post(url, message, opener=None):
    body = json.dumps({"text": message}).encode()[:MAX_BODY]
    req = urllib.request.Request(url, data=body,
                                 headers={"Content-Type": "application/json"})
    op = opener or urllib.request.build_opener()
    try:
        with op.open(req, timeout=30) as r:
            return 200 <= r.status < 300
    except Exception:
        return False


def main(argv=None):
    slots = argv if argv is not None else (sys.argv[1:] or ["1", "2", "3"])
    message = os.environ.get("NOTIFY_MESSAGE", "workflow run failed")
    candidates = [os.environ.get("SLOT_CONFIG_JSON", "").strip()]
    candidates += [os.environ.get("SLOT_%s_CONFIG" % s, "").strip() for s in slots]
    for raw in candidates:
        if not raw:
            continue
        url = _webhook(raw)
        if url and post(url, message):
            return 0
    return 0


if __name__ == "__main__":
    sys.exit(main())
