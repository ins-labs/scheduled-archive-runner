# D:\ins migration tracker

Stopgap tracker (GitHub Issues unavailable: no PAT with Issues scope yet - see token-inventory gap below). Maintained by the bridge-operator agent.

## Scope
Sherbo-approved scope (2026-10-15 21:26): move ONLY ins-3d, ins-3d-tools, ins-scratch on D:, plus C-side ins-* tool trees. D:\Sources, Games, Media, SystemStorage, EFSTMPWP stay untouched. ProOnly build output goes to D:\Sources\OS next to its source ISO.

## Done
- [x] D:\ins hub created: tools, cache, downloads, outputs, scripts, configs, backups, restore (2026-10-15)
- [x] D:\ins-3d -> D:\ins\outputs\ins-3d (41 files / 39,779,788 B) - original renamed .pre-ins-migration
- [x] D:\ins-3d-tools -> D:\ins\tools\ins-3d-tools (5,801 files / 1,447,743,117 B) - original renamed .pre-ins-migration
- [x] D:\ins-scratch -> D:\ins\cache\ins-scratch - original renamed .pre-ins-migration
- [x] Legacy-path scripts patched to new D:\ins paths: install_tasks.ps1, run_proof.cmd, dl.cmd (0 remaining legacy refs)
- [x] en-US ISO downloaded + SHA-256 verified (Windows11_Client_x64_en-us_26300_9457.iso, 9,047,330,816 B)

## In progress
- [ ] C-side migration (task InsCMove): C:\ins-voice, C:\ins-xtts, C:\ins-asr, C:\ins-video, C:\piper -> D:\ins\tools\*; HF cache -> D:\ins\cache\huggingface; junctions C:\ins\<name> created post-move; originals renamed .pre-ins-migration
- [ ] en-US ProOnly ISO build (task InsProOnlyUS): extract -> dism export "Windows 11 Pro" index -> oscdimg -> D:\Sources\OS\Windows11_Client_x64_en-us_26300_9457_ProOnly.iso (mirrors the verified en-GB ProOnly method)

## Blocked / pending owner
- [ ] Token-inventory gap: NO GitHub PAT with Issues scope anywhere (createIssue denied 2026-10-15). This tracker file is the stopgap until a PAT with Issues scope exists; then migrate to a real issue.
- [ ] Case 20/20 pending-card cap (~226 active cards in one topic): awaiting owner decision on mass-expiry of stale cards.

## Restore points
All moved originals are preserved next to their old locations as <name>.pre-ins-migration. Reversal = rename back + remove junctions (C-side).
