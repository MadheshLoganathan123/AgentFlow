from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from services.api.config import settings
from services.api.routers import health, profile


def create_app() -> FastAPI:
    """Application factory for AgentFlow Backend API."""
    app = FastAPI(
        title=settings.app_name,
        description=(
            "AgentFlow REST API - Multi-agent job-search copilot with human-in-the-loop "
            "approval gates, verifiable evidence grounding, and LangGraph workflow orchestration."
        ),
        version="0.1.0",
        debug=settings.debug
    )

    # CORS configuration
    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.cors_origins,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    # Register Routers
    app.include_router(health.router)
    app.include_router(profile.router)

    @app.get("/", tags=["Root"])
    async def root():
        return {
            "name": settings.app_name,
            "version": "0.1.0",
            "environment": settings.environment,
            "docs_url": "/docs",
            "health_url": "/health"
        }

    return app


app = create_app()

if __name__ == "__main__":
    import uvicorn
    uvicorn.run("services.api.main:app", host=settings.api_host, port=settings.api_port, reload=True)

