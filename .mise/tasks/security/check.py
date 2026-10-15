#!/usr/bin/env -S uv run --locked python
# fmt: off
#MISE description="Verify current security approval and an optional Trivy report"
# fmt: on

from hass_portainer_ee_tools.security import security_check_main

raise SystemExit(security_check_main())
