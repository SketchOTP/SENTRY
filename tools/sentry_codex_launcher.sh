#!/bin/sh
# Ubuntu confines unprivileged user namespaces for ordinary user-systemd
# services.  The installed Codex desktop AppArmor profile permits Codex's own
# Bubblewrap sandbox setup; enter it only for this fixed Codex binary.
exec /usr/bin/aa-exec -p chatgpt -- /usr/lib/chatgpt/resources/codex "$@"
