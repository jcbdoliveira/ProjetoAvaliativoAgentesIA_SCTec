"""
API FastAPI do Agente de Customer Success B2B.

Endpoints:
  POST /agent/executar  → instrução em linguagem natural → JSON estruturado
  GET  /health
  GET  /                → interface web
"""

import os
from pathlib import Path

from dotenv import load_dotenv
from fastapi import FastAPI, HTTPException, Request
from fastapi.responses import HTMLResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from pydantic import BaseModel, Field

load_dotenv()

from agent.graph import run_agent

BASE_DIR = Path(__file__).resolve().parent.parent
TEMPLATES_DIR = BASE_DIR / "frontend" / "templates"
STATIC_DIR = BASE_DIR / "frontend" / "static"

app = FastAPI(
    title="Agente CS B2B — API",
    description=(
        "Agente de Inteligência Artificial para Customer Success. "
        "Interpreta solicitações em linguagem natural, consulta empresas/assinaturas "
        "e inclui créditos extras de API com validação de regras de negócio."
    ),
    version="1.0.0",
)

if STATIC_DIR.exists():
    app.mount("/static", StaticFiles(directory=str(STATIC_DIR)), name="static")

templates = Jinja2Templates(directory=str(TEMPLATES_DIR))


class ExecutarRequest(BaseModel):
    mensagem: str = Field(
        ...,
        min_length=3,
        max_length=2000,
        description="Solicitação em linguagem natural do analista de CS.",
        examples=[
            "Consulte a assinatura da empresa Logística Sul e adicione 1500 créditos extras"
        ],
    )


class ExecutarResponse(BaseModel):
    parecer: str
    mensagem: str
    dados_consultados: dict
    operacao_creditos: dict
    status_operacao: str | None = None
    error: str | None = None


@app.get("/health")
def health():
    return {
        "status": "ok",
        "agent": "CS B2B Agent",
        "saas_api": os.getenv("SAAS_API_BASE_URL", "http://localhost:8002"),
        "model": os.getenv("LLM_MODEL", "openai/gpt-oss-120b"),
        "provider": "groq",
    }


@app.post("/agent/executar", response_model=ExecutarResponse)
def executar_agente(payload: ExecutarRequest):
    if not os.getenv("GROQ_API_KEY"):
        raise HTTPException(
            status_code=500,
            detail="GROQ_API_KEY não configurada. Defina a variável no arquivo .env.",
        )

    try:
        result = run_agent(payload.mensagem)
        return ExecutarResponse(**result)
    except Exception as exc:
        raise HTTPException(
            status_code=500,
            detail=f"Erro interno na execução do agente: {str(exc)}",
        )


@app.get("/", response_class=HTMLResponse)
async def interface_web(request: Request):
    return templates.TemplateResponse(
        request=request,
        name="index.html",
        context={"title": "Agente CS B2B"},
    )


if __name__ == "__main__":
    import uvicorn

    port = int(os.getenv("AGENT_API_PORT", "8000"))
    uvicorn.run("api.main:app", host="0.0.0.0", port=port, reload=True)
