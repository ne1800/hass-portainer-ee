# Portainer BE for Home Assistant OS

This repository builds a Home Assistant app with Portainer Business Edition
for `amd64` and `aarch64`. The default channel follows Portainer STS. An
explicitly configured LTS security bridge in `update-policy.yaml` is allowed
only when the STS line points to a newer LTS release for a security fix.

Current versions:

- App version: `2.45.2.1`
- Portainer Server: `2.45.2` LTS (configured security bridge)
- matching Edge Agent: `2.45.2`
- immutable server and agent base images pinned by manifest digest
- target image: `ghcr.io/ne1800/hass-portainer-ee:<app-version>`

The project is based on
[`MikeJMcGuire/hass-portainer-ee`](https://github.com/MikeJMcGuire/hass-portainer-ee).
The upstream maintainer remains the source for the regular LTS channel; this
fork does not maintain a second LTS branch.

## Security boundaries

Portainer requires administrative access to the Home Assistant OS Docker API.
The app's protection mode must therefore be disabled deliberately. A
compromised Portainer instance would consequently control containers and host
functions. Run the app only on a private network, only for administrators, and
only with trusted images, Git sources, and credentials.

Home Assistant Ingress is not used. The UI and Edge tunnel are exposed directly
through the configured ports `8000`, `9000`, and `9443`. Never bind two
Portainer apps to the same host ports at the same time.

A Portainer backup contains Portainer configuration, but not data from managed
containers or volumes. Restore a backup only into a fresh app instance with an
empty `/data` directory.

Portainer `2.45.2` follows the configured LTS security bridge and resolves
GHSA-jxhm-qq8x-v4c6. A fresh Trivy scan still reports ten HIGH findings in the
upstream binary; the temporary baseline in `security/accepted-risks.yaml`
requires explicit owner approval before publication. Its exceptions expire
on `2026-11-14`. New or missing high-severity findings, changed trust
boundaries, or a new server or agent build block release approval. The
Windows-only Docker CLI finding does not affect this Linux app; the other
archive, BuildKit and Go findings retain the private administrator-only
operating restrictions documented with the baseline.

## Development and verification

Run the complete local verification workflow through Mise:

```bash
mise install
mise run setup
mise run check
mise run release:check
mise run build
mise run security:scan
```

`mise run lint` invokes the pinned pre-commit hook repositories through
`prek run --all-files`; canonical formatting hooks may update files and show
their diff. `mise run test` runs the deterministic project tests separately,
and `mise run check` runs both gates in that order. In a normal clone,
`mise run hooks:install` may be used explicitly to install the Prek pre-commit
hook. The task refuses to replace an existing custom hooks path.

Mise installs the pinned Prek, Gitleaks, Python 3.13, `uv`, Actionlint, and
Hadolint versions. Hook-managed tools are installed in isolated environments
from the revisions in `.pre-commit-config.yaml`. Release and update commands are
direct Python-based Mise tasks; `uv run --locked` resolves their environment
from the committed `uv.lock`. No globally installed Python packages are part of
the workflow. `mise run setup` only verifies required tools and configuration.
It does not change Git identity or hooks. Maintainers configure their own Git
identity and optional local push guards outside the tracked public repository.

GitHub Actions separately uses the official Gitleaks action with a complete
checkout to inspect the Git history introduced by a push or pull request. A
secret is still compromised if a later commit deletes it: rotate the value and
consider rewriting the affected history instead of treating the deletion as a
fix.

`mise run update:check` checks official Portainer releases and the server and
agent manifests daily and on demand. A detected update may create at most one
reviewable pull request. It is never merged, published, or installed on a
production system automatically. A new image version remains blocked until
its security baseline has been reviewed explicitly.

Renovate maintains general Mise, Python/PEP 621, `uv.lock`, pre-commit hook
revisions, GitHub Actions, and Dockerfile dependencies through pull requests.
Portainer channel changes remain entirely under the dedicated update checker;
Renovate never merges anything automatically.

The Python Portainer client, a Portainer CLI, and MCP access for agents are a
separate follow-up project by design. This repository initially publishes only
the verified Home Assistant app and its secure release chain.

## Documentation

- [App operator guide](portaineree/DOCS.md)
- [Release runbook](docs/runbooks/release.md)

Specific migration, host, and agent runbooks are site-specific and do not
belong in this public fork.

Public documentation contains no passwords, JWTs, Edge keys, license data, or
private addresses. Keep those values outside the repository in files with
restrictive permissions.
