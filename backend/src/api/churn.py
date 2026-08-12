from __future__ import annotations

from fastapi import APIRouter, Query, Request

from src.schemas.churn import ChurnResponse
from src.services import churn_service

router = APIRouter(prefix="/api/churn", tags=["churn"])


@router.get("", response_model=ChurnResponse)
def get_churn(
    request: Request,
    limit: int = Query(default=50, ge=1, le=500),
    min_risk: float = Query(default=0.0, ge=0.0, le=1.0),
) -> ChurnResponse:
    state: churn_service.ChurnState = request.app.state.churn
    return churn_service.score(state, limit=limit, min_risk=min_risk)
