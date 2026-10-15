# Security policy

## Supported versions

Security maintenance targets the app version declared in
[release.yaml](release.yaml) and its reviewed Portainer channel. Older wrapper
versions are not maintained in parallel. The default channel is STS; only
explicitly configured LTS security bridges are eligible for updates.

An update PR is a proposal, not security approval. Maintainers must review the
exact server and agent images, scan both app architectures and assess any
remaining findings before publishing. Existing exceptions do not approve a new
app version automatically. Exceptions and expiration dates are recorded in
[security/accepted-risks.yaml](security/accepted-risks.yaml) and
[.trivyignore.yaml](.trivyignore.yaml). A scan with new, missing or expired
findings blocks the final app manifest.

## Report a vulnerability privately

Use GitHub's [private vulnerability reporting](https://github.com/ne1800/hass-portainer-ee/security/advisories/new).
Include the affected app and Portainer versions, architecture, a minimal
reproduction, impact and any workaround. Do not open a public issue containing
an exploit, credentials or sensitive configuration. Reports are reviewed by
the maintainer; there is no guaranteed response time or upstream support SLA.

Never submit passwords, JWTs, API or Edge keys, setup tokens, license data,
private addresses, backups or full configuration exports. Share only minimal
redacted evidence. For a vulnerability in Portainer itself, also consult
[Portainer's security policy](https://github.com/portainer/portainer/security/policy).

## Operating boundary

Portainer requires administrative Docker access and disabled Home Assistant
protection mode. Restrict it to private networks and administrators, and use
only trusted images, archives and Git sources. Internet exposure or broader
user access requires another assessment. A Portainer configuration backup does
not include managed workload data or volumes.

The repository's GPL-3.0 license covers the wrapper project. Portainer Business
Edition has separate upstream license terms and requires its own valid license.
