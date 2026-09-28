from datetime import timedelta

import pytest
from fakeredis import FakeRedis

from server.infra.cache import RedisCache
from server.infra.jobs import Job, JobNotClaimedError, RedisJobQueue


def test_cache_requires_positive_ttl() -> None:
    client = FakeRedis(decode_responses=True)
    cache = RedisCache(client)

    cache.set("answer", "cached", ttl=timedelta(seconds=10))
    assert cache.get("answer") == "cached"

    cache.delete("answer")
    assert cache.get("answer") is None


def test_cache_rejects_non_positive_ttl() -> None:
    client = FakeRedis(decode_responses=True)
    cache = RedisCache(client)

    try:
        cache.set("answer", "cached", ttl=timedelta(seconds=0))
    except ValueError as error:
        assert str(error) == "cache ttl must be positive"
    else:
        raise AssertionError("expected a ValueError")


def test_job_queue_claim_acknowledge_and_retry() -> None:
    client = FakeRedis(decode_responses=True)
    queue = RedisJobQueue(client, "test:jobs")
    original = Job.create("refresh-index", {"version_id": "v1"}, max_retries=1)

    assert queue.enqueue(original) == original.id
    claimed = queue.claim()
    assert claimed == original

    assert queue.retry_or_fail(claimed) is True
    retried = queue.claim()
    assert retried is not None
    assert retried.id == original.id
    assert retried.retry_count == 1

    queue.acknowledge(retried)
    assert client.llen("test:jobs:processing") == 0


def test_job_moves_to_failed_queue_after_retry_budget() -> None:
    client = FakeRedis(decode_responses=True)
    queue = RedisJobQueue(client, "test:jobs")
    job = Job.create("refresh-index", {}, max_retries=0)
    queue.enqueue(job)

    claimed = queue.claim()
    assert claimed is not None
    assert queue.retry_or_fail(claimed) is False
    assert client.llen("test:jobs:failed") == 1


def test_job_cannot_be_acknowledged_without_a_claim() -> None:
    client = FakeRedis(decode_responses=True)
    queue = RedisJobQueue(client, "test:jobs")
    job = Job.create("refresh-index", {})

    with pytest.raises(JobNotClaimedError):
        queue.acknowledge(job)
