#!/usr/bin/env -S uv run --locked python
# fmt: off
#MISE description="Require complete successful main CI for the release commit"
# fmt: on

from hass_portainer_ee_tools.release_ci import release_ci_main

raise SystemExit(release_ci_main())
