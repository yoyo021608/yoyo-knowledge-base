import logging
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from server.agent import AgentModule
from server.config import Settings, get_settings
from server.controller.agent import router as agent_router
from server.controller.agent.document_port import DocumentsSearchBridge
from server.controller.agent.recovery import recover_after_restart
from server.controller.agent.recovery_worker import AgentRecoveryWorker
from server.controller.documents import router as documents_router
from server.controller.health import router as health_router
from server.controller.sessions import router as sessions_router
from server.controller.users import router as users_router
from server.controller.users.reset_delivery import create_reset_delivery
from server.documents import DocumentsModule
from server.documents.worker import DocumentIndexWorker
from server.infra.resources import InfraResources
from server.sessions import SessionsModule
from server.users import UsersModule

_LOGGER = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(application: FastAPI) -> AsyncIterator[None]:
    settings: Settings = application.state.settings
    resources = InfraResources.create(settings)
    application.state.infra = resources
    application.state.users = UsersModule.create(
        resources.database,
        settings,
        create_reset_delivery(settings),
    )
    application.state.documents = DocumentsModule.create(
        resources.database,
        resources.files,
        resources.embeddings,
        resources.document_content,
    )
    application.state.sessions = SessionsModule.create(resources.database)
    application.state.agent = AgentModule.create(
        resources.database,
        settings,
        resources.chat,
        DocumentsSearchBridge(application.state.documents),
    )
    startup_recovered = False
    try:
        recover_after_restart(application.state.agent, application.state.sessions)
        startup_recovered = True
    except Exception:
        # 数据库暂不可用时由周期恢复任务重试，不阻止应用完成资源装配。
        _LOGGER.exception("agent.recovery.startup_failed")
    index_worker = DocumentIndexWorker(application.state.documents.indexer)
    agent_recovery_worker = AgentRecoveryWorker(
        application.state.agent,
        application.state.sessions,
        settings.agent_recovery_interval_seconds,
        startup_recovered=startup_recovered,
    )
    index_worker.start()
    agent_recovery_worker.start()
    try:
        yield
    finally:
        await index_worker.close()
        await agent_recovery_worker.close()
        resources.close()


def create_app(settings_override: Settings | None = None) -> FastAPI:
    settings = settings_override or get_settings()
    application = FastAPI(
        title="yoyo-knowledge-base",
        version="0.1.0",
        lifespan=lifespan,
    )
    application.add_middleware(
        CORSMiddleware,
        allow_origins=settings.cors_origin_list,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )
    application.state.settings = settings
    application.include_router(health_router)
    application.include_router(users_router)
    application.include_router(documents_router)
    application.include_router(sessions_router)
    application.include_router(agent_router)
    return application


app = create_app()
