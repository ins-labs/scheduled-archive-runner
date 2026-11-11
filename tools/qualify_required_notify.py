"""Review-only candidate vehicle. Stdlib, reviewed fixture transport guards, exactly64 named cases.
Writes public fixture-only reports to qualification-results, not live slot state.
"""
import ast
import hashlib
import json
import os
from pathlib import Path
import socket
import subprocess
import sys
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]
os.chdir(ROOT)
EXPECTED = {'adapters/cli.js': '7b6dc9244f724280394c0de789e1d946ead89b547dcdb61ff07003e47ed0bf4f', 'adapters/coreTelegramOrg.js': 'c9fa4f924688ead40e27a2babd014d1e17679bf9ea415a55e3edaf7d87a8981a', 'adapters/githubReleaseFeed.js': '21a9be07978f239290f285cf69f68d08b207ff454e0d1376e4f874ff1d19673d', 'adapters/utils.js': 'ce6f05f35d779882caef1076ef93394dba2e224269528b90055f4eff38848957', 'engine/README.md': '2036c549c6c4df9dec294f77395bd87d617e2f0fcef7ec8327394576eda0f2a8', 'engine/engine.py': '9c56a55074aafaee9874c96ea01564d5b368e6689361b306e073c70b657bd10e', 'engine/notifier.py': 'e96e339875c876daca3d247aab3ff06f234ac94601ba58c50b24c104438c1a57', 'engine/run_slot_cli.py': 'cf9eda3fd20f452688f0bd90ecd02089b9910930873e38793926ac10ccdd43c9', 'engine/snapshot_codec.py': 'fc4595babd88e4b8f0979023ca3beacb6341c36ce3240ab862f2dad8d5f12a62', 'engine/tests/fake_age': 'da487d84e40a8fff60fc225f4b254482b30ada5372806004d8ad60487a2da608', 'engine/tests/test_engine.py': 'ba2b2b0fe1cd1bdb673baa9a1018b9e3c6f070076474549d14d5ac41566d1c15', 'engine/tests/test_port.py': '88850f9ee8dae090f27f70fd40749106b03e19cfa54d0f3074f340811541df60'}
REPORT = ROOT / "qualification-results"
REPORT.mkdir(exist_ok=True)
import contextlib
import io
import tarfile
ENTRY = ["tools/qualify_required_notify.py", ".github/workflows/required-notify-candidate.yml"]
# Bind entry to committed bytes, not circular hard-coded self hashes.
entry_expected = {name: hashlib.sha256(subprocess.check_output(["git", "show", "HEAD:" + name])).hexdigest() for name in ENTRY}
expected = dict(EXPECTED, **entry_expected)
def check_sources():
    actual = {}
    for name, digest in expected.items():
        path = ROOT / name
        actual[name] = hashlib.sha256(path.read_bytes()).hexdigest() if path.is_file() else None
    return {"expected": expected, "actual": actual,
            "equal": all(actual.get(name) == digest for name, digest in expected.items())}

