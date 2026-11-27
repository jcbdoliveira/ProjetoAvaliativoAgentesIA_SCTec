import os

import httpx
from langchain_core.tools import tool
from pydantic import BaseModel, Field

SAAS_API_URL = os.getenv("SAAS_API_BASE_URL", "http://localhost:8002")
LIMITE_MAXIMO_CREDITOS = 3000


def _format_http_error(exc: Exception) -> str:
    if isinstance(exc, httpx.HTTPStatusError):
        status = exc.response.status_code
        detail = exc.response.text
        if status == 404:
            return f"Erro HTTP 404 (Não Encontrado): recurso inexistente na API SaaS. Detalhe: {detail}"
        if status == 422:
            return f"Erro HTTP 422 (Dados Inválidos): parâmetros rejeitados pelo contrato da API. Detalhe: {detail}"
        return f"Erro HTTP {status} na API SaaS: {detail}"
    if isinstance(exc, httpx.TimeoutException):
        return "Erro de Timeout: a API SaaS excedeu o tempo limite de resposta (15s)."
    if isinstance(exc, httpx.ConnectError):
        return f"Erro de conexão com a API SaaS em {SAAS_API_URL}. Verifique se o serviço está no ar."
    return f"Erro de conexão com a API SaaS: {str(exc)}"


class SearchInput(BaseModel):
    nome: str = Field(..., min_length=2, description="Nome fantasia da empresa.")


@tool("search", args_schema=SearchInput)
def search(nome: str) -> str:
    """Busca empresas pelo nome fantasia. Retorna empresa_id. Use sempre antes de lookup."""
    try:
        with httpx.Client(base_url=SAAS_API_URL, timeout=15.0) as client:
            response = client.get("/empresas", params={"nome": nome.strip()})
            response.raise_for_status()
            empresas = response.json()
            if not empresas:
                return f"RESULTADO_VAZIO: Nenhuma empresa encontrada para '{nome}'."
            if len(empresas) > 1:
                lista = "; ".join(
                    f"ID {e['id']}: {e['nome_fantasia']} (CNPJ: {e.get('cnpj', 'N/A')})"
                    for e in empresas
                )
                return (
                    f"AMBIGUIDADE: Foram encontradas {len(empresas)} empresas "
                    f"com nome semelhante a '{nome}': {lista}. "
                    "Peça ao analista para confirmar qual empresa."
                )
            return f"EMPRESAS_ENCONTRADAS: {empresas}"
    except Exception as exc:
        return _format_http_error(exc)


class LookupInput(BaseModel):
    empresa_id: int = Field(..., gt=0, description="ID da empresa.")


@tool("lookup", args_schema=LookupInput)
def lookup(empresa_id: int) -> str:
    """Consulta assinatura da empresa. Retorna assinatura_id, plano, status e saldo."""
    try:
        with httpx.Client(base_url=SAAS_API_URL, timeout=15.0) as client:
            response = client.get(f"/assinaturas/{empresa_id}")
            response.raise_for_status()
            return f"ASSINATURAS_ENCONTRADAS: {response.json()}"
    except Exception as exc:
        return _format_http_error(exc)


class CreditInput(BaseModel):
    assinatura_id: int = Field(..., gt=0, description="ID da assinatura.")
    quantidade: int = Field(
        ...,
        gt=0,
        le=LIMITE_MAXIMO_CREDITOS,
        description=f"Créditos a incluir (1 a {LIMITE_MAXIMO_CREDITOS}).",
    )
    motivo: str = Field(
        default="Bonificação solicitada via CrediSentinela (CS B2B)",
        min_length=5,
        description="Motivo. Use o padrão se o analista não informar.",
    )


@tool("credit", args_schema=CreditInput)
def credit(
    assinatura_id: int,
    quantidade: int,
    motivo: str = "Bonificação solicitada via CrediSentinela (CS B2B)",
) -> str:
    """Inclui créditos na assinatura ativa. Máximo 3000. Não peça motivo ao usuário."""
    if quantidade <= 0:
        return "VALIDACAO_RECUSADA: A quantidade deve ser maior que zero."
    if quantidade > LIMITE_MAXIMO_CREDITOS:
        return (
            f"VALIDACAO_RECUSADA: quantidade {quantidade} excede o teto de "
            f"{LIMITE_MAXIMO_CREDITOS} créditos."
        )
    try:
        with httpx.Client(base_url=SAAS_API_URL, timeout=15.0) as client:
            response = client.post(
                f"/assinaturas/{assinatura_id}/creditos",
                json={"quantidade": quantidade, "motivo": motivo.strip()},
            )
            response.raise_for_status()
            return f"CREDITOS_INCLUIDOS_SUCESSO: {response.json()}"
    except Exception as exc:
        return _format_http_error(exc)


TOOLS = [search, lookup, credit]
