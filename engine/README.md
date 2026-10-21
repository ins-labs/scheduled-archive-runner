# watch-engine
Generic LLM-free diff engine for scheduled watch slots (ins-infra#191, step 1 of #182). Stdlib only, no names or secrets.
Run tests: `cd engine && python3 -m unittest discover -s tests`.
Slot config keys: id, adapter (http-get|command), target, normalize (regex strip rules), notify (notifier name), allowed_hosts (required for http-get: non-empty list of hostnames the target and any redirect targets must match, exact and case-insensitive). The command adapter runs the target without a shell: configs are trusted data owned by the operator, never user input.
Snapshot codec (snapshot_codec.py): plain or age (pinned, sha256-verified age binary; recipient in config, identity only via the slot secret). No default codec: a slot must set "codec" explicitly, and "plain" additionally requires "public": true - plain means the content is public on the internet in this repo. Missing/unknown codec = bad_config, exit 2, nothing written. Notifier (notifier.py): generic HTTPS webhook, message = slot id + short hash only, never content. CLI (run_slot_cli.py): runs one slot from SLOT_CONFIG_JSON (per-slot secret SLOT_<n>_CONFIG), commits snapshots/<id>.snap[.age]; prints only the status word. Scheduling: .github/workflows/slot.yml (daily + dispatch, matrix over slot numbers; workflow YAML names no tasks).

## Example `SLOT_1_CONFIG` (Generic Scheduled Archive Task)
Main/owner sets the real `SLOT_1_CONFIG` secret in repository secrets; it is never committed to the repository.

```json
{
  "id": "<slot-id>",
  "adapter": "command",
  "target": "/usr/bin/env SLOT_1_CONFIG=<slot-1-json> /usr/bin/node launch.cjs",
  "normalize": ["^::add-mask::.*"],
  "notify": "webhook:<webhook-url>",
  "codec": "age",
  "age_bin": "<path-to-age-binary>",
  "age_recipient": "<age-public-key>",
  "age_identity": "<age-secret-identity>",
  "source_host": "<db-host-and-port>",
  "source_identity": "<source-username>",
  "source_key": "<source-key>",
  "encryption_key": "<encryption-passphrase>",
  "remote_identity": "<remote-email>",
  "remote_key": "<remote-password>",
  "namespace": "<source-db-name>",
  "collection": "<validation-collection>",
  "archive_prefix": "<archive-prefix>",
  "receipt_prefix": "<receipt-prefix>",
  "folder_name": "<remote-folder-name>",
  "folder_handle": "<remote-folder-handle>",
  "retention_enabled": true,
  "required_index_keys": ["<index-key>"],
  "clock_timezone": "<timezone>",
  "clock_hour": "<hour-24h>"
}
```

## Example `SLOT_3_CONFIG` (Generic Documentation)
```json
{
  "id": "docs_watch_source",
  "adapter": "command",
  "target": "/usr/local/bin/slot-node adapters/cli.js multi coreTelegramOrg:https://core.telegram.org/bots/api|githubReleaseFeed:owner:repo|githubReleaseFeed:owner2:repo2",
  "normalize": [],
  "notify": "",
  "codec": "plain",
  "public": true
}
```

## Snapshot persistence

Snapshots commit to the `slot-snapshots` branch (protected `main` rejects direct pushes). Each slot job restores that branch into a `state/` worktree, runs the engine with `SLOT_STATE_DIR=state/snapshots`, then commits and pushes only when the snapshot changed.
