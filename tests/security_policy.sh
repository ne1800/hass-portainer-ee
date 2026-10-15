#!/usr/bin/env bash
set -euo pipefail

# Preparation may leave approval bound to the old image. security:scan remains
# the release gate and requires approval for the current image and date.
uv run --locked python - <<'PYCODE'
from pathlib import Path
from hass_portainer_ee_tools.security import check_security_policy

check_security_policy(Path.cwd())
PYCODE
