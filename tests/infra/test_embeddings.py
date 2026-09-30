import math

from server.config import Settings
from server.infra.embeddings import (
    EMBEDDING_DIMENSIONS,
    FakeEmbeddingClient,
    create_embedding_client,
)


def test_fake_embeddings_are_stable_normalized_and_fixed_size() -> None:
    """本地替身必须让索引和查询得到可复现且可比较的向量。"""
    client = FakeEmbeddingClient()
    first = client.embed("混合检索 vector search")
    second = client.embed("混合检索 vector search")

    assert first == second
    assert len(first) == EMBEDDING_DIMENSIONS
    assert math.isclose(sum(value * value for value in first), 1.0)


def test_fake_provider_assembles_fake_embedding_client() -> None:
    settings = Settings(_env_file=None, llm_provider="fake")
    assert isinstance(create_embedding_client(settings), FakeEmbeddingClient)
