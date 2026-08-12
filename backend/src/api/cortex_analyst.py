from __future__ import annotations

from fastapi import APIRouter, HTTPException

from src.config import get_settings
from src.schemas.cortex_analyst import CortexAnalystRequest, CortexAnalystResponse

router = APIRouter(prefix="/api/cortex-analyst", tags=["cortex-analyst"])


def _unavailable_detail(execution_mode: str) -> dict:
    return {
        "message": "Cortex AnalystはEXECUTION_MODE=snowflake接続時のみ利用可能です。この機能にはデモ経路に相当するものが存在しません。",
        "execution_mode": execution_mode,
    }


@router.post("/ask", response_model=CortexAnalystResponse)
def ask(body: CortexAnalystRequest) -> CortexAnalystResponse:
    settings = get_settings()
    if settings.execution_mode != "snowflake":
        # 503, not 404 (this isn't a missing resource) and not 200+flag
        # (that would hide "no real answer" behind a status code that
        # normally means success) — 503 correctly says "this backing
        # service isn't configured," matching HTTP semantics and letting
        # the frontend distinguish this from a real error.
        raise HTTPException(status_code=503, detail=_unavailable_detail(settings.execution_mode))

    from src.snowflake.cortex_analyst.client import ask_cortex_analyst  # noqa: PLC0415

    result = ask_cortex_analyst(body.question, settings)
    return CortexAnalystResponse(question=body.question, generated_sql=result.get("sql"), answer=result.get("answer", ""))
