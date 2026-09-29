import json
from dataclasses import asdict, dataclass, replace
from typing import cast
from uuid import uuid4

from redis import Redis


class JobNotClaimedError(RuntimeError):
    pass


@dataclass(frozen=True, slots=True)
class Job:
    id: str
    kind: str
    payload: dict[str, object]
    retry_count: int = 0
    max_retries: int = 3

    def __post_init__(self) -> None:
        if not self.kind.strip():
            raise ValueError("job kind cannot be empty")
        if self.retry_count < 0:
            raise ValueError("job retry_count cannot be negative")
        if self.max_retries < 0:
            raise ValueError("job max_retries cannot be negative")

    @classmethod
    def create(
        cls,
        kind: str,
        payload: dict[str, object],
        *,
        max_retries: int = 3,
    ) -> "Job":
        return cls(
            id=str(uuid4()),
            kind=kind,
            payload=payload,
            max_retries=max_retries,
        )


class RedisJobQueue:
    """A small reliable Redis queue; domain handlers provide idempotency."""

    def __init__(self, client: Redis, queue_name: str) -> None:
        if not queue_name.strip():
            raise ValueError("queue name cannot be empty")
        self._client = client
        self._queue_name = queue_name
        self._processing_name = f"{queue_name}:processing"
        self._failed_name = f"{queue_name}:failed"

    def enqueue(self, job: Job) -> str:
        self._client.lpush(self._queue_name, self._encode(job))
        return job.id

    def claim(self) -> Job | None:
        encoded = self._client.rpoplpush(
            self._queue_name,
            self._processing_name,
        )
        if encoded is None:
            return None
        if isinstance(encoded, bytes):
            encoded = encoded.decode("utf-8")
        return self._decode(encoded)

    def acknowledge(self, job: Job) -> None:
        self._remove_claimed(job)

    def retry_or_fail(self, job: Job) -> bool:
        self._remove_claimed(job)
        retried = replace(job, retry_count=job.retry_count + 1)
        encoded = self._encode(retried)
        if retried.retry_count > retried.max_retries:
            self._client.lpush(self._failed_name, encoded)
            return False
        self._client.lpush(self._queue_name, encoded)
        return True

    def _remove_claimed(self, job: Job) -> None:
        removed = self._client.lrem(self._processing_name, 1, self._encode(job))
        if removed != 1:
            raise JobNotClaimedError(f"job {job.id} is not claimed by this queue")

    @staticmethod
    def _encode(job: Job) -> str:
        return json.dumps(asdict(job), ensure_ascii=False, separators=(",", ":"))

    @staticmethod
    def _decode(value: str) -> Job:
        data = cast(dict[str, object], json.loads(value))
        payload = cast(dict[str, object], data["payload"])
        return Job(
            id=str(data["id"]),
            kind=str(data["kind"]),
            payload=payload,
            retry_count=int(cast(int, data["retry_count"])),
            max_retries=int(cast(int, data["max_retries"])),
        )
