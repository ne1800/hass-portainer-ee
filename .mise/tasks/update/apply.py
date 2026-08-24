#!/usr/bin/env -S uv run --locked python
# fmt: off
#MISE description="Apply validated Portainer update output reproducibly"
# fmt: on

from hass_portainer_ee_tools.cli import update_apply_main

raise SystemExit(update_apply_main())
