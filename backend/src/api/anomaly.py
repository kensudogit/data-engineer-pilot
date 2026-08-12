from __future__ import annotations

from fastapi import APIRouter, Query, Request

from src.schemas.anomaly import AnomalyResponse
from src.services import anomaly_service

router = APIRouter(prefix="/api/anomaly", tags=["anomaly"])


@router.get("", response_model=AnomalyResponse)
def get_anomalies(
    request: Request,
    window_days: int | None = Query(default=30, ge=1, le=730),
    limit: int = Query(default=100, ge=1, le=1000),
) -> AnomalyResponse:
    state: anomaly_service.AnomalyState = request.app.state.anomaly
    return anomaly_service.detect(state, window_days=window_days, limit=limit)
