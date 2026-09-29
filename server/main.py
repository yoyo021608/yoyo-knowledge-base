from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from server.config import Settings, get_settings
from server.controller.health import router as health_router
from server.controller.reset_delivery import create_reset_delivery
from server.controller.users import router as users_router
from server.infra.resources import InfraResources
from server.users import UsersModule


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
    try:
        yield
    finally:
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
    return application


app = create_app()
