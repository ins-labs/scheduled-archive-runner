import json, os, sys, unittest
from unittest import mock

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "..", "tools"))
import notify_failure


class WebhookExtraction(unittest.TestCase):
    def test_valid(self):
        self.assertEqual(notify_failure._webhook(json.dumps({"notify": "webhook:https://example.invalid/hook"})), "https://example.invalid/hook")

    def test_rejects_non_https_and_unknown(self):
        self.assertEqual(notify_failure._webhook(json.dumps({"notify": "webhook:http://x"})), "")
        self.assertEqual(notify_failure._webhook(json.dumps({"notify": "email:a@b"})), "")
        self.assertEqual(notify_failure._webhook(json.dumps({})), "")
        self.assertEqual(notify_failure._webhook("not json"), "")


class MainFlow(unittest.TestCase):
    def test_no_config_noop_success(self):
        with mock.patch.dict(os.environ, {}, clear=True):
            self.assertEqual(notify_failure.main([]), 0)

    def test_posts_through_first_configured(self):
        sent = []
        class FakeResp:
            status = 200
            def __enter__(self): return self
            def __exit__(self, *a): return False
        class FakeOpener:
            def open(self, req, timeout=30):
                sent.append((req.full_url, req.data))
                return FakeResp()
        env = {"SLOT_2_CONFIG": json.dumps({"notify": "webhook:https://example.invalid/hook"}),
               "NOTIFY_MESSAGE": "slot 2: watch run failed https://example.invalid/run/1"}
        with mock.patch.dict(os.environ, env, clear=True), \
             mock.patch.object(notify_failure.urllib.request, "build_opener", return_value=FakeOpener()):
            self.assertEqual(notify_failure.main(["1", "2", "3"]), 0)
        self.assertEqual(len(sent), 1)
        self.assertEqual(sent[0][0], "https://example.invalid/hook")
        self.assertIn(b"slot 2", sent[0][1])

    def test_send_failure_still_exit_zero(self):
        class FailOpener:
            def open(self, req, timeout=30): raise OSError("down")
        env = {"SLOT_CONFIG_JSON": json.dumps({"notify": "webhook:https://example.invalid/hook"})}
        with mock.patch.dict(os.environ, env, clear=True), \
             mock.patch.object(notify_failure.urllib.request, "build_opener", return_value=FailOpener()):
            self.assertEqual(notify_failure.main(), 0)


if __name__ == "__main__":
    unittest.main()
