#!/bin/sh
set -eu

payload="$(curl --fail --silent --show-error --max-time 3 http://127.0.0.1:9222/json/version)"
printf '%s' "${payload}" | grep -q '"Browser"[[:space:]]*:[[:space:]]*"Chrome/'
printf '%s' "${payload}" | grep -q '"webSocketDebuggerUrl"[[:space:]]*:[[:space:]]*"ws://'
