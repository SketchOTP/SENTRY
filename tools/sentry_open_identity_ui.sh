#!/usr/bin/env bash
set -eu
exec /home/sketch/.venvs/sentry-ubuntu/bin/python \
  /srv/ATLAS/100_ACTIVE/Projects/SENTRY/tools/sentry_launch.py \
  --config /home/sketch/.config/sentry/config.json
