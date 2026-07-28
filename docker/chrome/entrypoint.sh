#!/bin/sh
set -eu

Xvfb "${DISPLAY}" -screen 0 1280x900x24 -nolisten tcp &
xvfb_pid=$!

cleanup() {
  kill "${xvfb_pid}" 2>/dev/null || true
}
trap cleanup EXIT INT TERM

exec google-chrome-stable \
  --remote-debugging-address=0.0.0.0 \
  --remote-debugging-port=9222 \
  --user-data-dir=/var/lib/chrome/profile \
  --no-first-run \
  --no-default-browser-check \
  about:blank
