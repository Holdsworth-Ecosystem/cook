#!/usr/bin/env bash
# Deploy cook service and upgrade sturmey dependency.
#
# Usage: ssh holdsworth "bash ~/cook/scripts/deploy.sh"
set -euo pipefail

cd ~/cook
git pull
/home/holdsworth/.local/bin/uv lock --upgrade-package sturmey
/home/holdsworth/.local/bin/uv sync
sudo -n /usr/bin/systemctl restart cook
echo "✓ cook deployed (sturmey upgraded)"
