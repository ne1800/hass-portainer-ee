# Portainer BE for Home Assistant OS

Portainer Business Edition for `amd64` and `aarch64`, following STS with
explicitly reviewed LTS security bridges. The current versions and channel are
listed in [release.yaml](../release.yaml).

## Install and start

Add `https://github.com/ne1800/hass-portainer-ee` in the Home Assistant app
store's **Repositories** menu, then install **Portainer BE STS**.

- Disable protection mode deliberately: administrative access to the local
  Docker API is required.
- Home Assistant Ingress is not supported. All host port mappings start
  disabled. Assign an available host port to `9443/tcp` for the HTTPS UI.
- Enable `8000/tcp` only for the Edge tunnel. `9000/tcp` is optional legacy HTTP.
- Stop any older Portainer app that occupies the selected ports before starting.
- Start manually, then open `https://<HAOS-HOST>:9443`, substituting your host
  and configured HTTPS port. Configure a certificate trusted by your clients.
- For a new installation, read the setup token locally in the app's logs,
  create the first administrator, and provide a valid Portainer BE license.
  Never share those values or unredacted logs.

Enable automatic startup only after the installation or migration has passed
its acceptance checks. This app must stay on a private administrative network.

## Migrate and back up

A Portainer backup contains users, license data, endpoints and stack metadata,
but no container or volume data from managed hosts. Back up workload data
separately and retain a completed Home Assistant backup of the old app.

Use **Restore Portainer from backup** only during the first start of a fresh
instance with an empty `/data` directory. Do not share the old app's data
directory with a different instance or Portainer version. Keep the old app and
verified backups available until the migration is accepted.

Migrate and verify the Portainer Server before updating an Edge Agent. Align
server and agent versions afterward.

Temporary HIGH findings and their expiry are documented in
[accepted risks](../security/accepted-risks.yaml). A new build requires a new
assessment; an expired or changed baseline blocks publication.

See the [operator guide](DOCS.md) and [security policy](../SECURITY.md).
