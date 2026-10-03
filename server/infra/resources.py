from dataclasses import dataclass

from redis import Redis

from server.config import Settings
from server.infra.cache import RedisCache
from server.infra.chat import ChatClient, create_chat_client
from server.infra.database import Database
from server.infra.document_content import DefaultDocumentContentLoader
from server.infra.embeddings import EmbeddingClient, create_embedding_client
from server.infra.files import LocalFileStorage
from server.infra.jobs import RedisJobQueue


@dataclass(slots=True)
class InfraResources:
    database: Database
    redis: Redis
    cache: RedisCache
    jobs: RedisJobQueue
    files: LocalFileStorage
    embeddings: EmbeddingClient
    document_content: DefaultDocumentContentLoader
    chat: ChatClient

    @classmethod
    def create(cls, settings: Settings) -> "InfraResources":
        database = Database(
            settings.database_url,
            pool_size=settings.database_pool_size,
            max_overflow=settings.database_max_overflow,
            pool_timeout_seconds=settings.database_pool_timeout_seconds,
            connect_timeout_seconds=settings.database_connect_timeout_seconds,
        )
        redis_client = Redis.from_url(
            settings.redis_url,
            decode_responses=True,
            socket_timeout=settings.redis_socket_timeout_seconds,
        )
        return cls(
            database=database,
            redis=redis_client,
            cache=RedisCache(redis_client),
            jobs=RedisJobQueue(redis_client, settings.redis_job_queue_name),
            files=LocalFileStorage(settings.upload_dir),
            embeddings=create_embedding_client(settings),
            document_content=DefaultDocumentContentLoader(),
            chat=create_chat_client(settings),
        )

    def close(self) -> None:
        self.redis.close()
        self.database.close()
