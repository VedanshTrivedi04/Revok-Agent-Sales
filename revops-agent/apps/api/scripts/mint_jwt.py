"""Mint a service JWT for local/staging API calls (what the Next.js proxy does in production).

Usage: uv run python scripts/mint_jwt.py [role=owner] [ttl_seconds=3600]
Uses API_JWT_SECRET/API_JWT_AUDIENCE from the environment and the Demo SaaS seed identities.
"""

import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import jwt  # noqa: E402

from app.config import get_settings  # noqa: E402
from app.mocks import data as D  # noqa: E402

role = sys.argv[1] if len(sys.argv) > 1 else "owner"
ttl = int(sys.argv[2]) if len(sys.argv) > 2 else 3600
s = get_settings()
now = int(time.time())
claims = {
    "sub": D.USER_IDS[role], "org_id": D.ORG_ID, "email": D.USERS[role][1],
    "aud": s.api_jwt_audience, "iat": now, "exp": now + ttl,
}  # fmt: skip
print(jwt.encode(claims, s.api_jwt_secret, algorithm="HS256"))
