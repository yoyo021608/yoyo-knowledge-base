from datetime import timedelta
from typing import cast

from redis import Redis


class RedisCache:
    """Stores rebuildable string values with explicit expiry."""

    def __init__(self, client: Redis) -> None:
        self._client = client

    def get(self, key: str) -> str | None:
        return cast(str | None, self._client.get(key))

    def set(self, key: str, value: str, *, ttl: timedelta) -> None:
        if ttl.total_seconds() <= 0:
            raise ValueError("cache ttl must be positive")
        self._client.set(key, value, ex=ttl)

    def delete(self, key: str) -> None:
        self._client.delete(key)
