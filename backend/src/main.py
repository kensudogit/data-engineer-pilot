from __future__ import annotations

from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import HTMLResponse

from src.api.anomaly import router as anomaly_router
from src.api.churn import router as churn_router
from src.api.demand_forecast import router as demand_forecast_router
from src.api.overview import router as overview_router
from src.api.sales_forecast import router as sales_forecast_router
from src.api.segmentation import router as segmentation_router
from src.config import get_settings
from src.data.synth import generate_dataset
from src.services import (
    anomaly_service,
    churn_service,
    demand_forecast_service,
    overview_service,
    sales_forecast_service,
    segmentation_service,
)


@asynccontextmanager
async def lifespan(app: FastAPI):
    settings = get_settings()

    # Fail loudly at startup rather than silently falling back to demo mode
    # — see config.py's execution_mode docstring and bigquery/client.py /
    # snowflake/client.py.
    if settings.execution_mode == "bigquery":
        from src.bigquery.client import get_client  # noqa: PLC0415

        get_client()
    elif settings.execution_mode == "snowflake":
        from src.snowflake.client import get_session  # noqa: PLC0415

        get_session()

    # Generated once, held for the process lifetime — every service trains
    # against this same fixed dataset instead of regenerating random data
    # (and refitting its model) per request.
    dataset = generate_dataset(seed=settings.synth_seed)
    app.state.dataset = dataset

    app.state.sales_forecast = sales_forecast_service.prepare(dataset)
    app.state.churn = churn_service.prepare(dataset)
    app.state.segmentation = segmentation_service.prepare(dataset)
    app.state.anomaly = anomaly_service.prepare(dataset)
    app.state.demand_forecast = demand_forecast_service.prepare(dataset)
    app.state.overview = overview_service.prepare(
        dataset,
        churn_metrics=app.state.churn.metrics,
        segmentation_metrics=app.state.segmentation.metrics,
        anomaly_metrics=app.state.anomaly.metrics,
    )

    yield


app = FastAPI(
    title="Data Engineer Pilot",
    description="BigQuery ML想定の5機能（売上予測・解約予測・顧客分類・異常検知・需要予測）のパイロット実装",
    version="0.1.0",
    lifespan=lifespan,
)

settings = get_settings()
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origin_list or ["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(overview_router)
app.include_router(sales_forecast_router)
app.include_router(churn_router)
app.include_router(segmentation_router)
app.include_router(anomaly_router)
app.include_router(demand_forecast_router)


@app.get("/", response_class=HTMLResponse)
def root():
    """Browser-friendly landing (avoids bare {"detail":"Not Found"} on /)."""
    return f"""<!DOCTYPE html>
<html lang="ja">
<head>
  <meta charset="utf-8" />
  <meta name="viewport" content="width=device-width, initial-scale=1" />
  <title>Data Engineer Pilot API</title>
  <style>
    body {{ font-family: "IBM Plex Sans", system-ui, sans-serif; margin: 0;
      background: linear-gradient(160deg,#0f172a,#1e293b); color: #e2e8f0;
      min-height: 100vh; display: grid; place-items: center; }}
    main {{ width: min(560px, calc(100% - 2rem)); }}
    h1 {{ font-family: Georgia, serif; font-weight: 560; margin: 0 0 .5rem; }}
    h1 span {{ color: #38bdf8; }}
    p {{ color: #94a3b8; line-height: 1.5; }}
    a {{ color: #38bdf8; }}
    ul {{ padding-left: 1.1rem; line-height: 1.8; }}
  </style>
</head>
<body>
  <main>
    <h1>Data Engineer <span>Pilot</span> API</h1>
    <p>バックエンドは稼働中です（実行モード: {get_settings().execution_mode}）。UI または API ドキュメントへ進んでください。</p>
    <ul>
      <li><a href="http://localhost:3030">フロントエンド UI</a> — http://localhost:3030</li>
      <li><a href="/docs">Swagger API Docs</a></li>
      <li><a href="/health">Health check</a></li>
      <li><a href="/api/overview">Overview JSON</a></li>
    </ul>
  </main>
</body>
</html>"""


@app.get("/health")
def health():
    settings = get_settings()
    return {"status": "ok", "app": "data-engineer-pilot", "execution_mode": settings.execution_mode}
