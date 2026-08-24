# Release runbook

This runbook publishes an already verified, immutable multi-architecture image.
It changes neither Home Assistant nor Synology. Every GitHub push and every
GitHub release requires its own deliberate approval.

## 1. Local prerequisites

- The worktree and index are clean.
- Git identity and push guards stay outside the tracked public repository.
- GitHub account protection and branch protection have been reviewed.
- GitHub Actions may create update pull requests; no workflow may approve or
  merge them.
- The planned app tag exists neither as a Git tag nor as a GHCR reference.

Run this sequence unchanged in a fresh checkout:

```bash
mise install
mise run setup
mise run check
mise run release:check
mise run build
mise run security:scan
```

Mise installs the pinned Prek, Gitleaks, Python, and `uv` versions, and the
Python-based tasks use the committed `uv.lock`. `mise run check` scans the
current tree and runs lint and tests through Prek. `mise run setup` verifies
tools, configuration, and task files but does not configure an identity or
hook. GitHub Actions separately scans the Git history introduced by the push
with the official Gitleaks action.

Before every GitHub push, inspect the complete diff. The agent then stops,
announces the target repository and branch, and waits for the owner's explicit
approval. Only then may `main` be pushed.

## 2. Wait for CI on `main`

After the approved push, CI on `main` must complete successfully. Verify the
Gitleaks history scan, Prek checks, release consistency, local build, security
baseline, and native builds for `amd64` and `aarch64`.

A missing or additional high-severity finding blocks the release. A new
Portainer version must not inherit the baseline from an older app version
automatically.

## 3. Create the GitHub release

The immutable release tag for the first version is `v2.44.0.1`. It must point to
a commit on `main` and match `release.yaml` exactly. Example after another
explicit approval:

```bash
mise exec -- gh release create v2.44.0.1 \
  --repo ne1800/hass-portainer-ee \
  --target main \
  --title "Portainer BE STS 2.44.0.1" \
  --notes "Home Assistant wrapper 2.44.0.1 with Portainer BE 2.44.0 for amd64 and aarch64."
```

The release workflow publishes only the exact app version and the two internal
architecture tags. Moving tags such as `latest`, `sts`, or `lts` are
prohibited. Do not retry a partially failed push under the same tag; give the
correction a new wrapper revision.

## 4. Verify GHCR independently

After the workflow succeeds, explicitly set the GitHub package visibility to
`public`. The following manifest check uses a fresh anonymous registry
configuration:

```bash
registry_config="$(mktemp -d)"
REGCTL_CONFIG="${registry_config}/regctl.json" \
  mise exec -- regctl manifest get \
  ghcr.io/ne1800/hass-portainer-ee:2.44.0.1
manifest_digest="$(
  REGCTL_CONFIG="${registry_config}/regctl.json" \
    mise exec -- regctl image digest \
    ghcr.io/ne1800/hass-portainer-ee:2.44.0.1
)"
[[ "$manifest_digest" =~ ^sha256:[0-9a-f]{64}$ ]]
```

The manifest may contain only `linux/amd64` and `linux/arm64`. Then verify the
keyless signature against the release workflow:

```bash
mise exec -- cosign verify \
  --certificate-identity-regexp \
  '^https://github.com/ne1800/hass-portainer-ee/.github/workflows/release.yml@refs/tags/v2.44.0.1$' \
  --certificate-oidc-issuer https://token.actions.githubusercontent.com \
  "ghcr.io/ne1800/hass-portainer-ee@${manifest_digest}"
```

Also check both platforms for the labels `io.hass.type=app`,
`io.hass.version=2.44.0.1`, and their respective architecture. Only a
successful anonymous pull proves that Home Assistant can use the package
without GitHub credentials.

## 5. Hand off to migration

Add the repository to the Home Assistant app store only after CI is green and
the release workflow, public anonymous pull, manifest check, signature check,
and security scan all succeed. Production migration follows a separately
maintained site-specific operating procedure and is not part of this public
fork.

`mise run update:check` and Renovate may prepare pull requests in the future.
They may neither merge nor create releases or update systems.
