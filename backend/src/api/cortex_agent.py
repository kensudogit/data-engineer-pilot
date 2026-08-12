from __future__ import annotations

from fastapi import APIRouter, HTTPException

from src.config import get_settings
from src.schemas.cortex_agent import CortexAgentRequest, CortexAgentResponse

router = APIRouter(prefix="/api/cortex-agent", tags=["cortex-agent"])


def _unavailable_detail(execution_mode: str) -> dict:
    return {
        "message": "Cortex AgentはEXECUTION_MODE=snowflake接続時のみ利用可能です。この機能にはデモ経路に相当するものが存在しません。",
        "execution_mode": execution_mode,
    }


@router.post("/ask", response_model=CortexAgentResponse)
def ask(body: CortexAgentRequest) -> CortexAgentResponse:
    settings = get_settings()
    if settings.execution_mode != "snowflake":
        raise HTTPException(status_code=503, detail=_unavailable_detail(settings.execution_mode))

    from src.snowflake.cortex_agent.client import ask_cortex_agent  # noqa: PLC0415

    result = ask_cortex_agent(body.question, settings)
    return CortexAgentResponse(question=body.question, answer=result.get("answer", ""), citations=result.get("citations", []))
