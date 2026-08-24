#!/usr/bin/env -S uv run --locked python
# fmt: off
#MISE description="Check official Portainer releases for allowed updates"
# fmt: on

from hass_portainer_ee_tools.cli import update_check_main

raise SystemExit(update_check_main())
