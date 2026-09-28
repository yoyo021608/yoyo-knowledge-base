from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from server.config import get_settings
from server.controller.health import router as health_router
from server.infra.resources import InfraResources


@asynccontextmanager
async def lifespan(application: FastAPI) -> AsyncIterator[None]:
    resources = InfraResources.create(get_settings())
    application.state.infra = resources
    try:
        yield
    finally:
        resources.close()


def create_app() -> FastAPI:
    settings = get_settings()
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
    application.include_router(health_router)
    return application


app = create_app()
