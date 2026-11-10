from datetime import datetime, timezone

from fastapi import APIRouter, status
from pydantic import BaseModel

from services.api.config import settings

router = APIRouter(tags=["Health"])


class HealthResponse(BaseModel):
    status: str
    service: str
    version: str
    environment: str
    timestamp: datetime


@router.get("/health", response_model=HealthResponse, status_code=status.HTTP_200_OK)
async def health_check():
    """Health check endpoint to verify API readiness and status."""
    return HealthResponse(
        status="healthy",
        service=settings.app_name,
        version="0.1.0",
        environment=settings.environment,
        timestamp=datetime.now(timezone.utc)
    )

