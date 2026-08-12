from __future__ import annotations

from fastapi import APIRouter, HTTPException, Query, Request

from src.schemas.sales_forecast import ChannelListResponse, SalesForecastResponse
from src.services import sales_forecast_service

router = APIRouter(prefix="/api/sales-forecast", tags=["sales-forecast"])


@router.get("", response_model=SalesForecastResponse)
def get_sales_forecast(
    request: Request,
    channel: str | None = Query(default=None),
    horizon_days: int = Query(default=30, ge=1, le=90),
) -> SalesForecastResponse:
    state: sales_forecast_service.SalesForecastState = request.app.state.sales_forecast
    selected_channel = channel or sorted(state.channels.keys())[0]
    try:
        return sales_forecast_service.forecast(state, selected_channel, horizon_days)
    except KeyError as exc:
        raise HTTPException(status_code=404, detail=f"不明なチャネルです: {selected_channel}") from exc


@router.get("/channels", response_model=ChannelListResponse)
def list_channels(request: Request) -> ChannelListResponse:
    state: sales_forecast_service.SalesForecastState = request.app.state.sales_forecast
    return ChannelListResponse(
        source=state.source, model=sales_forecast_service.MODEL_NAME, channels=sorted(state.channels.keys())
    )
