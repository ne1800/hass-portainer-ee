# Portainer BE STS

This Home Assistant app provides Portainer Business Edition from the verified
STS channel. An explicitly configured LTS security bridge may be used
temporarily when Portainer does not publish a suitable STS release for a fix.

## Before starting

- Portainer requires access to the local Docker API. The protection mode must
  therefore be disabled deliberately.
- Home Assistant Ingress is not supported. Access the app directly through the
  configured host ports.
- Port `8000` serves the Edge tunnel, `9000` serves the HTTP UI, and `9443`
  serves the HTTPS UI.
- Only one Portainer app may bind these ports at a time.
- The app initially starts manually. Enable automatic startup only after a
  successful restore and acceptance check.

Depending on your configuration, open the app directly at an address such as
`https://<HAOS-HOST>:9443`. The certificate and reachability must match your
network environment.

## Migrating an existing configuration

A Portainer backup contains Portainer users, license data, endpoints, and stack
configuration, but no container or volume data from managed Docker hosts. Back
up those workload data separately.

Use `Restore Portainer from backup` only during the first start of a fresh
instance with an empty `/data` directory. Never share the data directory of an
older app directly with a different Portainer version. Keep the old app and
verified backups available as a rollback path until the migration is accepted.

Fully migrate and verify the Portainer Server before updating an Edge Agent.
The server and agent should use the same Portainer version afterward.

The current `2.44.0` baseline is approved only for temporary private operation
through `2026-09-30`. A new high-severity finding or a published security bridge
requires another review before the next update.

See the [app operator guide](DOCS.md) for generally applicable instructions.
Document site-specific migrations outside this public fork.
