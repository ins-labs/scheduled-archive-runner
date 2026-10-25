import io, json, os, stat, sys, tempfile, unittest
from unittest import mock
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
import notifier, snapshot_codec

FAKE_AGE = os.path.join(os.path.dirname(__file__), "fake_age")


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


class CodecTest(unittest.TestCase):
    def test_plain_round_trip(self):
        c = {"codec": "plain", "public": True}
        self.assertEqual(snapshot_codec.decode(snapshot_codec.encode("hello\nworld", c), c), "hello\nworld")

    def test_age_round_trip_with_shim(self):
        c = {"codec": "age", "age_bin": FAKE_AGE, "age_recipient": "age1test", "age_identity": "AGE-SECRET-KEY-TEST"}
        enc = snapshot_codec.encode("private bytes 123", c)
        self.assertNotIn("private", enc)
        self.assertIn("AGE-TEST-BEGIN", enc)
        self.assertEqual(snapshot_codec.decode(enc, c), "private bytes 123")

    def test_age_requires_identity_and_recipient(self):
        with self.assertRaises(ValueError):
            snapshot_codec.encode("x", {"codec": "age", "age_bin": FAKE_AGE})
        with self.assertRaises(ValueError):
            snapshot_codec.decode("x", {"codec": "age", "age_bin": FAKE_AGE, "age_recipient": "r"})

    def test_unknown_codec_rejected(self):
        with self.assertRaises(ValueError):
            snapshot_codec.encode("x", {"codec": "zip"})

    def test_missing_codec_rejected(self):
        with self.assertRaises(ValueError):
            snapshot_codec.encode("x", {})

    def test_plain_requires_public_true(self):
        for cfg in ({"codec": "plain"}, {"codec": "plain", "public": False}, {"codec": "plain", "public": "yes"}):
            with self.assertRaises(ValueError):
                snapshot_codec.encode("x", cfg)


class NotifierTest(unittest.TestCase):
    def test_empty_and_missing_name_returns_false(self):
        self.assertFalse(notifier.notify("", "watch x: changed a -> b"))
        self.assertFalse(notifier.notify(None, "watch x: changed a -> b"))

    def test_invalid_sink_types_returns_false(self):
        for bad in (123, [], {}, True, False):
            self.assertFalse(notifier.notify(bad, "m"))

    def test_unknown_and_non_https_refused(self):
        self.assertFalse(notifier.notify("pagerduty:x", "m"))
        self.assertFalse(notifier.notify("webhook:http://insecure/hook", "m"))

    def test_webhook_posts_json(self):
        op = ConfigurableFakeOpener(status=200)
        ok = notifier.notify("webhook:https://hooks.example/t", "watch slot1: changed aaa -> bbb", opener=op)
        self.assertTrue(ok)
        self.assertEqual(len(op.requests), 1)
        self.assertEqual(op.requests[0].full_url, "https://hooks.example/t")
        self.assertIn("slot1", op.requests[0].data.decode())

    def test_webhook_failure_returns_false(self):
        op = ConfigurableFakeOpener(exc=OSError("down"))
        self.assertFalse(notifier.notify("webhook:https://hooks.example/t", "m", opener=op))

    def test_non_2xx_returns_false(self):
        op = ConfigurableFakeOpener(status=500)
        self.assertFalse(notifier.notify("webhook:https://hooks.example/t", "m", opener=op))


class CliTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.mkdtemp()
        self.old = dict(os.environ)

    def tearDown(self):
        os.environ.clear(); os.environ.update(self.old)

    def _run(self, cfg):
        import run_slot_cli
        os.environ["SLOT_CONFIG_JSON"] = json.dumps(cfg)
        os.environ["SLOT_STATE_DIR"] = os.path.join(self.tmp, "snap")
        return run_slot_cli.main()

    def _run_captured(self, cfg_or_raw):
        import run_slot_cli
        if isinstance(cfg_or_raw, str):
            os.environ["SLOT_CONFIG_JSON"] = cfg_or_raw
        else:
            os.environ["SLOT_CONFIG_JSON"] = json.dumps(cfg_or_raw)
        os.environ["SLOT_STATE_DIR"] = os.path.join(self.tmp, "snap")
        out = io.StringIO()
        with mock.patch("sys.stdout", out):
            code = run_slot_cli.main()
        return code, out.getvalue()

    def _cfg(self, **kw):
        c = {"id": "t1", "adapter": "command", "target": "/bin/cat " + os.path.join(self.tmp, "live.txt"),
             "notify": "", "codec": "plain", "public": True}
        c.update(kw); return c

    def _live(self, text):
        with open(os.path.join(self.tmp, "live.txt"), "w") as f:
            f.write(text)

    def test_skip_without_config(self):
        code, stdout = self._run_captured("")
        self.assertEqual(code, 0)
        self.assertEqual(stdout, "skip: slot not configured\n")

    def test_plain_cycle_stores_then_unchanged_then_changed(self):
        self._live("v1")
        code, stdout = self._run_captured(self._cfg())
        self.assertEqual(code, 0)
        self.assertEqual(stdout, "stored\n")
        snap = os.path.join(self.tmp, "snap", "t1.snap")
        self.assertEqual(open(snap).read(), "v1")
        self._live("v2")
        code, stdout = self._run_captured(self._cfg())
        self.assertEqual(code, 0)
        self.assertEqual(stdout, "snapshot_changed\n")
        self.assertEqual(open(snap).read(), "v2")

    def test_age_cycle_commits_ciphertext_only(self):
        self._live("secret-v1")
        c = self._cfg(codec="age", age_bin=FAKE_AGE, age_recipient="age1t", age_identity="AGE-SECRET-KEY-T")
        self._run(c)
        committed = open(os.path.join(self.tmp, "snap", "t1.snap.age")).read()
        self.assertNotIn("secret-v1", committed)
        self._live("secret-v2")
        self._run(c)
        committed2 = open(os.path.join(self.tmp, "snap", "t1.snap.age")).read()
        self.assertNotIn("secret-v2", committed2)
        self.assertNotEqual(committed, committed2)

    def test_missing_codec_fails_closed(self):
        self._live("x")
        c = self._cfg()
        del c["codec"]
        code, stdout = self._run_captured(c)
        self.assertEqual(code, 2)
        self.assertEqual(stdout, "bad_config\n")
        self.assertFalse(os.path.exists(os.path.join(self.tmp, "snap")))

    def test_plain_without_public_fails_closed(self):
        self._live("x")
        c = self._cfg()
        del c["public"]
        code, stdout = self._run_captured(c)
        self.assertEqual(code, 2)
        self.assertEqual(stdout, "bad_config\n")
        self.assertFalse(os.path.exists(os.path.join(self.tmp, "snap")))

    def test_fail_marker_persists_across_runs(self):
        c = self._cfg(target="/bin/cat " + os.path.join(self.tmp, "missing.txt"))
        self._run(c)
        self.assertTrue(os.path.isfile(os.path.join(self.tmp, "snap", "t1.fail")))
        self._run(c)
        self.assertTrue(os.path.isfile(os.path.join(self.tmp, "snap", "t1.fail")))
        self._live("recovered")
        self._run(self._cfg())
        self.assertFalse(os.path.exists(os.path.join(self.tmp, "snap", "t1.fail")))

    def test_slot_3_docs_watch_config_with_cli_adapter(self):
        cli_script = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", "adapters", "cli.js"))
        cli_script_clean = cli_script.replace('\\', '/')
        mock_runner = os.path.join(self.tmp, "mock_runner.js")
        with open(mock_runner, "w", encoding="utf-8") as f:
            f.write(f"globalThis.fetch=async()=>({{ok:true,text:async()=>'<h1>Telegram Bot API</h1><p>Mock Docs</p>'}});require('{cli_script_clean}')")
        cfg = {
            "id": "docs_watch_telegram_api",
            "adapter": "command",
            "target": f"/usr/bin/node {mock_runner} coreTelegramOrg",
            "normalize": [],
            "notify": "",
            "codec": "plain",
            "public": True
        }
        if os.path.exists("/usr/bin/node"):
            code, stdout = self._run_captured(cfg)
            self.assertEqual(code, 0)
            self.assertEqual(stdout, "stored\n")
            snap_file = os.path.join(self.tmp, "snap", "docs_watch_telegram_api.snap")
            self.assertTrue(os.path.isfile(snap_file))
            with open(snap_file, "r", encoding="utf-8") as f:
                content = f.read()
            self.assertEqual(content, "Telegram Bot API Mock Docs")

    def test_cli_snapshot_only_persists_snapshot_and_reports_snapshot_changed(self):
        self._live("v1")
        c = self._cfg(mode="SNAPSHOT_ONLY")
        code1, stdout1 = self._run_captured(c)
        self.assertEqual(code1, 0)
        self.assertEqual(stdout1, "stored\n")
        snap = os.path.join(self.tmp, "snap", "t1.snap")
        self.assertEqual(open(snap).read(), "v1")
        self._live("v2")
        code2, stdout2 = self._run_captured(c)
        self.assertEqual(code2, 0)
        self.assertEqual(stdout2, "snapshot_changed\n")
        self.assertEqual(open(snap).read(), "v2")

    def test_c1_cli_omitted_mode_defaults_snapshot_only(self):
        self._live("v1")
        c = self._cfg() # mode key omitted
        code1, stdout1 = self._run_captured(c)
        self.assertEqual(code1, 0)
        self.assertEqual(stdout1, "stored\n")
        self._live("v2")
        code2, stdout2 = self._run_captured(c)
        self.assertEqual(code2, 0)
        self.assertEqual(stdout2, "snapshot_changed\n")

    def test_c1_cli_explicit_null_mode_returns_bad_config_exit_2(self):
        self._live("v1")
        raw = json.dumps(self._cfg(mode=None))
        code, stdout = self._run_captured(raw)
        self.assertEqual(code, 2)
        self.assertEqual(stdout, "bad_config\n")
        self.assertFalse(os.path.exists(os.path.join(self.tmp, "snap")))

    def test_c3_cli_notify_failed_returns_exit_1_exact_stdout_no_persistence(self):
        self._live("v1")
        c = self._cfg(mode="REQUIRED_NOTIFY", notify="")
        code1, stdout1 = self._run_captured(c)
        self.assertEqual(code1, 0)
        self.assertEqual(stdout1, "stored\n")
        snap = os.path.join(self.tmp, "snap", "t1.snap")
        self.assertEqual(open(snap).read(), "v1")

        self._live("v2")
        code2, stdout2 = self._run_captured(c)
        self.assertEqual(code2, 1) # Exit 1 for notify_failed!
        self.assertEqual(stdout2, "notify_failed\n")
        self.assertEqual(open(snap).read(), "v1") # Snapshot file retained as v1!

    def test_c3_cli_required_notify_succeeds_with_real_notifier_and_fake_opener(self):
        self._live("v1")
        c = self._cfg(mode="REQUIRED_NOTIFY", notify="webhook:https://example.invalid/hook")
        op = ConfigurableFakeOpener(status=200)
        with mock.patch("urllib.request.build_opener", return_value=op):
            code1, stdout1 = self._run_captured(c)
            self.assertEqual(code1, 0)
            self.assertEqual(stdout1, "stored\n")

            self._live("v2")
            code2, stdout2 = self._run_captured(c)
            self.assertEqual(code2, 0)
            self.assertEqual(stdout2, "changed\n")
            snap = os.path.join(self.tmp, "snap", "t1.snap")
            self.assertEqual(open(snap).read(), "v2")
            self.assertEqual(len(op.requests), 1)

    def test_cli_bad_mode_returns_bad_config_exit_2(self):
        self._live("v1")
        c = self._cfg(mode="INVALID_MODE")
        code, stdout = self._run_captured(c)
        self.assertEqual(code, 2)
        self.assertEqual(stdout, "bad_config\n")
        self.assertFalse(os.path.exists(os.path.join(self.tmp, "snap")))


if __name__ == "__main__":
    unittest.main()
