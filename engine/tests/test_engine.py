import json, os, sys, tempfile, time, unittest
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
import engine, notifier


def cfg(**k):
    c = {"id": "slot1", "adapter": "command", "target": "/bin/echo hello_world", "normalize": [], "notify": "webhook:https://example.invalid/hook"}
    c.update(k)
    return c


class ConfigurableFakeOpener:
    def __init__(self, status=200, exc=None):
        self.status = status
        self.exc = exc
        self.requests = []
    def open(self, req, timeout=30):
        self.requests.append(req)
        if self.exc:
            raise self.exc
        class Resp:
            def __init__(self, status): self.status = status
            def __enter__(self): return self
            def __exit__(self, *a): return False
        return Resp(self.status)


class Env:
    def __init__(self, texts, status=200, exc=None):
        self.texts = list(texts)
        self.d = tempfile.mkdtemp()
        self.opener = ConfigurableFakeOpener(status=status, exc=exc)
    def fetch(self, c):
        t = self.texts.pop(0)
        if isinstance(t, Exception):
            raise t
        return t
    def notify(self, name, msg):
        return notifier.notify(name, msg, opener=self.opener)
    def run(self, c=None):
        return engine.run_slot(c or cfg(), self.d, fetch=self.fetch, notify=self.notify)


class T(unittest.TestCase):
    def test_first_run_stores_silently(self):
        e = Env(["a"]); self.assertEqual(e.run(), "stored"); self.assertEqual(len(e.opener.requests), 0)

    def test_unchanged_is_silent(self):
        e = Env(["a", "a"]); e.run(); self.assertEqual(e.run(), "unchanged"); self.assertEqual(len(e.opener.requests), 0)

    def test_change_notifies_once_without_content(self):
        # Explicit REQUIRED_NOTIFY mode added because this test verifies notification dispatch and 'changed' status upon content change.
        c = cfg(mode="REQUIRED_NOTIFY")
        e = Env(["a", "SECRET-b", "SECRET-b"]); e.run(c)
        self.assertEqual(e.run(c), "changed"); self.assertEqual(len(e.opener.requests), 1)
        req_body = e.opener.requests[0].data.decode()
        self.assertNotIn("SECRET", req_body); self.assertIn("slot1", req_body)
        self.assertEqual(e.run(c), "unchanged"); self.assertEqual(len(e.opener.requests), 1)

    def test_normalize_strips_noise(self):
        c = cfg(normalize=[r"\d{4}-\d\d-\d\d"]); e = Env(["v1 2026-01-01", "v1 2026-02-02"])
        e.run(c); self.assertEqual(e.run(c), "unchanged")

    def test_fetch_failure_keeps_snapshot_and_reports_once(self):
        # Explicit REQUIRED_NOTIFY mode added because this test verifies notification reporting upon fetch failure.
        c = cfg(mode="REQUIRED_NOTIFY")
        e = Env(["a", OSError("x"), OSError("y"), "a"]); e.run(c)
        self.assertEqual(e.run(c), "fetch_failed"); self.assertEqual(len(e.opener.requests), 1)
        self.assertEqual(e.run(c), "fetch_failed"); self.assertEqual(len(e.opener.requests), 1)   # once per transition
        self.assertEqual(e.run(c), "unchanged")                                          # old snapshot survived

    def test_snapshot_written_only_after_notify_ok(self):
        # Explicit REQUIRED_NOTIFY mode added because this test verifies that snapshot advancement is contingent on successful notification delivery.
        c = cfg(mode="REQUIRED_NOTIFY")
        e = Env(["a", "b", "b"], status=500)
        self.assertEqual(e.run(c), "stored")
        self.assertEqual(e.run(c), "notify_failed")
        snap_path = os.path.join(e.d, "slot1.snap")
        with open(snap_path, "r", encoding="utf-8") as f:
            self.assertEqual(f.read(), "a")
        # Repair opener to 200
        e.opener.status = 200
        self.assertEqual(e.run(c), "changed")                                          # retried, not lost
        with open(snap_path, "r", encoding="utf-8") as f:
            self.assertEqual(f.read(), "b")

    def test_bad_config_never_raises(self):
        for bad in ({"id": "../x"}, {"adapter": "rm"}, {"normalize": ["("]}, {"id": ""}):
            e = Env(["a"]); self.assertEqual(e.run(cfg(**bad)), "bad_config")

    def test_c1_explicit_null_mode_is_bad_config_before_fetch(self):
        c = cfg(mode=None)
        fetch_called = False
        def bad_fetch(c_arg):
            nonlocal fetch_called
            fetch_called = True
            return "data"
        e = Env(["a"])
        self.assertEqual(engine.run_slot(c, e.d, fetch=bad_fetch, notify=e.notify), "bad_config")
        self.assertFalse(fetch_called)
        self.assertEqual(len(os.listdir(e.d)), 0)

    def test_snapshot_file_not_world_readable(self):
        e = Env(["a"]); e.run()
        for f in os.listdir(e.d):
            self.assertEqual(os.stat(os.path.join(e.d, f)).st_mode & 0o077, 0)

    def test_empty_fetch_response_fails(self):
        e = Env([""]); self.assertEqual(e.run(), "fetch_failed")
        e2 = Env(["\n  \n"]); self.assertEqual(e2.run(), "fetch_failed")

    def test_notify_failed_on_fetch_failure_notification(self):
        # Explicit REQUIRED_NOTIFY mode added because this test verifies notify_failed behavior on fetch failure notification error.
        c = cfg(mode="REQUIRED_NOTIFY")
        e = Env(["a", OSError("fetch error")], status=500)
        self.assertEqual(e.run(c), "stored")
        self.assertEqual(e.run(c), "notify_failed")

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

    def test_r1_required_notify_empty_sink_change_retains_baseline_and_repaired_delivers(self):
        c = cfg(mode="REQUIRED_NOTIFY", notify="")
        e = Env(["a", "b", "b"])
        self.assertEqual(e.run(c), "stored")
        self.assertEqual(e.run(c), "notify_failed")
        self.assertEqual(len(e.opener.requests), 0)
        snap_path = os.path.join(e.d, "slot1.snap")
        with open(snap_path, "r", encoding="utf-8") as f:
            self.assertEqual(f.read(), "a")
        c_repaired = cfg(mode="REQUIRED_NOTIFY", notify="webhook:https://example.invalid/hook")
        self.assertEqual(e.run(c_repaired), "changed")
        self.assertEqual(len(e.opener.requests), 1)
        with open(snap_path, "r", encoding="utf-8") as f:
            self.assertEqual(f.read(), "b")

    def test_r2_required_notify_missing_sink_retains_baseline(self):
        c = cfg(mode="REQUIRED_NOTIFY")
        del c["notify"]
        e = Env(["a", "b"])
        self.assertEqual(e.run(c), "stored")
        self.assertEqual(e.run(c), "notify_failed")
        self.assertEqual(len(e.opener.requests), 0)
        snap_path = os.path.join(e.d, "slot1.snap")
        with open(snap_path, "r", encoding="utf-8") as f:
            self.assertEqual(f.read(), "a")

    def test_r3_required_notify_fetch_failure_invalid_sink_no_reported_fail(self):
        c = cfg(mode="REQUIRED_NOTIFY", notify="")
        e = Env(["a", OSError("fetch error")])
        self.assertEqual(e.run(c), "stored")
        self.assertEqual(e.run(c), "notify_failed")
        self.assertEqual(len(e.opener.requests), 0)
        fail_path = os.path.join(e.d, "slot1.fail")
        self.assertFalse(os.path.exists(fail_path))

    def test_c2_required_notify_transport_exception_keeps_snapshot_and_fail_untouched(self):
        c = cfg(mode="REQUIRED_NOTIFY", notify="webhook:https://example.invalid/hook")
        e = Env(["a", "b"], exc=OSError("connection refused"))
        self.assertEqual(e.run(c), "stored")
        self.assertEqual(e.run(c), "notify_failed")
        self.assertEqual(len(e.opener.requests), 1)
        snap_path = os.path.join(e.d, "slot1.snap")
        with open(snap_path, "r", encoding="utf-8") as f:
            self.assertEqual(f.read(), "a")

    def test_c2_explicit_notify_false_contract_preserved(self):
        c = cfg(mode="REQUIRED_NOTIFY")
        e = Env(["a", "b"])
        e.run(c)
        self.assertEqual(engine.run_slot(c, e.d, fetch=e.fetch, notify=lambda n, m: False), "notify_failed")

    def test_r4_explicit_snapshot_only_honest_distinct_status_and_advance_no_notify(self):
        c = cfg(mode="SNAPSHOT_ONLY", notify="webhook:https://example.invalid/hook")
        e = Env(["a", "b"])
        self.assertEqual(e.run(c), "stored")
        self.assertEqual(e.run(c), "snapshot_changed")
        self.assertEqual(len(e.opener.requests), 0)
        snap_path = os.path.join(e.d, "slot1.snap")
        with open(snap_path, "r", encoding="utf-8") as f:
            self.assertEqual(f.read(), "b")

    def test_r5_omitted_mode_remains_legacy_snapshot_only_and_malformed_mode_bad_config(self):
        c = cfg(notify="webhook:https://example.invalid/hook")
        e = Env(["a", "b"])
        self.assertEqual(e.run(c), "stored")
        self.assertEqual(e.run(c), "snapshot_changed")
        self.assertEqual(len(e.opener.requests), 0)

        for bad in ("UNKNOWN", 123, ["REQUIRED_NOTIFY"], {"m": "REQUIRED_NOTIFY"}):
            e_bad = Env(["a"])
            c_bad = cfg(mode=bad)
            self.assertEqual(e_bad.run(c_bad), "bad_config")

    def test_fetch_failure_snapshot_only_does_not_notify_writes_fail(self):
        c = cfg(mode="SNAPSHOT_ONLY", notify="webhook:https://example.invalid/hook")
        e = Env(["a", OSError("fetch error")])
        self.assertEqual(e.run(c), "stored")
        self.assertEqual(e.run(c), "fetch_failed")
        self.assertEqual(len(e.opener.requests), 0)
        fail_path = os.path.join(e.d, "slot1.fail")
        self.assertTrue(os.path.isfile(fail_path))

if __name__ == "__main__":
    unittest.main()
