# Operator guide for the Portainer BE app

## Purpose and trust boundary

The app runs Portainer Business Edition on Home Assistant OS. Because
`docker_api: true` is enabled, Portainer can manage containers, networks,
volumes, and other host functions. The protection mode must be disabled for
this access. This is a deliberate administrative trust decision, not a normal
app permission.

Restrict access to a private network and administrative users. Public port
forwarding, untrusted Git sources, or arbitrary third-party images change the
verified risk model and block operation until a new assessment is complete.

## Network and user interface

Home Assistant Ingress is not used. All host mappings start disabled (`null`).
In the app network settings, explicitly assign an available host port to
`9443/tcp`. Enable `8000/tcp` only for an Edge tunnel and leave optional legacy
HTTP disabled unless it is required. These container ports are available:

| Port | Purpose |
|---:|---|
| `8000/tcp` | Portainer Edge tunnel |
| `9000/tcp` | Portainer web UI over HTTP |
| `9443/tcp` | Portainer web UI over HTTPS |

Before every start, verify that no other container occupies these host ports.
In particular, do not run old BE apps or third-party CE apps alongside the new
app on the same ports.

## Fresh installation, license and TLS

Add `https://github.com/ne1800/hass-portainer-ee` through the Home Assistant
app store's **Repositories** menu and install **Portainer BE STS**. Disable
protection mode deliberately, configure the ports and start manually. Visit
`https://<HAOS-HOST>:9443` using the selected host port.

For a fresh instance, read the setup token locally in the app's logs, create
an administrator and enter a valid BE license. Follow
[Portainer's initial setup](https://docs.portainer.io/start/install/server/setup).
When migrating an existing installation, use the restore sequence below.

Portainer initially generates a self-signed HTTPS certificate. Configure a
trusted certificate and its complete chain through the Portainer UI as
explained in [Portainer's TLS guide](https://docs.portainer.io/advanced/ssl).
Mounting Home Assistant's `/ssl` directory does not select a certificate
automatically; this wrapper does not inject certificate command-line options.
Never publish setup tokens, license data, private keys or unredacted logs.

The wrapper's GPL-3.0 license does not grant a Portainer Business Edition
license. Portainer BE has separate upstream terms.

## Persistence and backups

Portainer stores its database and configuration under `/data`. Each app
instance receives only its own data directory. Do not share or copy this
directory between the old and new apps.

A Portainer configuration backup contains users, teams, license information,
endpoints, and stack metadata, but it does not include container or volume data
from managed hosts. Workloads, bind mounts, and named volumes require separate
backups. Before every migration, also retain a complete and successfully
finished Home Assistant backup of the old app.

Restore only through `Restore Portainer from backup` in a fresh instance with an empty `/data`
directory. Verify the archive's file size, checksum, and restore usability
beforehand. Never write passwords or JWTs to command-line logs or this
repository.

## Startup and update sequence

1. Verify the release, manifest, signature, and security scan for the new app
   image.
2. Complete the live inventory and both backups.
3. Install the new app, disable protection mode, and configure the ports, but
   do not start it yet.
4. Stop only the currently active BE app normally and confirm exclusive port
   ownership.
5. Start the new app and restore the Portainer backup into the empty `/data`
   directory.
6. Verify the license, users, endpoints, stacks, persistence, TLS, and logs.
7. Only then update a remote Edge Agent to exactly the same version.

On any failure, roll back the server first. Do not delete the old app, backups,
or old images during the observation period.

## Updates and channels

`release.yaml` is the machine-readable source for the channel, Portainer
version, app version, and digests. `mise run update:check` selects only a newer
STS release or an explicitly configured LTS security bridge. Downgrades are
prohibited.

An automatically generated update PR is not an approval signal. The new build
must pass its own security baseline. Review, backups, the server-before-agent
sequence, and separate production approvals remain mandatory afterward.

## Further runbooks

- [Publish a release](https://github.com/ne1800/hass-portainer-ee/blob/main/docs/runbooks/release.md)
- [Security policy and private reporting](https://github.com/ne1800/hass-portainer-ee/blob/main/SECURITY.md)

Specific server, host, and agent migrations are outside the scope of this
public fork and require a separate site-specific operating procedure.