def run_fixtures():
    # Prevent Python transports, including direct socket use. Fake urllib openers
    # in the tests remain callable. Child Node is separately guarded below.
    def denied(*args, **kwargs):
        raise RuntimeError("network forbidden in candidate qualification")
    socket.socket.connect = denied
    socket.socket.connect_ex = denied
    socket.create_connection = denied
    socket.getaddrinfo = denied

    if not os.access("/usr/bin/node", os.X_OK):
        raise SystemExit("required adapter case would silently skip: /usr/bin/node missing")
    if not os.access(ROOT / "engine/tests/fake_age", os.X_OK):
        raise SystemExit("fake_age executable git mode missing")

    # No npm install is needed: cli.js and its two adapters use built-in Node APIs.
    # A preload blocks real networking while the test's explicit globalThis.fetch
    # fixture remains available. Unknown child commands still fail their own tests.
    with tempfile.TemporaryDirectory(prefix="notify-qualify-") as tmp:
        guard = Path(tmp) / "network-deny.cjs"
        guard.write_text("const deny=()=>{throw Error('network forbidden');};\n"
                         "require('node:net').connect=deny;require('node:net').createConnection=deny;\n"
                         "require('node:net').Socket.prototype.connect=deny;\n"
                         "require('node:http').request=deny;require('node:http').get=deny;\n"
                         "require('node:https').request=deny;require('node:https').get=deny;\n"
                         "require('node:tls').connect=deny;globalThis.fetch=deny;\n")
        # engine.default_fetch intentionally starts commands with env={}; intercept
        # only Popen env to pass this inert preload to Node child commands.
        original_popen = subprocess.Popen
        def guarded_popen(*args, **kwargs):
            env = kwargs.get("env")
            command = args[0] if args else kwargs.get("args")
            if env == {} and isinstance(command, (list, tuple)) and command and command[0] == "/usr/bin/node":
                kwargs["env"] = {"NODE_OPTIONS": "--require=" + str(guard)}
            return original_popen(*args, **kwargs)
        subprocess.Popen = guarded_popen
        sys.path.insert(0, str(ROOT / "engine"))
        sys.path.insert(0, str(ROOT / "engine/tests"))
        suite = unittest.defaultTestLoader.loadTestsFromNames(["test_engine", "test_port"])
        def leaves(item):
            for child in item:
                if isinstance(child, unittest.TestSuite):
                    yield from leaves(child)
                else:
                    yield child
        ids = [case.id() for case in leaves(suite)]
        expected_ids = []
        for module in ("test_engine", "test_port"):
            tree = ast.parse((ROOT / "engine/tests" / (module + ".py")).read_text())
            for cls in tree.body:
                if isinstance(cls, ast.ClassDef):
                    expected_ids.extend(module + "." + cls.name + "." + method.name
                                        for method in cls.body if isinstance(method, ast.FunctionDef)
                                        and method.name.startswith("test_"))
        if sorted(ids) != sorted(expected_ids):
            raise SystemExit("runtime test census differs from declared test IDs")
        (REPORT / "census.json").write_text(json.dumps(ids, indent=2) + "\n")
        print("TEST_CENSUS " + json.dumps(ids))
        if len(ids) != 64 or len(set(ids)) != 64:
            raise SystemExit("candidate census mismatch, expected64 unique cases")
        # Syntax scan without imports or execution beyond the explicit test suite.
        source_hashes = {}
        for path in sorted((ROOT / "engine").rglob("*.py")):
            ast.parse(path.read_text(), filename=str(path))
            source_hashes[str(path.relative_to(ROOT))] = hashlib.sha256(path.read_bytes()).hexdigest()
        result = unittest.TextTestRunner(stream=sys.stderr, verbosity=2).run(suite)
        report = {"head": subprocess.check_output(["git", "rev-parse", "HEAD"], text=True).strip(),
                  "tree": subprocess.check_output(["git", "rev-parse", "HEAD^{tree}"], text=True).strip(),
                  "run": result.testsRun, "failures": len(result.failures),
                  "errors": len(result.errors), "skips": len(result.skipped),
                  "source_hashes": source_hashes, "python": sys.version,
                  "node": subprocess.check_output(["/usr/bin/node", "--version"], text=True).strip()}
        (REPORT / "result.json").write_text(json.dumps(report, indent=2) + "\n")
        print(json.dumps(report, sort_keys=True))
        if not result.wasSuccessful() or result.skipped or result.testsRun != 64:
            raise SystemExit(1)

pre = check_sources()
(REPORT / "source-pre.json").write_text(json.dumps(pre, indent=2) + "\n")
phase_rc = 1
log = io.StringIO()
try:
    if not pre["equal"]:
        raise RuntimeError("source precheck failed")
    with contextlib.redirect_stdout(log), contextlib.redirect_stderr(log):
        run_fixtures()
    phase_rc = 0
except BaseException as exc:
    phase_rc = exc.code if isinstance(exc, SystemExit) and isinstance(exc.code, int) else 1
    if phase_rc == 0:
        phase_rc = 1
    log.write("qualification stopped: " + type(exc).__name__ + "\n")
finally:
    post = check_sources()
    (REPORT / "source-post.json").write_text(json.dumps(post, indent=2) + "\n")
    (REPORT / "tests.log").write_text(log.getvalue())
    # No successful qualification without complete census/result and postcheck.
    complete = all((REPORT / name).is_file() for name in ("census.json", "result.json"))
    final_rc = phase_rc if phase_rc else (0 if pre["equal"] and post["equal"] and complete else 1)
    identity = {"run_id": os.environ.get("QUALIFY_RUN_ID"), "attempt": os.environ.get("QUALIFY_RUN_ATTEMPT"),
                "job": os.environ.get("QUALIFY_JOB"),
                "head": subprocess.check_output(["git", "rev-parse", "HEAD"], text=True).strip(),
                "tree": subprocess.check_output(["git", "rev-parse", "HEAD^{tree}"], text=True).strip(),
                "phase_rc": phase_rc, "terminal_rc": final_rc, "complete": complete,
                "pre_equal": pre["equal"], "post_equal": post["equal"]}
    (REPORT / "identity.json").write_text(json.dumps(identity, indent=2) + "\n")
    members = sorted(path for path in REPORT.iterdir() if path.is_file())
    manifest = {path.name: {"bytes": path.stat().st_size, "sha256": hashlib.sha256(path.read_bytes()).hexdigest()} for path in members}
    (REPORT / "MANIFEST.json").write_text(json.dumps(manifest, indent=2) + "\n")
    with tarfile.open(ROOT / "qualification-evidence.tar.gz", "w:gz") as archive:
        for path in members + [REPORT / "MANIFEST.json"]:
            archive.add(path, arcname=path.name)
    data = (ROOT / "qualification-evidence.tar.gz").read_bytes()
    digest = hashlib.sha256(data).hexdigest()
    (ROOT / "qualification-evidence.sha256").write_text(digest + "  qualification-evidence.tar.gz\n")
    print(log.getvalue())
    print("EVIDENCE " + json.dumps({"bytes": len(data), "sha256": digest, **identity}, sort_keys=True))
raise SystemExit(final_rc)
