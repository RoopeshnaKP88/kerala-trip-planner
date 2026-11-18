"""Live session storage in Redis (falls back to memory if Redis is off)."""
import redis

from .config import settings
from .models import TripState

_mem: dict[str, str] = {}
_client: redis.Redis | None = None
_tried = False


def _redis() -> redis.Redis | None:
    global _client, _tried
    if not _tried:
        _tried = True
        try:
            c = redis.Redis.from_url(settings.redis_url, decode_responses=True)
            c.ping()
            _client = c
        except redis.RedisError:
            print("[store] Redis not reachable, using in-memory sessions")
    return _client


def save(trip: TripState) -> None:
    data = trip.model_dump_json()
    r = _redis()
    if r:
        r.set(f"trip:{trip.session_id}", data, ex=86400)
    else:
        _mem[trip.session_id] = data


def load(session_id: str) -> TripState | None:
    r = _redis()
    data = r.get(f"trip:{session_id}") if r else _mem.get(session_id)
    return TripState.model_validate_json(data) if data else None