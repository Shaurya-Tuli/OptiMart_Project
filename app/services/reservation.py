"""Reservation locking service using Redis TTL keys.

The Redis key `claim:lock:{batch_id}` acts as the single source of truth for
whether a batch is currently reserved. This prevents double-claiming under
high-concurrency conditions when many users receive the same flash-sale alert.
"""
import os
import json
from datetime import datetime, timedelta, timezone
from typing import Optional, Dict, Any

import redis

REDIS_URL = os.environ.get("REDIS_URL", "redis://redis:6379/0")
DEFAULT_TTL_SECONDS = int(os.environ.get("RESERVATION_TTL_SECONDS", "180"))  # 3 minutes


def _get_redis() -> redis.Redis:
    return redis.from_url(REDIS_URL, decode_responses=True)


def acquire_reservation_lock(batch_id: int, claim_id: int, ttl_seconds: int = DEFAULT_TTL_SECONDS) -> bool:
    """Attempts to set a Redis TTL lock for `batch_id`.

    Uses SET NX (only set if not exists) to ensure atomicity under concurrency.
    Returns True if lock acquired, False if batch is already reserved by another claim.
    """
    r = _get_redis()
    key = f"claim:lock:{batch_id}"
    value = json.dumps({"claim_id": claim_id, "locked_at": datetime.now(timezone.utc).isoformat()})
    # SET key value EX ttl NX — atomic; only sets if key doesn't already exist
    result = r.set(key, value, ex=ttl_seconds, nx=True)
    return result is True


def release_reservation_lock(batch_id: int) -> bool:
    """Releases the Redis TTL lock for `batch_id` (e.g., on payment success or expiry rollback)."""
    r = _get_redis()
    key = f"claim:lock:{batch_id}"
    deleted = r.delete(key)
    return deleted > 0


def get_reservation_lock_info(batch_id: int) -> Optional[Dict[str, Any]]:
    """Returns lock metadata dict if the batch is currently locked, None otherwise."""
    r = _get_redis()
    key = f"claim:lock:{batch_id}"
    value = r.get(key)
    if value:
        try:
            data = json.loads(value)
            data["ttl_remaining_seconds"] = r.ttl(key)
            return data
        except Exception:
            return {"raw": value, "ttl_remaining_seconds": r.ttl(key)}
    return None


def is_batch_reserved(batch_id: int) -> bool:
    """Quick check: returns True if the batch has an active TTL reservation lock in Redis."""
    r = _get_redis()
    return r.exists(f"claim:lock:{batch_id}") > 0


def reservation_expiry_timestamp(ttl_seconds: int = DEFAULT_TTL_SECONDS) -> datetime:
    """Returns the UTC datetime when the current reservation will expire."""
    return datetime.now(timezone.utc) + timedelta(seconds=ttl_seconds)
