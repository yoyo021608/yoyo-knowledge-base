from logging.config import fileConfig

from alembic import context
from sqlalchemy import engine_from_config, pool
from sqlalchemy.dialects.postgresql.base import ischema_names

from server.agent import models as agent_models  # noqa: F401
from server.config import get_settings
from server.documents import models as document_models  # noqa: F401
from server.infra.database import Base
from server.sessions import models as session_models  # noqa: F401
from server.users import models as user_models  # noqa: F401

# PostgreSQL 反射需要认识 pgvector，才能正确比较 embedding 列且不产生 NullType 警告。
ischema_names.setdefault("vector", document_models.VectorType)

config = context.config
if config.config_file_name is not None:
    fileConfig(config.config_file_name)

config.set_main_option("sqlalchemy.url", get_settings().database_url.replace("%", "%%"))
target_metadata = Base.metadata
_MIGRATION_MANAGED_INDEXES = {
    "ix_document_chunks_embedding",
    "ix_document_chunks_full_text",
}


def include_object(
    object_value: object,
    name: str | None,
    type_: str,
    reflected: bool,
    compare_to: object | None,
) -> bool:
    """保留只存在于 PostgreSQL 的表达式/向量索引，不让自动检查建议删除。"""
    del object_value
    if (
        type_ == "index"
        and reflected
        and compare_to is None
        and name in _MIGRATION_MANAGED_INDEXES
    ):
        return False
    return True


def compare_type(
    migration_context: object,
    inspected_column: object,
    metadata_column: object,
    inspected_type: object,
    metadata_type: object,
) -> bool | None:
    """SQLite 会把 vector(256) 反射为 NUMERIC；该差异不代表结构漂移。"""
    del inspected_column, inspected_type
    dialect = getattr(migration_context, "dialect", None)
    column_name = getattr(metadata_column, "name", None)
    if (
        getattr(dialect, "name", None) == "sqlite"
        and column_name == "embedding"
        and metadata_type.__class__.__name__ == "VectorType"
    ):
        return False
    return None


def run_migrations_offline() -> None:
    context.configure(
        url=config.get_main_option("sqlalchemy.url"),
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
        compare_type=compare_type,
        include_object=include_object,
    )
    with context.begin_transaction():
        context.run_migrations()


def run_migrations_online() -> None:
    connectable = engine_from_config(
        config.get_section(config.config_ini_section, {}),
        prefix="sqlalchemy.",
        poolclass=pool.NullPool,
    )
    with connectable.connect() as connection:
        context.configure(
            connection=connection,
            target_metadata=target_metadata,
            compare_type=compare_type,
            include_object=include_object,
        )
        with context.begin_transaction():
            context.run_migrations()


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
