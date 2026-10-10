from dataclasses import dataclass
from uuid import UUID

import jwt

from app.config import get_settings
from app.utils.errors import AppError

LEEWAY_SECONDS = 30
ALGORITHMS = ["HS256"]


@dataclass(frozen=True)
class Claims:
    user_id: UUID
    org_id: UUID
    email: str | None
    role_claim: str | None  # informational only: never trusted for authorization


def verify_service_jwt(token: str) -> Claims:
    s = get_settings()
    try:
        payload = jwt.decode(
            token,
            s.api_jwt_secret,
            algorithms=ALGORITHMS,
            audience=s.api_jwt_audience,
            leeway=LEEWAY_SECONDS,
            options={"require": ["sub", "org_id", "aud", "exp"]},
        )
        return Claims(
            user_id=UUID(payload["sub"]),
            org_id=UUID(payload["org_id"]),
            email=payload.get("email"),
            role_claim=payload.get("role"),
        )
    except jwt.ExpiredSignatureError as e:
        raise AppError("token_expired", "Session expired", 401) from e
    except (jwt.InvalidTokenError, ValueError, KeyError) as e:
        raise AppError("invalid_token", "Invalid authentication token", 401) from e
