#!/bin/sh
# SOURCE ONLY. Requires explicit native execution selection after source/supply review.
set -u
umask 077
SOURCE=$PWD
WORK=$(mktemp -d /tmp/issue51-compat.XXXXXX) || exit 1
trap 'rm -rf "$WORK"' EXIT
# Signal exit removes temporary files, but does not prove descendant mongod termination.
# Parent must pause provider and verify every owned container TASK_KILLED before release.
trap 'exit 143' HUP INT TERM
mkdir "$WORK/job" "$WORK/home" "$WORK/cache" "$WORK/bin" "$WORK/data" || exit 1
: > "$WORK/user.npmrc"
: > "$WORK/global.npmrc"
run_checks() {
 [ "$(uname -m)" = x86_64 ] || return 1
 grep -qw avx /proc/cpuinfo || return 1
 grep -q '^ID=ubuntu$' /etc/os-release || return 1
 grep -q '^VERSION_ID="24.04"$' /etc/os-release || return 1
 [ "$(node --version)" = v22.23.4 ] || return 1
 [ "$(npm --version)" = 10.9.9 ] || return 1
 # Capture only the allowlisted public tooling-wrapper lock before strict hash admission.
 [ -f "$SOURCE/package-lock.json" ] && [ ! -L "$SOURCE/package-lock.json" ] || return 1
 [ "$(wc -c < "$SOURCE/package-lock.json")" -le 16384 ] || return 1
 printf '%s\n' BEGIN_WRAPPER_LOCK_DIAGNOSTIC
 sha256sum "$SOURCE/package-lock.json" || return 1
 wc -c < "$SOURCE/package-lock.json" || return 1
 base64 "$SOURCE/package-lock.json" || return 1
 printf '%s\n' END_WRAPPER_LOCK_DIAGNOSTIC
 (cd "$SOURCE" && sha256sum -c SOURCE-SHA256SUMS) || return 1
 cp -R "$SOURCE/candidate" "$WORK/job/" || return 1
 cp "$SOURCE/"*-fixture.cjs "$WORK/job/" || return 1
 cd "$WORK/job" || return 1
 test ! -e candidate/node_modules && test ! -L candidate/node_modules || return 1
 (cd candidate && sha256sum package.json package-lock.json) > "$WORK/before"
 (cd candidate && env -i PATH="$PATH" HOME="$WORK/home" MONGOMS_DISABLE_POSTINSTALL=1 npm_config_cache="$WORK/cache" npm_config_userconfig="$WORK/user.npmrc" npm_config_globalconfig="$WORK/global.npmrc" npm_config_registry=https://registry.npmjs.org npm ci --ignore-scripts --omit=dev --no-audit --no-fund) || return 1
 (cd candidate && sha256sum -c "$WORK/before") || return 1
 # Deliberate test execution, only after separately selected script-suppressed installation.
 (cd candidate && env -i PATH="$PATH" HOME="$WORK/home" MONGOMS_DISABLE_POSTINSTALL=1 npm test) || return 1
 env -i PATH="$PATH" HOME="$WORK/home" node srv-fixture.cjs || return 1
 env -i PATH="$PATH" HOME="$WORK/home" FIXTURE_ARCHIVE="$WORK/mongo.tgz" node "$SOURCE/supply-mongod.cjs" || return 1
 tar -tzf "$WORK/mongo.tgz" > "$WORK/members" || return 1
 grep -qx 'mongodb-linux-x86_64-ubuntu2404-8.0.34/bin/mongod' "$WORK/members" || return 1
 tar -xzf "$WORK/mongo.tgz" -C "$WORK/bin" --strip-components=2 mongodb-linux-x86_64-ubuntu2404-8.0.34/bin/mongod || return 1
 sha256sum "$WORK/bin/mongod"
 env -i PATH="$PATH" HOME="$WORK/home" MONGOMS_DISABLE_POSTINSTALL=1 MONGOMS_RUNTIME_DOWNLOAD=0 MONGOMS_SYSTEM_BINARY="$WORK/bin/mongod" FIXTURE_MONGOD="$WORK/bin/mongod" FIXTURE_DATA_DIR="$WORK/data" node local-fixture.cjs || return 1
 return 0
}
run_checks
RC=$?
printf 'ISSUE51_COMPATIBILITY_RC=%s\n' "$RC"
# Hold after result to avoid service-managed automatic retries. Parent stops on first receipt.
sleep 600
exit "$RC"
