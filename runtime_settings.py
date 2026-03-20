import os
import secrets

DEFAULT_ALLOWED_ORIGINS = (
    "http://localhost:3000",
    "http://127.0.0.1:3000",
    "null",
)

_AUTH_SECRET = os.getenv("PYTC_AUTH_SECRET") or secrets.token_urlsafe(32)


def get_allowed_origins() -> list[str]:
    raw_origins = os.getenv("PYTC_ALLOWED_ORIGINS", "").strip()
    if raw_origins:
        origins = [origin.strip() for origin in raw_origins.split(",")]
        filtered = [origin for origin in origins if origin]
        if filtered:
            return filtered

    return list(DEFAULT_ALLOWED_ORIGINS)


def get_auth_secret() -> str:
    return _AUTH_SECRET
