from __future__ import annotations

from datetime import datetime, timezone
from functools import lru_cache
from typing import Any

try:
    import jwt
    from jwt.exceptions import PyJWKClientError, PyJWTError
except ModuleNotFoundError:  # Allows configuration validation before dependencies are installed.
    jwt = None  # type: ignore[assignment]
    PyJWKClientError = PyJWTError = Exception  # type: ignore[misc,assignment]

from identity.schemas import OIDCClaims
from settings import Settings, get_settings


class AuthenticationError(Exception):
    pass


class IdentityNotConfiguredError(Exception):
    pass


class OIDCVerifier:
    def __init__(self, settings: Settings) -> None:
        if not settings.oidc_enabled:
            raise IdentityNotConfiguredError("OIDC authentication is not configured")
        if jwt is None:
            raise RuntimeError("PyJWT is required when OIDC authentication is enabled")

        self.settings = settings
        self._jwk_client = jwt.PyJWKClient(
            settings.oidc_jwks_url,
            cache_keys=True,
            lifespan=settings.oidc_jwks_cache_seconds,
            timeout=settings.oidc_http_timeout_seconds,
        )

    def verify(self, token: str) -> OIDCClaims:
        try:
            signing_key = self._jwk_client.get_signing_key_from_jwt(token)
            payload: dict[str, Any] = jwt.decode(
                token,
                signing_key.key,
                algorithms=["RS256", "ES256"],
                audience=self.settings.oidc_audience,
                issuer=self.settings.oidc_issuer,
                leeway=self.settings.oidc_clock_skew_seconds,
                options={"require": ["aud", "exp", "iat", "iss", "sub"]},
            )
        except (PyJWTError, PyJWKClientError) as exc:
            raise AuthenticationError("The access token is invalid or expired") from exc

        email = payload.get("email") if payload.get("email_verified") is True else None
        locale = str(payload.get("locale") or "en").lower()
        if locale not in {"en", "zom", "my"}:
            locale = "en"

        return OIDCClaims(
            issuer=str(payload["iss"]),
            subject=str(payload["sub"]),
            expires_at=datetime.fromtimestamp(int(payload["exp"]), tz=timezone.utc),
            token_id=str(payload["jti"]) if payload.get("jti") else None,
            email=str(email) if email else None,
            display_name=str(payload["name"]) if payload.get("name") else None,
            locale=locale,
        )


@lru_cache(maxsize=1)
def get_oidc_verifier() -> OIDCVerifier:
    return OIDCVerifier(get_settings())
