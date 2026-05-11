#!/bin/sh
set -eu

PUID="${PUID:-99}"
PGID="${PGID:-100}"

# If running as root and PUID/PGID don't match the baked-in user, rewrite it.
if [ "$(id -u)" = "0" ]; then
    current_uid="$(id -u jellyswipe)"
    current_gid="$(id -g jellyswipe)"
    if [ "$current_uid" != "$PUID" ] || [ "$current_gid" != "$PGID" ]; then
        groupmod -o -g "$PGID" jellyswipe
        usermod  -o -u "$PUID" -g "$PGID" jellyswipe
    fi
    # Ensure /app/data is writable by the runtime user. Fast no-op when correct.
    chown -R jellyswipe:jellyswipe /app/data
    exec gosu jellyswipe "$@"
fi

# Already non-root (e.g. user passed `--user` on `docker run`). Exec directly;
# operator is responsible for ensuring /app/data is writable.
exec "$@"
