#!/usr/bin/env bash
set -euo pipefail
url='https://github.com/FiloSottile/age/releases/download/v1.3.2/age-v1.3.2-linux-amd64.tar.gz'
expected='cbe24006683f8eb669266162894b9a522a1af52f2665fbc63a4bb032ed26ac10'
# Fail closed before integrity check or extraction. No retry or pin relaxation.
curl --fail --silent --show-error --location --output /tmp/age.tar.gz "$url"
# A successful HTTP response can still contain an error page or other non-archive bytes.
tar -tzf /tmp/age.tar.gz >/dev/null
printf '%s  %s\n' "$expected" /tmp/age.tar.gz | sha256sum -c -
tar -xzf /tmp/age.tar.gz -C /tmp
