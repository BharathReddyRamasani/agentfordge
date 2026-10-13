"""JWT revocation list backing logout. Stores only SHA-256 hashes of revoked tokens
in Redis with TTL = remaining token lifetime (never raw tokens, never in Postgres)."""

import hashlib
import time

from app.core.security import decode_token_claims

KEY_PREFIX = "agentforge:revoked:"
MAX_TTL_S = 7 * 24 * 3600


def _key(token: str) -> str:
    return KEY_PREFIX + hashlib.sha256(token.encode("utf-8")).hexdigest()


def revoke_token(token: str) -> bool:
    claims = decode_token_claims(token)
    if claims is None:
        return False
    ttl = min(max(int(claims.get("exp", 0)) - int(time.time()), 60), MAX_TTL_S)
    try:
        from app.workers.queue import get_redis

        get_redis().set(_key(token), "1", ex=ttl)
        return True
    except Exception:
        return False


def is_revoked(token: str) -> bool:
    try:
        from app.workers.queue import get_redis

        return bool(get_redis().exists(_key(token)))
    except Exception:
        return False
