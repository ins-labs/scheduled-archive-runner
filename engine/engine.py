"""Generic LLM-free diff engine for scheduled watch slots. Stdlib only. No names, no secrets in this file or in configs.

run_slot(cfg, state_dir, fetch, notify) -> 'stored' | 'unchanged' | 'changed' | 'snapshot_changed' | 'fetch_failed' | 'notify_failed' | 'bad_config' | 'error'
Never raises. Notifications carry the slot id and a short hash only, never the content."""
import hashlib, json, os, re, select, signal, subprocess, tempfile, time, urllib.parse, urllib.request

ADAPTERS = ("http-get", "command")
MODES = ("SNAPSHOT_ONLY", "REQUIRED_NOTIFY")
SLOT_ID = re.compile(r"^[A-Za-z0-9_.-]{1,64}$")
MAX_BYTES = 5 * 1024 * 1024


class ValidateResult(tuple):
    """3-tuple (sid, rules, mode) preserving backward compatibility with 2-tuple indexing/unpacking."""
    def __new__(cls, sid, rules, mode):
        return super().__new__(cls, (sid, rules, mode))
    @property
    def sid(self): return self[0]
    @property
    def rules(self): return self[1]
    @property
    def mode(self): return self[2]


class HTTPSOnlyRedirectHandler(urllib.request.HTTPRedirectHandler):
    def __init__(self, allowed_hosts=None):
        super().__init__()
        if allowed_hosts is None:
            self.allowed_hosts = []
        else:
            self.allowed_hosts = [h.lower() for h in allowed_hosts if isinstance(h, str)]

    def redirect_request(self, req, fp, code, msg, headers, newurl):
        joined = urllib.parse.urljoin(req.full_url, newurl)
        if not joined.startswith("https://"):
            raise ValueError("https redirect forbidden")
        host = urllib.parse.urlsplit(joined).hostname
        if not host or host.lower() not in self.allowed_hosts:
            raise ValueError("redirect host not allowed")
        return super().redirect_request(req, fp, code, msg, headers, newurl)


def validate(cfg):
    """Returns ValidateResult(slot_id, compiled normalize rules, mode) or raises ValueError."""
    if not isinstance(cfg, dict) or not SLOT_ID.match(str(cfg.get("id", ""))) or str(cfg["id"]).startswith("."):
        raise ValueError("id")
    if "mode" not in cfg:
        mode = "SNAPSHOT_ONLY"
    else:
        mode = cfg["mode"]
        if mode not in MODES:
            raise ValueError("mode")
    adapter = cfg.get("adapter")
    if adapter not in ADAPTERS or not isinstance(cfg.get("target"), str) or not cfg["target"]:
        raise ValueError("adapter")
    if adapter == "http-get":
        allowed_hosts = cfg.get("allowed_hosts")
        if not isinstance(allowed_hosts, list) or not allowed_hosts:
            raise ValueError("allowed_hosts")
        if not all(isinstance(h, str) and h for h in allowed_hosts):
            raise ValueError("allowed_hosts elements must be non-empty strings")
        target_host = urllib.parse.urlsplit(cfg["target"]).hostname
        if not target_host or target_host.lower() not in [h.lower() for h in allowed_hosts]:
            raise ValueError("target host not allowed")
    rules = cfg.get("normalize", [])
    if not isinstance(rules, list) or len(rules) > 50:
        raise ValueError("normalize")
    return ValidateResult(cfg["id"], [re.compile(r) for r in rules], mode)


