"""Snapshot content codecs for the slot engine. Stdlib only.

A codec turns normalized snapshot text into stored file bytes and back.
- "plain": public content; stored as UTF-8 text (docs-style public sources).
- "age": private content; stored as age ciphertext. The age BINARY path comes
  from cfg["age_bin"] (workflow downloads a pinned, hash-verified age); the
  recipient public key rides in cfg["age_recipient"] (not secret); the secret
  identity string arrives via cfg["age_identity"] (from the slot secret) and is
  written to a 0600 temp file only for the decrypt call, then removed.
"""
import os, subprocess, tempfile

CODECS = ("plain", "age")


def _age(cfg, args, data):
    try:
        p = subprocess.run([cfg["age_bin"]] + args, input=data.encode(),
                           stdout=subprocess.PIPE, stderr=subprocess.PIPE, timeout=60)
    except (OSError, subprocess.TimeoutExpired):
        raise ValueError("age exec")
    if p.returncode != 0:
        raise ValueError("age failed")
    return p.stdout.decode()


def _codec(cfg):
    # Fail closed: a slot must name its codec explicitly, and "plain" (stored
    # in this public repo) additionally requires cfg["public"] == true.
    codec = cfg.get("codec")
    if codec not in CODECS:
        raise ValueError("codec")
    if codec == "plain" and cfg.get("public") is not True:
        raise ValueError("public")
    return codec


def encode(text, cfg):
    codec = _codec(cfg)
    if codec == "plain":
        return text
    if codec == "age":
        if not cfg.get("age_recipient"):
            raise ValueError("age_recipient")
        return _age(cfg, ["-r", cfg["age_recipient"], "-a"], text)
    raise ValueError("codec")


def decode(stored, cfg):
    codec = _codec(cfg)
    if codec == "plain":
        return stored
    if codec == "age":
        ident = cfg.get("age_identity")
        if not ident:
            raise ValueError("age_identity")
        fd, path = tempfile.mkstemp(prefix=".id.")
        try:
            os.fchmod(fd, 0o600)
            with os.fdopen(fd, "w") as f:
                f.write(ident + "\n")
            return _age(cfg, ["-d", "-i", path, "-a"], stored)
        finally:
            try:
                os.unlink(path)
            except OSError:
                pass
    raise ValueError("codec")
