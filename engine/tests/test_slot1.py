import json, os, sys, tempfile, unittest, subprocess

engine_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
if engine_dir not in sys.path:
    sys.path.insert(0, engine_dir)

import run_slot_cli

class Slot1Test(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.mkdtemp()
        self.old_env = dict(os.environ)

    def tearDown(self):
        os.environ.clear()
        os.environ.update(self.old_env)

    def test_launch_cjs_fallback_to_slot_1_config(self):
        launch_path = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", "launch.cjs"))
        res = subprocess.run(["which", "node"], capture_output=True, text=True)
        node_cmd = res.stdout.strip() if res.returncode == 0 else "node"

        # Missing source_host causes launch.cjs to fail gracefully with generic message
        slot1_cfg = {
            "id": "slot1",
            "adapter": "command",
            "target": f"{node_cmd} {launch_path}",
            "normalize": [],
            "notify": "",
            "codec": "plain",
            "public": True
        }

        os.environ["SLOT_1_CONFIG"] = json.dumps(slot1_cfg)
        os.environ["SLOT_CONFIG_JSON"] = json.dumps(slot1_cfg)
        os.environ["SLOT_STATE_DIR"] = os.path.join(self.tmp, "snap")

        # launch.cjs outputs failure message and exits with status 1
        # default_fetch reports command failed with exit code 1 -> engine status fetch_failed
        ret = run_slot_cli.main()
        self.assertEqual(ret, 0)
        fail_file = os.path.join(self.tmp, "snap", "slot1.fail")
        self.assertTrue(os.path.isfile(fail_file), "Fail marker was not created for failed launch execution")

if __name__ == "__main__":
    unittest.main()
