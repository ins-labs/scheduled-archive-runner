import json, os, sys, tempfile, unittest

engine_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
repo_dir = os.path.abspath(os.path.join(engine_dir, ".."))
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
        launch_path = os.path.join(repo_dir, "launch.cjs").replace("\\", "/")
        runner_path = os.path.join(repo_dir, "runner.cjs").replace("\\", "/")

        node_cmd = "/usr/bin/node"

        eval_code = f"const fs=require('fs'),path=require('path');const r=path.resolve('{runner_path}');require.cache[r]={{id:r,filename:r,loaded:true,exports:{{main:async()=>{{const sd=process.env.RUNNER_SECRETS_DIR;if(!sd)throw Error('missing secrets dir');const secret=n=>fs.readFileSync(path.join(sd,n),'utf8').trim();if(secret('mongo-uri')!=='mongodb+srv://testuser:testpass@db.example.com/?retryWrites=true&w=majority'||secret('encryption-passphrase')!=='encpass'||secret('mega-email')!=='megauser'||secret('mega-password')!=='megapass')throw Error('secret verification failed');if(process.env.SOURCE_NAMESPACE!=='example'||process.env.VALIDATION_COLLECTION!=='records'||process.env.ARCHIVE_PREFIX!=='test-v1-'||process.env.RECEIPT_PREFIX!=='test-state-v1-'||process.env.REMOTE_FOLDER_NAME!=='test-folder'||process.env.REMOTE_FOLDER_HANDLE!=='test-handle')throw Error('env verification failed');console.log('Archive operation verified');}}}}}};require('{launch_path}');"

        wrapper_js = os.path.join(self.tmp, "run_launch.js").replace("\\", "/")
        with open(wrapper_js, "w", encoding="utf-8") as f:
            f.write(eval_code)

        slot1_secrets = {
            "source_host": "db.example.com",
            "source_identity": "testuser",
            "source_key": "testpass",
            "encryption_key": "encpass",
            "remote_identity": "megauser",
            "remote_key": "megapass",
            "namespace": "example",
            "collection": "records",
            "archive_prefix": "test-v1-",
            "receipt_prefix": "test-state-v1-",
            "folder_name": "test-folder",
            "folder_handle": "test-handle"
        }

        # Format SLOT_1_CONFIG without spaces so command adapter split() delivers single argument to env
        env_arg = "SLOT_1_CONFIG=" + json.dumps(slot1_secrets, separators=(",", ":"))
        target_cmd = f"/usr/bin/env {env_arg} {node_cmd} {wrapper_js}"

        slot1_cfg = {
            "id": "slot1",
            "adapter": "command",
            "target": target_cmd,
            "normalize": ["(?m)^::add-mask::.*$"],
            "notify": "",
            "codec": "plain",
            "public": True
        }

        os.environ.clear()
        os.environ["SLOT_1_CONFIG"] = json.dumps(slot1_cfg)
        os.environ["SLOT_CONFIG_JSON"] = json.dumps(slot1_cfg)
        os.environ["SLOT_STATE_DIR"] = os.path.join(self.tmp, "snap")

        ret = run_slot_cli.main()
        self.assertEqual(ret, 0)
        snap_file = os.path.join(self.tmp, "snap", "slot1.snap")
        self.assertTrue(os.path.isfile(snap_file), "Snapshot file was not created")
        with open(snap_file, "r", encoding="utf-8") as f:
            content = f.read()
        self.assertEqual(content, "Archive operation verified")

if __name__ == "__main__":
    unittest.main()
