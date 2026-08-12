from __future__ import annotations

from fastapi import APIRouter, HTTPException, Query, Request

from src.schemas.demand_forecast import DemandForecastResponse, ProductListResponse
from src.services import demand_forecast_service

router = APIRouter(prefix="/api/demand-forecast", tags=["demand-forecast"])


@router.get("", response_model=DemandForecastResponse)
def get_demand_forecast(
    request: Request,
    product_id: str | None = Query(default=None),
    horizon_days: int = Query(default=14, ge=1, le=60),
) -> DemandForecastResponse:
    state: demand_forecast_service.DemandForecastState = request.app.state.demand_forecast
    selected = product_id or sorted(state.products.keys())[0]
    try:
        return demand_forecast_service.forecast(state, selected, horizon_days)
    except KeyError as exc:
        raise HTTPException(status_code=404, detail=f"不明な商品IDです: {selected}") from exc


@router.get("/products", response_model=ProductListResponse)
def list_products(request: Request) -> ProductListResponse:
    state: demand_forecast_service.DemandForecastState = request.app.state.demand_forecast
    products = demand_forecast_service.list_products(state)
    return ProductListResponse(source="demo", model=demand_forecast_service.MODEL_NAME, products=products)
