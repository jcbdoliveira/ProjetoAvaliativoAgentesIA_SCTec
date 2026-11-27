from typing import Annotated, Optional

from langchain_core.messages import AnyMessage
from langgraph.graph.message import add_messages
from typing_extensions import TypedDict


class AgentState(TypedDict):
    # Histórico conversacional do LangGraph
    messages: Annotated[list[AnyMessage], add_messages]

    # Dados operacionais extraídos durante a execução
    empresa_id: Optional[int]
    empresa_nome: Optional[str]
    assinatura_id: Optional[int]
    plano: Optional[str]
    status_assinatura: Optional[str]
    saldo_atual: Optional[int]
    creditos_solicitados: Optional[int]

    # Controle de validação, desfecho e iterações
    violacao_regra: Optional[str]
    status_operacao: str
    iteracoes: int
