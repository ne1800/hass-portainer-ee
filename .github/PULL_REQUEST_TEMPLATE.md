Describe the problem, resulting behavior, and relevant validation.

- Keep changes focused and document effects on permissions, ports, persistence or updates.
- Run `mise run lint`, `mise run test`, and `mise run release:check`.
- For image or release changes, build and run `mise run security:scan`.
- Review the complete diff for secrets, private infrastructure data and local planning files.
- A version update requires a separate security assessment before publication.
