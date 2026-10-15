# Release runbook

Publishing requires deliberate maintainer approval. A release publishes
versioned GHCR images; it does not install or update a production system.

## 1. Verify locally

Use a clean worktree. Configure Git identity
outside the tracked public repository. Before every GitHub push, inspect the complete outgoing diff and
Git history for secrets, private infrastructure data and planning artifacts.
Never include host-specific procedures or credentials in this repository.

```bash
mise install
eval "$(mise env -s bash)"
mise run setup
mise run check
mise run release:check
mise run build
mise run security:scan
```

Load the project environment once per shell before running tools such as `gh`,
`yq`, `regctl` or `cosign` directly. In Zsh, use `mise env -s zsh` instead.
An already activated Mise shell also supplies these tool versions. Commands
inside `mise run` tasks and after `mise-action` in CI already have this
environment and need no additional `mise exec --` wrapper.

`mise run check` runs the pinned Prek checks and deterministic tests. The
security scan requires a built image; a missing image is an error. A new app
version must receive an explicit security review: its approval cannot be
inherited from another version. Update PRs may be prepared before that review,
but release CI remains blocked until the assessment is complete.

Keep the app version, upstream versions and digests consistent in
[release.yaml](../../release.yaml). Every published wrapper revision needs a
new app version, changelog entry and reviewed security baseline. Do not reuse
an existing Git tag or any of the three GHCR version tags.

## 2. Merge and require CI for the release commit

Merge the reviewed PR, then wait for CI on `main`. The Release workflow checks
successful **Verify**, **Test build (amd64)** and **Test build (aarch64)** jobs
for exactly the tagged commit. A missing, failed, pending or newer failed CI
attempt blocks publication. Subsequent jobs check out that verified commit.
The current security approval must also be valid on the release date.

## 3. Create the approved release

Read the version from the metadata instead of copying an old example:

```bash
version="$(yq -r '.app.version' release.yaml)"
tag="v${version}"
commit="$(git rev-parse HEAD)"
mise run release:check -- --release-tag "$tag"
mise run release:ci -- --commit "$commit"
gh release create "$tag" \
  --repo ne1800/hass-portainer-ee \
  --target "$commit" \
  --title "Portainer BE app ${version}" \
  --notes-file release-notes.md
```

Prepare and review the release notes locally; do not add private operational
notes to the public release. Enable GitHub immutable releases for future Git
tag and release-asset protection. This setting does not make GHCR tags
immutable; the workflow separately refuses to overwrite version references.

## 4. Verify publication

Native images are built and signed first. Before creating the final app tag,
`mise run release:manifest` resolves both native images by digest, verifies
their signatures, architecture, app version, source and exact build commit,
then scans each image against the current security baseline. New or missing
findings block the final app manifest. A partial failure can leave native
image tags behind; use a new wrapper revision rather than overwriting them.

The final manifest includes the package description and source revision and is
signed by the release workflow. Moving tags such as `latest`, `sts` and `lts`
are not published. Cosign may store additional signature-artifact tags.

Confirm the GHCR package is public, then inspect it with anonymous credentials:

```bash
image="ghcr.io/ne1800/hass-portainer-ee:${version}"
registry_config="$(mktemp -d)"
manifest_digest="$(
  REGCTL_CONFIG="${registry_config}/regctl.json" \
    regctl image digest "$image"
)"
[[ "$manifest_digest" =~ ^sha256:[0-9a-f]{64}$ ]]
REGCTL_CONFIG="${registry_config}/regctl.json" \
  regctl manifest get "$image"
cosign verify \
  --certificate-identity \
  "https://github.com/ne1800/hass-portainer-ee/.github/workflows/release.yml@refs/tags/${tag}" \
  --certificate-oidc-issuer https://token.actions.githubusercontent.com \
  "${image%:*}@${manifest_digest}"
DOCKER_CONFIG="${registry_config}" \
  docker pull --platform linux/amd64 "${image%:*}@${manifest_digest}"
DOCKER_CONFIG="${registry_config}" \
  docker pull --platform linux/arm64 "${image%:*}@${manifest_digest}"
```

The runnable platforms must be `linux/amd64` and `linux/arm64`; the index can
also contain non-runnable provenance attestations. Check the labels
`io.hass.type=app`, `io.hass.version`, `io.hass.arch` and
`org.opencontainers.image.revision` on both platforms. Only successful
anonymous pulls prove that Home Assistant can download the image without
GitHub credentials.

## 5. Separate production acceptance

Production installation and migration require their own inventory, backups,
restore and acceptance checks. Follow the [operator guide](../../portaineree/DOCS.md)
and retain host-specific procedures privately. Neither Renovate nor the
Portainer updater merges PRs, creates releases or deploys to production.
