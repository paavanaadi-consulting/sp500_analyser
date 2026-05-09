#!/usr/bin/env sh
# Wait for Docker Engine, then ensure the sp500_analyser compose stack is running.
# Use from a macOS LaunchAgent (login or when the Docker socket appears) so the
# scheduler comes back after Docker Desktop starts.

COMPOSE_DIR="$(CDPATH= cd -- "$(dirname "$0")/.." && pwd)"
cd "$COMPOSE_DIR" || exit 1

i=0
while ! docker info >/dev/null 2>&1; do
  i=$((i + 1))
  if [ "$i" -gt 120 ]; then
    echo "docker-compose-up-when-ready: Docker not ready after 240s" >&2
    exit 1
  fi
  sleep 2
done

exec docker compose up -d
