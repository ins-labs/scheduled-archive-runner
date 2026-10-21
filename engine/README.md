# watch-engine
Generic LLM-free diff engine for scheduled watch slots (ins-infra#191, step 1 of #182). Stdlib only, no names or secrets.
Run tests: `cd watch-engine && python3 -m unittest discover -s tests`.
Slot config keys: id, adapter (http-get|command), target, normalize (regex strip rules), notify (notifier name), allowed_hosts (required for http-get: non-empty list of hostnames the target and any redirect targets must match, exact and case-insensitive). The command adapter runs the target without a shell: configs are trusted data owned by the operator, never user input.
Snapshot codec (snapshot_codec.py): plain or age (pinned, sha256-verified age binary; recipient in config, identity only via the slot secret). No default codec: a slot must set "codec" explicitly, and "plain" additionally requires "public": true - plain means the content is public on the internet in this repo. Missing/unknown codec = bad_config, exit 2, nothing written. Notifier (notifier.py): generic HTTPS webhook, message = slot id + short hash only, never content. CLI (run_slot_cli.py): runs one slot from SLOT_CONFIG_JSON (per-slot secret SLOT_<n>_CONFIG), commits snapshots/<id>.snap[.age]; prints only the status word. Scheduling: .github/workflows/slot.yml (daily + dispatch, matrix over slot numbers; workflow YAML names no tasks).

## Example `SLOT_1_CONFIG` (Generic Scheduled Archive Task)
```json
{
  "id": "scheduled_archive",
  "adapter": "command",
  "target": "/usr/bin/node launch.cjs",
  "normalize": ["^::add-mask::.*"],
  "notify": "webhook:https://example.com/webhook-path",
  "codec": "age",
  "age_bin": "/tmp/age/age",
  "age_recipient": "age1example...",
  "age_identity": "AGE-SECRET-KEY-1...",
  "source_host": "db.example.internal:27017",
  "source_identity": "archive-reader",
  "source_key": "secret-source-password",
  "encryption_key": "passphrase-for-backup-encryption",
  "remote_identity": "storage-account@example.invalid",
  "remote_key": "storage-account-password",
  "namespace": "source-db",
  "collection": "validation-coll",
  "archive_prefix": "archive-v1-",
  "receipt_prefix": "archive-state-v1-",
  "folder_name": "remote-folder",
  "folder_handle": "remote-handle",
  "retention_enabled": true,
  "required_index_keys": ["recordId"],
  "clock_timezone": "UTC",
  "clock_hour": "00"
}
```

## Example `SLOT_3_CONFIG` (Generic Documentation)
```json
{
  "id": "docs_watch_source",
  "adapter": "command",
  "target": "/usr/bin/node /path/to/adapters/cli.js coreTelegramOrg https://core.telegram.org/bots/api",
  "normalize": [],
  "notify": "webhook:https://example.com/webhook-path",
  "codec": "plain",
  "public": true
}
```
