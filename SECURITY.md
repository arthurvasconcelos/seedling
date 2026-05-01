# Security Policy

## Supported Versions

Only the latest released minor version receives security fixes.

| Version | Supported |
|---------|-----------|
| 0.2.x   | ✓ current |
| 0.1.x   | ✗         |

Once 1.0 ships this table will follow semver: the latest patch of each
supported minor line will receive fixes.

## Reporting a Vulnerability

**Please do not report security vulnerabilities through public GitHub issues.**

If you discover a vulnerability, report it privately in one of two ways:

**GitHub private vulnerability reporting** — use the
[Report a vulnerability](../../security/advisories/new) button on the Security
tab of this repository. This keeps the report private until a fix is released.

Include as much of the following as possible:

- Type of issue (e.g. SQL injection, path traversal, unsafe deserialization)
- Full paths of the affected source file(s)
- The git commit or version where the issue was introduced
- Any special configuration required to reproduce
- Step-by-step instructions to reproduce
- Proof-of-concept or exploit code (if available)
- Impact and how an attacker might exploit it

## Response

This project is maintained on a best-effort basis. There are no guaranteed
response times. Reports will be reviewed and addressed as time permits.

We aim to coordinate disclosure with the reporter before making any fix public.
Reporters who wish to be credited will be acknowledged in the release notes.
