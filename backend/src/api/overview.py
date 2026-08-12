from __future__ import annotations

from fastapi import APIRouter, Request

from src.schemas.overview import OverviewResponse

router = APIRouter(prefix="/api/overview", tags=["overview"])


@router.get("", response_model=OverviewResponse)
def get_overview(request: Request) -> OverviewResponse:
    return request.app.state.overview.response