def default_fetch(cfg, timeout=60):
    if cfg["adapter"] == "http-get":
        if not cfg["target"].startswith("https://"):
            raise ValueError("https only")
        opener = urllib.request.build_opener(
            HTTPSOnlyRedirectHandler(allowed_hosts=cfg.get("allowed_hosts"))
        )
        with opener.open(cfg["target"], timeout=timeout) as r:
            data = r.read(MAX_BYTES + 1)
    else:
        # Note: env={} removes PATH. Command targets must use absolute paths
        # (e.g. /bin/echo) and no shell quoting when env is cleared.
        proc = subprocess.Popen(
            cfg["target"].split(),
            stdout=subprocess.PIPE,
            stderr=subprocess.DEVNULL,
            env={},
            start_new_session=True
        )

        def _kill_pg():
            try:
                pgid = os.getpgid(proc.pid)
                os.killpg(pgid, signal.SIGKILL)
            except Exception:
                try:
                    proc.kill()
                except Exception:
                    pass
            try:
                proc.wait(timeout=2)
            except Exception:
                pass

        # Non-blocking fd: buffered read() could block past the deadline on a
        # slow-trickling child even after select() reports readable.
        os.set_blocking(proc.stdout.fileno(), False)
        data = bytearray()
        deadline = time.time() + timeout
        try:
            while True:
                rem = deadline - time.time()
                if rem <= 0:
                    _kill_pg()
                    raise ValueError("command timed out")

                r, _, _ = select.select([proc.stdout], [], [], min(rem, 0.1))
                if r:
                    try:
                        chunk = os.read(proc.stdout.fileno(), min(65536, MAX_BYTES + 1 - len(data)))
                    except BlockingIOError:
                        chunk = b""
                    if not chunk:
                        break  # EOF (child exited and pipe drained)
                    data.extend(chunk)
                    if len(data) > MAX_BYTES:
                        _kill_pg()
                        raise ValueError("oversize")

            proc.stdout.close()
            ret = proc.wait(timeout=5)
            if len(data) <= MAX_BYTES and ret != 0:
                raise ValueError("command failed with exit code %d" % ret)
        except Exception:
            _kill_pg()
            try:
                proc.stdout.close()
            except Exception:
                pass
            raise

    if len(data) > MAX_BYTES:
        raise ValueError("oversize")
    return data.decode("utf-8", "replace")


def normalize(text, rules):
    for r in rules:
        text = r.sub("", text)
    return "\n".join(l.rstrip() for l in text.strip().splitlines())


def _read(path):
    try:
        with open(path, "r", encoding="utf-8") as f:
            return f.read()
    except OSError:
        return None


def _write(path, data):
    fd, tmp = tempfile.mkstemp(dir=os.path.dirname(path), prefix=".w.")
    try:
        with os.fdopen(fd, "w") as f:
            f.write(data); f.flush(); os.fsync(f.fileno())
        os.chmod(tmp, 0o600); os.replace(tmp, path)
    except Exception:
        try: os.unlink(tmp)
        except OSError: pass
        raise


def run_slot(cfg, state_dir, fetch=default_fetch, notify=None):
    try:
        sid, rules, mode = validate(cfg)
    except (ValueError, re.error, KeyError, TypeError):
        return "bad_config"

    try:
        os.makedirs(state_dir, mode=0o700, exist_ok=True)
    except Exception:
        return "error"

    snap = os.path.join(state_dir, sid + ".snap")
    fail = os.path.join(state_dir, sid + ".fail")

    try:
        raw = fetch(cfg)
        if not raw:
            raise ValueError("empty response")
        cur = normalize(raw, rules)
        if not cur:
            raise ValueError("empty response")
    except Exception:
        if _read(fail) is None:                      # report once per transition
            if mode == "REQUIRED_NOTIFY":
                sink = cfg.get("notify", "")
                if not (notify and notify(sink, "watch %s: fetch failed" % sid)):
                    return "notify_failed"
                try:
                    _write(fail, "1")
                except Exception:
                    return "error"
            else:
                try:
                    _write(fail, "1")
                except Exception:
                    return "error"
        return "fetch_failed"

    if os.path.exists(fail):
        try:
            os.unlink(fail)
        except OSError:
            pass

    old = _read(snap)
    if old is None:
        try:
            _write(snap, cur)
        except Exception:
            return "error"
        return "stored"

    if old == cur:
        return "unchanged"

    if mode == "SNAPSHOT_ONLY":
        try:
            _write(snap, cur)
        except Exception:
            return "error"
        return "snapshot_changed"

    h = lambda t: hashlib.sha256(t.encode()).hexdigest()[:10]
    sink = cfg.get("notify", "")
    if not (notify and notify(sink, "watch %s: changed %s -> %s" % (sid, h(old), h(cur)))):
        return "notify_failed"                        # snapshot untouched: retried next run, not lost

    try:
        _write(snap, cur)
    except Exception:
        return "error"

    return "changed"
