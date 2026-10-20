import json, os, sys, tempfile, time, unittest
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
import engine


def cfg(**k):
    c = {"id": "slot1", "adapter": "command", "target": "/bin/echo hello_world", "normalize": [], "notify": "n"}
    c.update(k)
    return c


class Env:
    def __init__(self, texts, notify_ok=True):
        self.texts = list(texts); self.sent = []; self.notify_ok = notify_ok
        self.d = tempfile.mkdtemp()
    def fetch(self, c):
        t = self.texts.pop(0)
        if isinstance(t, Exception):
            raise t
        return t
    def notify(self, name, msg):
        self.sent.append((name, msg)); return self.notify_ok
    def run(self, c=None):
        return engine.run_slot(c or cfg(), self.d, fetch=self.fetch, notify=self.notify)


class T(unittest.TestCase):
    def test_first_run_stores_silently(self):
        e = Env(["a"]); self.assertEqual(e.run(), "stored"); self.assertEqual(e.sent, [])
    def test_unchanged_is_silent(self):
        e = Env(["a", "a"]); e.run(); self.assertEqual(e.run(), "unchanged"); self.assertEqual(e.sent, [])
    def test_change_notifies_once_without_content(self):
        e = Env(["a", "SECRET-b", "SECRET-b"]); e.run()
        self.assertEqual(e.run(), "changed"); self.assertEqual(len(e.sent), 1)
        self.assertNotIn("SECRET", json.dumps(e.sent)); self.assertIn("slot1", e.sent[0][1])
        self.assertEqual(e.run(), "unchanged"); self.assertEqual(len(e.sent), 1)
    def test_normalize_strips_noise(self):
        c = cfg(normalize=[r"\d{4}-\d\d-\d\d"]); e = Env(["v1 2026-01-01", "v1 2026-02-02"])
        e.run(c); self.assertEqual(e.run(c), "unchanged")
    def test_fetch_failure_keeps_snapshot_and_reports_once(self):
        e = Env(["a", OSError("x"), OSError("y"), "a"]); e.run()
        self.assertEqual(e.run(), "fetch_failed"); self.assertEqual(len(e.sent), 1)
        self.assertEqual(e.run(), "fetch_failed"); self.assertEqual(len(e.sent), 1)   # once per transition
        self.assertEqual(e.run(), "unchanged")                                          # old snapshot survived
    def test_snapshot_written_only_after_notify_ok(self):
        e = Env(["a", "b", "b"]); e.run(); e.notify_ok = False
        self.assertEqual(e.run(), "notify_failed")
        e.notify_ok = True; self.assertEqual(e.run(), "changed")                       # retried, not lost
        self.assertEqual(len(e.sent), 2)
    def test_bad_config_never_raises(self):
        for bad in ({"id": "../x"}, {"adapter": "rm"}, {"normalize": ["("]}, {"id": ""}):
            e = Env(["a"]); self.assertEqual(e.run(cfg(**bad)), "bad_config")
    def test_snapshot_file_not_world_readable(self):
        e = Env(["a"]); e.run()
        for f in os.listdir(e.d):
            self.assertEqual(os.stat(os.path.join(e.d, f)).st_mode & 0o077, 0)

    def test_empty_fetch_response_fails(self):
        e = Env([""]); self.assertEqual(e.run(), "fetch_failed")
        e2 = Env(["\n  \n"]); self.assertEqual(e2.run(), "fetch_failed")

    def test_notify_failed_on_fetch_failure_notification(self):
        e = Env([OSError("fetch error")], notify_ok=False)
        self.assertEqual(e.run(), "notify_failed")

    def test_http_get_rejects_non_https_redirect(self):
        class DummyRequest:
            full_url = "https://example.com"
        handler = engine.HTTPSOnlyRedirectHandler()
        with self.assertRaises(ValueError):
            handler.redirect_request(DummyRequest(), None, 302, "Found", {}, "http://insecure.com/test")

    def test_default_fetch_command(self):
        c = cfg(adapter="command", target="/bin/echo hello_world")
        res = engine.default_fetch(c)
        self.assertIn("hello_world", res)

    def test_command_timeout_kills_process(self):
        c = cfg(adapter="command", target="/bin/sleep 60")
        with self.assertRaises(ValueError):
            engine.default_fetch(c, timeout=0.1)

    def test_command_env_is_isolated(self):
        os.environ["SECRET_TOKEN"] = "SUPERSECRET123"
        c = cfg(adapter="command", target="/usr/bin/env")
        res = engine.default_fetch(c)
        self.assertNotIn("SUPERSECRET123", res)

    def test_unbounded_command_stdout_fails_fast_oversize(self):
        c = cfg(adapter="command", target="/usr/bin/yes")
        t0 = time.time()
        with self.assertRaises(ValueError) as ctx:
            engine.default_fetch(c, timeout=30)
        t1 = time.time()
        self.assertLess(t1 - t0, 1.0)
        self.assertIn("oversize", str(ctx.exception))

if __name__ == "__main__":
    unittest.main()
