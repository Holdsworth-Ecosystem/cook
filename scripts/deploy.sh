#!/usr/bin/env bash
# Deploy cook service and upgrade sturmey dependency.
#
# Usage: ssh holdsworth "bash ~/cook/scripts/deploy.sh"
set -euo pipefail

cd ~/cook
git pull
# bash loads the whole script into memory at invocation, so if this very
# script was just updated by the git pull above, we're still running the old
# version. Re-exec once with a sentinel to pick up the new script before
# running any of the deploy steps below.
if [[ "${_DEPLOY_RELOADED:-}" != "1" ]]; then
    export _DEPLOY_RELOADED=1
    exec bash "$0" "$@"
fi
/home/holdsworth/.local/bin/uv sync
# Alembic needs DDL which the per-service role lacks. Run as the
# holdsworth owner role via peer-auth on the unix socket.
ALEMBIC_DATABASE_URL="postgresql+asyncpg://holdsworth@/holdsworth?host=/var/run/postgresql" \
    /home/holdsworth/.local/bin/uv run alembic upgrade head
sudo -n /usr/bin/systemctl restart cook
systemctl is-active --quiet cook || { echo "✗ cook failed to start"; exit 1; }
echo "✓ cook deployed"
