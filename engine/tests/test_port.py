import json, os, stat, sys, tempfile, unittest
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
import notifier, snapshot_codec

FAKE_AGE = os.path.join(os.path.dirname(__file__), "fake_age")


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
    def test_empty_name_ok_noop(self):
        self.assertTrue(notifier.notify("", "watch x: changed a -> b"))

    def test_unknown_and_non_https_refused(self):
        self.assertFalse(notifier.notify("pagerduty:x", "m"))
        self.assertFalse(notifier.notify("webhook:http://insecure/hook", "m"))

    def test_webhook_posts_json(self):
        class R:
            status = 200
            def __enter__(self): return self
            def __exit__(self, *a): return False
        seen = {}
        class Op:
            def open(self, req, timeout=0):
                seen["url"] = req.full_url
                seen["body"] = req.data.decode()
                return R()
        ok = notifier.notify("webhook:https://hooks.example/t", "watch slot1: changed aaa -> bbb", opener=Op())
        self.assertTrue(ok)
        self.assertIn("slot1", seen["body"])
        self.assertTrue(seen["url"].startswith("https://"))

    def test_webhook_failure_returns_false(self):
        class Op:
            def open(self, req, timeout=0):
                raise OSError("down")
        self.assertFalse(notifier.notify("webhook:https://hooks.example/t", "m", opener=Op()))


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

    def _cfg(self, **kw):
        c = {"id": "t1", "adapter": "command", "target": "/bin/cat " + os.path.join(self.tmp, "live.txt"),
             "notify": "", "codec": "plain", "public": True}
        c.update(kw); return c

    def _live(self, text):
        with open(os.path.join(self.tmp, "live.txt"), "w") as f:
            f.write(text)

    def test_skip_without_config(self):
        os.environ["SLOT_CONFIG_JSON"] = ""
        import run_slot_cli
        self.assertEqual(run_slot_cli.main(), 0)

    def test_plain_cycle_stores_then_unchanged_then_changed(self):
        self._live("v1")
        self.assertEqual(self._run(self._cfg()), 0)
        snap = os.path.join(self.tmp, "snap", "t1.snap")
        self.assertEqual(open(snap).read(), "v1")
        self._live("v2")
        self._run(self._cfg())
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
        # no codec in config: CLI returns 2 and writes nothing
        self._live("x")
        c = self._cfg()
        del c["codec"]
        self.assertEqual(self._run(c), 2)
        self.assertFalse(os.path.exists(os.path.join(self.tmp, "snap")))

    def test_plain_without_public_fails_closed(self):
        self._live("x")
        c = self._cfg()
        del c["public"]
        self.assertEqual(self._run(c), 2)
        self.assertFalse(os.path.exists(os.path.join(self.tmp, "snap")))

    def test_fail_marker_persists_across_runs(self):
        c = self._cfg(target="/bin/cat " + os.path.join(self.tmp, "missing.txt"))
        # fetch fails both runs (notify is a no-op); the marker must persist across runs
        self._run(c)
        self.assertTrue(os.path.isfile(os.path.join(self.tmp, "snap", "t1.fail")))
        self._run(c)
        self.assertTrue(os.path.isfile(os.path.join(self.tmp, "snap", "t1.fail")))
        self._live("recovered")
        self._run(self._cfg())
        self.assertFalse(os.path.exists(os.path.join(self.tmp, "snap", "t1.fail")))


if __name__ == "__main__":
    unittest.main()
