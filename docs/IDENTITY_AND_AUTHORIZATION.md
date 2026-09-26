# Identity and authorization

Siamsil uses OpenID Connect (OIDC) for authentication and PostgreSQL for
authorization. The identity provider proves who a person is; Siamsil's own
`user_roles` table decides what that person may do.

## Trust boundary

- Access tokens must be signed with RS256 or ES256.
- Issuer, audience, signature, expiry, issued-at time, and required claims are
  validated against the configured JWKS endpoint.
- Provider role claims are ignored. Roles are loaded from PostgreSQL.
- Raw access tokens and raw token IDs are never stored. Session tracking uses a
  SHA-256 digest scoped by issuer.
- New authenticated users receive the `learner` role.
- Disabled users and revoked tracked sessions are denied.
- User provisioning and administrator role grants emit append-only audit events.

## Provider configuration

Configure a mature OIDC provider, then set:

```dotenv
SIAMSIL_OIDC_ENABLED=true
SIAMSIL_OIDC_ISSUER=https://identity.example.com/
SIAMSIL_OIDC_AUDIENCE=https://api.siamsil.com
SIAMSIL_OIDC_JWKS_URL=https://identity.example.com/.well-known/jwks.json
SIAMSIL_BOOTSTRAP_ADMIN_SUBJECTS=["provider-subject-id"]
```

`SIAMSIL_BOOTSTRAP_ADMIN_SUBJECTS` is a JSON list of exact OIDC `sub` values.
Keep it empty after the initial administrators have signed in and been
provisioned. Provider selection and production credentials remain deployment
decisions; no provider secret belongs in the repository.

## Versioned endpoints

```text
GET  /api/v1/identity/me
POST /api/v1/identity/users/{user_id}/roles/{role}
```

The role-assignment endpoint requires the internal `administrator` role.
Authenticated identity endpoints deliberately have no legacy `/api` aliases.
