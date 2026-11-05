from functools import lru_cache
from uuid import UUID

import jwt
from jwt import PyJWKClient
from jwt.exceptions import PyJWKClientConnectionError, PyJWKClientError, PyJWTError

from .config import settings


class InvalidAccessToken(Exception):
    pass


class AuthServiceUnavailable(Exception):
    pass


@lru_cache(maxsize=1)
def _jwks_client(url: str) -> PyJWKClient:
    return PyJWKClient(f"{url.rstrip('/')}/auth/v1/.well-known/jwks.json")


def verify_access_token(token: str) -> str:
    project_url = settings.supabase_url.rstrip("/")
    if not project_url:
        raise AuthServiceUnavailable("Supabase authentication is not configured.")

    issuer = f"{project_url}/auth/v1"
    try:
        if settings.supabase_jwt_secret:
            claims = jwt.decode(
                token,
                settings.supabase_jwt_secret,
                algorithms=["HS256"],
                audience="authenticated",
                issuer=issuer,
            )
        else:
            signing_key = _jwks_client(project_url).get_signing_key_from_jwt(token)
            if signing_key.algorithm_name not in {"ES256", "RS256", "EdDSA"}:
                raise InvalidAccessToken("Unsupported signing algorithm.")
            claims = jwt.decode(
                token,
                signing_key.key,
                algorithms=[signing_key.algorithm_name],
                audience="authenticated",
                issuer=issuer,
            )
        return str(UUID(claims["sub"]))
    except PyJWKClientConnectionError as exc:
        raise AuthServiceUnavailable("Could not retrieve Supabase signing keys.") from exc
    except (PyJWKClientError, PyJWTError, KeyError, TypeError, ValueError) as exc:
        raise InvalidAccessToken("Invalid or expired access token.") from exc
