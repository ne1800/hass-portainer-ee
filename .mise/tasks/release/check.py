#!/usr/bin/env -S uv run --locked python
# fmt: off
#MISE description="Verify release metadata and image pins"
# fmt: on

from hass_portainer_ee_tools.cli import release_check_main

raise SystemExit(release_check_main())
