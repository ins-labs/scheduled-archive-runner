"""CLI entry for one watch slot. Stdlib only; no names, no secrets in code.

Environment:
  SLOT_CONFIG_JSON  - the full slot config JSON (from the per-slot secret):
                      engine keys (id, adapter, target, normalize, notify,
                      allowed_hosts, mode) plus codec keys (codec, age_bin,
                      age_recipient, age_identity).
  SLOT_STATE_DIR    - directory holding committed snapshots (default: ./snapshots)

Behaviour: decrypts the stored snapshot (if encrypted) into a private temp
state dir, runs the audited engine against it, and re-encrypts when the
snapshot changed. Prints ONLY the engine status word. Exit 0 always except a
missing/invalid config (exit 2), so one bad slot never fails the matrix.
"""
import json, os, sys, tempfile

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import engine, notifier, snapshot_codec


def main():
    raw = os.environ.get("SLOT_CONFIG_JSON", "").strip()
    if not raw:
        print("skip: slot not configured")
        return 0
    try:
        cfg = json.loads(raw)
    except ValueError:
        print("bad_config")
        return 2

    store = os.environ.get("SLOT_STATE_DIR", "snapshots")
    sid = str(cfg.get("id", ""))
    try:
        codec = snapshot_codec._codec(cfg)
    except ValueError:
        print("bad_config")
        return 2
    ext = ".snap.age" if codec == "age" else ".snap"
    committed = os.path.join(store, sid + ext)

    with tempfile.TemporaryDirectory(prefix=".slot.") as tmp:
        os.chmod(tmp, 0o700)
        # seed the private state dir from the committed snapshot and fail marker
        failmark = os.path.join(store, sid + ".fail")
        if os.path.isfile(failmark):
            open(os.path.join(tmp, sid + ".fail"), "w").write("1")
        if os.path.isfile(committed):
            try:
                plain = snapshot_codec.decode(open(committed, encoding="utf-8").read(), cfg)
            except ValueError:
                print("error")
                return 0
            with open(os.path.join(tmp, sid + ".snap"), "w", encoding="utf-8") as f:
                f.write(plain)

        status = engine.run_slot(cfg, tmp, notify=notifier.notify)

        if status == "bad_config":
            print("bad_config")
            return 2

        if status in ("stored", "changed", "snapshot_changed"):
            try:
                out = snapshot_codec.encode(open(os.path.join(tmp, sid + ".snap"),
                                                 encoding="utf-8").read(), cfg)
            except ValueError:
                print("error")
                return 0
            os.makedirs(store, exist_ok=True)
            fd, tmppath = tempfile.mkstemp(dir=store, prefix=".w.")
            with os.fdopen(fd, "w", encoding="utf-8") as f:
                f.write(out)
            os.replace(tmppath, committed)
        # persist the fail marker (contains no content, just "1")
        if os.path.isfile(os.path.join(tmp, sid + ".fail")):
            os.makedirs(store, exist_ok=True)
            open(failmark, "w").write("1")
        elif os.path.isfile(failmark):
            os.unlink(failmark)
    print(status)
    return 0


if __name__ == "__main__":
    sys.exit(main())
