#!/usr/bin/env bash
set -eu
SENTRY_LAUNCH_DIR="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"
exec /home/sketch/.venvs/sentry-ubuntu/bin/python \
  "$SENTRY_LAUNCH_DIR/sentry_launch.py" \
  --config /home/sketch/.config/sentry/config.json \
  "$@"
