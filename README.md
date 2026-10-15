# Portainer BE for Home Assistant OS

[![CI](https://github.com/ne1800/hass-portainer-ee/actions/workflows/ci.yml/badge.svg)](https://github.com/ne1800/hass-portainer-ee/actions/workflows/ci.yml)

Portainer Business Edition packaged as a Home Assistant app for `amd64` and
`aarch64` (ARM64). Published images have versioned tags, pinned upstream bases,
and keyless Cosign signatures.

The default update channel is STS. An explicitly reviewed **LTS security
bridge** may temporarily replace STS when a security fix requires it. The
current app version, Portainer version, channel, matching Edge Agent and image
digests are recorded together in [release.yaml](release.yaml). See the
[latest release](https://github.com/ne1800/hass-portainer-ee/releases/latest)
for the published version and its security assessment.

This fork is based on
[`MikeJMcGuire/hass-portainer-ee`](https://github.com/MikeJMcGuire/hass-portainer-ee).
It does not maintain a separate regular LTS branch.

## Install

1. Open the Home Assistant app store and its **Repositories** menu.
2. Add `https://github.com/ne1800/hass-portainer-ee` and install **Portainer BE STS**.
3. Read the permission warning below, then disable the app's protection mode.
4. In the app's network settings, explicitly assign host port `9443` to
   `9443/tcp`. All port mappings are disabled initially to avoid conflicts.
   Enable `8000/tcp` only if an Edge tunnel is required. Keep the optional
   legacy HTTP port `9000/tcp` disabled unless it is specifically needed.
5. Stop any older Portainer app using the same ports, then start this app
   manually. Open `https://<HAOS-HOST>:9443` using the host port you configured.
6. For a fresh installation, read the setup token locally in the app's logs,
   create the administrator account, and supply a valid Portainer BE license.
   Follow [Portainer's initial setup](https://docs.portainer.io/start/install/server/setup).
   For a migration, follow the [operator guide](portaineree/DOCS.md) before starting.

Home Assistant Ingress is not supported. Portainer initially supplies a
self-signed HTTPS certificate. Configure a certificate trusted by your clients
before routine use. Never publish setup tokens, license keys or unredacted logs.

## Security and backups

`docker_api: true` requires protection mode to be disabled. Portainer receives
administrative Docker access: compromise can affect containers, their data and
host functions. Use a private network, administrative users, and trusted
images, archives and Git sources. Do not expose the app directly to the internet.

A Portainer backup contains its configuration, users, license information,
endpoints and stack metadata. It does **not** back up workload containers or
volumes. Back up those data separately. Restore a Portainer backup only into a
fresh app instance with an empty `/data` directory.

The current upstream binary still has temporarily accepted HIGH findings.
Their scope, operating restrictions and expiration are documented in
[accepted risks](security/accepted-risks.yaml) and [.trivyignore.yaml](.trivyignore.yaml).
Exceptions are neither permanent nor transferred automatically to another app
version. New or missing findings, an expired approval or changed operating
conditions block publication. See [SECURITY.md](SECURITY.md) for supported
versions and the private vulnerability reporting process.

## Development and verification

Use Mise for all repository workflows:

```bash
mise install
mise run setup
mise run check
mise run release:check
mise run build
mise run security:scan
```

`mise run lint` invokes the pinned pre-commit hook repositories with
`prek run --all-files`; formatting hooks may update files and show their diff.
`mise run test` runs deterministic tests independently, and `mise run check`
runs both gates. `mise run hooks:install` optionally installs a Prek pre-commit
hook without replacing a custom hooks path.

Mise manages the tools; Python-based tasks use `uv run --locked` and the
committed `uv.lock`. No globally installed Python packages are required.
`mise run setup` verifies tools and configuration and does not change Git
identity or hooks. GitHub Actions also scans introduced Git history for secrets:
deleting a leaked value in a later commit does not undo the disclosure.

`mise run update:check` checks official Portainer releases and manifests daily
and on demand. A detected update prepares a reviewable PR, while the existing
security approval stays bound to its reviewed image. The PR can therefore have
a failing security gate until a maintainer assesses the new build. Updates are
never merged, published or installed automatically.

Renovate maintains Mise tools, Python dependencies and `uv.lock`, pre-commit
hooks, GitHub Actions and Dockerfile dependencies through PRs. Python runtime
updates stay within the supported project line. Portainer channel selection
remains under the dedicated updater; no dependency update merges automatically.

## Documentation and support

- [App operator guide](portaineree/DOCS.md)
- [Release runbook](docs/runbooks/release.md)
- [Report a non-security issue](https://github.com/ne1800/hass-portainer-ee/issues/new/choose)
- [Report a vulnerability privately](https://github.com/ne1800/hass-portainer-ee/security/advisories/new)

The wrapper repository is covered by [GPL-3.0](LICENSE). Portainer Business
Edition has its own upstream license terms and requires a valid BE license;
the wrapper license does not grant a Portainer BE license.

Host-specific migration procedures, infrastructure inventories, credentials,
private addresses and agent planning artifacts do not belong in this public
repository. Portainer API clients, CLI and MCP tooling are separate projects.
