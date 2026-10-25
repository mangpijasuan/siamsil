# Security Policy

## Report a vulnerability privately

Do not disclose exploitable vulnerabilities, credentials, or private user information in a public issue.

When GitHub private vulnerability reporting is enabled, use **Security → Report a vulnerability** in this repository. Otherwise, ask a maintainer for a secure private communication channel without posting exploit details publicly. No guaranteed response deadline or monitored security email is asserted here.

Include the affected code revision, impact, and a minimal non-destructive reproduction using synthetic data.

## Areas that require particular care

- Authentication and OpenID Connect configuration
- User identities, roles, consent records, and audit events
- Language corpus provenance and data licensing
- Generated-entry review workflow and publication permissions
- Input validation, search endpoints, and exposed configuration

Never use real user data in bug reports or screenshots. Follow [data rights](docs/DATA_RIGHTS.md) and [identity documentation](docs/IDENTITY_AND_AUTHORIZATION.md).
