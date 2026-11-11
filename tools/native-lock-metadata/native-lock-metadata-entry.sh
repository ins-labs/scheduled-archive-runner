#!/bin/sh
# Proposed native runtime entry. SOURCE ONLY, NOT executed or selected.
set -u
umask 077
INPUT=${LOCK_INPUT_DIR:-"$PWD/lock-input"}
WORK=$(mktemp -d /tmp/mongodb78-metadata.XXXXXX) || exit 1
cleanup() { rm -rf "$WORK"; }
trap cleanup EXIT HUP INT TERM
mkdir "$WORK/job" "$WORK/home" "$WORK/cache" "$WORK/output" || exit 1
OUT="$WORK/output"
OVERALL=1
STATUS="$OUT/status.txt"
printf '%s\n' 'metadata-only; no dependency install, tests, imports, DB or storage access' > "$OUT/scope.txt"
printf '%s\n' 'fa0d9096576b8a472756855c2898e052ff406a70' > "$OUT/base.txt"
printf '%s\n' 'resolver=NOTRUN' 'validation=NOTRUN' > "$STATUS"
# Copy only an individually allowed regular non-symlink file. Never follow a symlink.
safe_copy() {
 if [ -f "$1" ] && [ ! -L "$1" ]; then cp "$1" "$2"; else return 1; fi
}
# Return whatever allowed diagnostic evidence exists even after a failed resolver/validation.
packet() {
 cd "$OUT" || return 1
 : > SHA256SUMS
 set --
 for FILE in base.txt scope.txt status.txt input-sha256sums.txt input-package.json input-package-lock.json output-package.json output-package-lock.json node-version.txt npm-version.txt resolver.log resolver-exit.txt validation.log; do
  if [ -f "$FILE" ] && [ ! -L "$FILE" ]; then
   sha256sum "$FILE" >> SHA256SUMS || return 1
   set -- "$@" "$FILE"
  fi
 done
 sha256sum -c SHA256SUMS || return 1
 tar -czf "$WORK/lock-metadata.tar.gz" "$@" SHA256SUMS || return 1
 SIZE=$(wc -c < "$WORK/lock-metadata.tar.gz") || return 1
 if [ "$SIZE" -gt 262144 ]; then
  printf '%s\n' 'PACKET_OVERSIZE: no artifact emitted; custody incomplete'
  return 1
 fi
 printf '%s\n' 'BEGIN_LOCK_METADATA_PACKET'
 sha256sum "$WORK/lock-metadata.tar.gz" || return 1
 printf 'bytes=%s\n' "$SIZE"
 base64 "$WORK/lock-metadata.tar.gz" || return 1
 printf '%s\n' 'END_LOCK_METADATA_PACKET'
}
prepare() {
 for FILE in package.json package-lock.json INPUT-SHA256SUMS; do
  if [ ! -f "$INPUT/$FILE" ] || [ -L "$INPUT/$FILE" ]; then
   printf 'input_file_%s=FAIL_regular_nonsymlink_required\n' "$FILE" >> "$STATUS"
   return 1
  fi
 done
 safe_copy "$INPUT/INPUT-SHA256SUMS" "$OUT/input-sha256sums.txt" || return 1
 safe_copy "$INPUT/package.json" "$OUT/input-package.json" || return 1
 safe_copy "$INPUT/package-lock.json" "$OUT/input-package-lock.json" || return 1
 # Manifest contents are reviewed source and contain exactly the two expected relative paths.
 (cd "$INPUT" && sha256sum -c INPUT-SHA256SUMS) > "$OUT/validation.log" 2>&1
 RC=$?
 printf 'input_hashes_rc=%s\n' "$RC" >> "$STATUS"
 [ "$RC" -eq 0 ] || return 1
 cp "$OUT/input-package.json" "$WORK/job/package.json" || return 1
 cp "$OUT/input-package-lock.json" "$WORK/job/package-lock.json" || return 1
 node --version > "$OUT/node-version.txt" 2>&1 || return 1
 npm --version > "$OUT/npm-version.txt" 2>&1 || return 1
 cd "$WORK/job" || return 1
 if [ -e node_modules ] || [ -L node_modules ]; then
  printf '%s\n' 'pre_node_modules=FAIL_unexpected' >> "$STATUS"
  return 1
 fi
 printf '%s\n' 'pre_node_modules=PASS_absent' >> "$STATUS"
 env -i PATH="$PATH" HOME="$WORK/home" MONGOMS_DISABLE_POSTINSTALL=1 npm_config_cache="$WORK/cache" npm_config_userconfig=/dev/null npm_config_globalconfig=/dev/null npm_config_registry=https://registry.npmjs.org npm install --package-lock-only --ignore-scripts --save-exact --no-audit --no-fund mongodb@7.8.0 > "$OUT/resolver.log" 2>&1
 RC=$?
 printf '%s\n' "$RC" > "$OUT/resolver-exit.txt"
 printf 'resolver_rc=%s\n' "$RC" >> "$STATUS"
 VALID=0
 if [ -e node_modules ] || [ -L node_modules ]; then
  printf '%s\n' 'post_node_modules=FAIL_unexpected_excluded_from_packet' >> "$STATUS"
  VALID=1
 else
  printf '%s\n' 'post_node_modules=PASS_absent' >> "$STATUS"
 fi
 if safe_copy package.json "$OUT/output-package.json"; then
  printf '%s\n' 'output_manifest=PASS_regular_nonsymlink_captured' >> "$STATUS"
  if cmp "$OUT/output-package.json" "$OUT/input-package.json" >> "$OUT/validation.log" 2>&1; then
   printf '%s\n' 'manifest_identity=PASS_unchanged' >> "$STATUS"
  else
   printf '%s\n' 'manifest_identity=FAIL_drift_captured' >> "$STATUS"
   VALID=1
  fi
 else
  printf '%s\n' 'output_manifest=FAIL_missing_or_symlink_excluded' >> "$STATUS"
  VALID=1
 fi
 if safe_copy package-lock.json "$OUT/output-package-lock.json"; then
  printf '%s\n' 'output_lock=PASS_regular_nonsymlink_captured_semantics_UNVERIFIED' >> "$STATUS"
 else
  printf '%s\n' 'output_lock=FAIL_missing_or_symlink_excluded' >> "$STATUS"
  VALID=1
 fi
 # No parser here: malformed contents, lock roots/integrity/graph require independent review.
 printf '%s\n' 'lock_semantics=UNVERIFIED_independent_review_required' >> "$STATUS"
 if [ "$RC" -ne 0 ] || [ "$VALID" -ne 0 ]; then return 1; fi
 return 0
}
prepare
OVERALL=$?
printf 'entry_validation_rc=%s\n' "$OVERALL" >> "$STATUS"
if ! packet; then
 printf '%s\n' 'FAIL: evidence packet incomplete; no custody completion claim'
 exit 1
fi
if [ "$OVERALL" -ne 0 ]; then
 printf '%s\n' 'FAIL: diagnostic packet retained; resolver or source validation failed'
 exit 1
fi
printf '%s\n' 'LOCK_METADATA_RESOLUTION_COMPLETE_SEMANTIC_REVIEW_REQUIRED'
# Neither a diagnostic packet nor resolver exit0 adopts a lock or qualifies the application.
