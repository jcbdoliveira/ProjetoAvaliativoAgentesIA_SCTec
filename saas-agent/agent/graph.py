import ast
import os
from typing import Literal

from dotenv import load_dotenv
from langchain_core.messages import AIMessage, HumanMessage, SystemMessage, ToolMessage
from langchain_groq import ChatGroq
from langgraph.graph import END, START, StateGraph
from langgraph.prebuilt import ToolNode

load_dotenv()  # carrega .env antes de ler variáveis / instanciar ChatGroq

from agent.prompts import SYSTEM_PROMPT
from agent.state import AgentState
from agent.tools import LIMITE_MAXIMO_CREDITOS, TOOLS

MAX_ITERATIONS = int(os.getenv("AGENT_MAX_ITERATIONS") or os.getenv("RECURSION_LIMIT") or "10")


def _get_llm():
    model_name = (
        os.getenv("LLM_MODEL")
        or os.getenv("GROQ_MODEL")
        or "openai/gpt-oss-120b"
    )
    api_key = os.getenv("GROQ_API_KEY")
    if not api_key:
        raise RuntimeError(
            "GROQ_API_KEY não definida. Coloque no arquivo .env na raiz do projeto "
            "ou exporte a variável de ambiente antes de executar."
        )
    llm = ChatGroq(model=model_name, temperature=0, api_key=api_key)
    return llm.bind_tools(TOOLS)


def no_raciocinio(state: AgentState) -> dict:
    """Nó de raciocínio e planejamento ReAct com controle explícito de iterações."""
    iteracao_atual = state.get("iteracoes", 0) + 1
    if iteracao_atual > MAX_ITERATIONS:
        return {
            "iteracoes": iteracao_atual,
            "status_operacao": "LIMITE_ITERACOES_EXCEDIDO",
            "messages": [
                AIMessage(
                    content=(
                        f"Execução encerrada por segurança após atingir o limite máximo de {MAX_ITERATIONS} iterações. "
                        "Verifique a disponibilidade da API SaaS ou reformule a solicitação."
                    )
                )
            ],
        }

    llm = _get_llm()
    messages = [SystemMessage(content=SYSTEM_PROMPT)] + list(state["messages"])
    response = llm.invoke(messages)
    return {"messages": [response], "iteracoes": iteracao_atual}


def no_validar_regras(state: AgentState) -> dict:
    """
    Nó intermediário de validação:
    1. Sincroniza os dados estruturados retornados pelas tools anteriores no State.
    2. Bloqueia qualquer tentativa de chamada a `credit` se a assinatura não estiver ATIVA
       ou se os créditos ultrapassarem 3000 / forem inválidos.
    """
    updates: dict = {"violacao_regra": None}

    # 1. Extrai dados operacionais das observações (ToolMessages) já executadas
    for msg in state["messages"]:
        if not isinstance(msg, ToolMessage):
            continue
        text = str(msg.content)
        if text.startswith("EMPRESAS_ENCONTRADAS:"):
            try:
                lista = ast.literal_eval(text.split(":", 1)[1].strip())
                if len(lista) == 1:
                    updates["empresa_id"] = lista[0]["id"]
                    updates["empresa_nome"] = lista[0].get("nome_fantasia")
            except Exception:
                pass
        elif text.startswith("ASSINATURAS_ENCONTRADAS:"):
            try:
                assinaturas = ast.literal_eval(text.split(":", 1)[1].strip())
                if assinaturas:
                    a = assinaturas[0] if isinstance(assinaturas, list) else assinaturas
                    updates["assinatura_id"] = a["id"]
                    updates["plano"] = a.get("plano")
                    updates["status_assinatura"] = a.get("status")
                    updates["saldo_atual"] = a.get("saldo_creditos_api")
            except Exception:
                pass
        elif text.startswith("CREDITOS_INCLUIDOS_SUCESSO:"):
            try:
                a = ast.literal_eval(text.split(":", 1)[1].strip())
                updates["saldo_atual"] = a.get("saldo_creditos_api")
                updates["status_operacao"] = "CREDITOS_INCLUIDOS"
            except Exception:
                pass

    status_assinatura_atual = updates.get(
        "status_assinatura", state.get("status_assinatura")
    )

    # 2. Valida argumentos da chamada de ferramenta solicitada pelo LLM
    last_message = state["messages"][-1]
    if isinstance(last_message, AIMessage) and last_message.tool_calls:
        bloqueios: list[ToolMessage] = []
        motivo_bloqueio = None

        for tc in last_message.tool_calls:
            if tc["name"] == "credit":
                args = tc["args"]
                qtd = int(args.get("quantidade", 0))
                updates["creditos_solicitados"] = qtd

                if qtd <= 0 or qtd > LIMITE_MAXIMO_CREDITOS:
                    motivo_bloqueio = (
                        f"Quantidade solicitada ({qtd}) fora da faixa permitida "
                        f"(1 a {LIMITE_MAXIMO_CREDITOS} créditos)."
                    )
                elif status_assinatura_atual and str(status_assinatura_atual).upper() != "ATIVA":
                    motivo_bloqueio = (
                        f"A assinatura encontra-se com status '{status_assinatura_atual}'. "
                        "Apenas assinaturas ATIVAS podem receber créditos."
                    )

                if motivo_bloqueio:
                    bloqueios.append(
                        ToolMessage(
                            tool_call_id=tc["id"],
                            name=tc["name"],
                            content=(
                                f"BLOQUEIO_REGRA_NEGOCIO: {motivo_bloqueio} "
                                "Não prossiga com a inclusão."
                            ),
                        )
                    )

        if bloqueios:
            updates["violacao_regra"] = motivo_bloqueio
            updates["status_operacao"] = "RECUSADO_REGRA_NEGOCIO"
            updates["messages"] = bloqueios

    return updates


no_executar_ferramentas = ToolNode(TOOLS)


def no_resposta_final(state: AgentState) -> dict:
    """Consolida o status final da execução antes do encerramento (END)."""
    updates: dict = {}
    status_atual = state.get("status_operacao", "CONCLUIDO")

    # Reprocessa ToolMessages para capturar inclusão bem-sucedida
    # (o nó validar_regras só roda quando há tool_calls pendentes)
    for msg in state.get("messages", []):
        if not isinstance(msg, ToolMessage):
            continue
        text = str(msg.content)
        if text.startswith("CREDITOS_INCLUIDOS_SUCESSO:"):
            try:
                a = ast.literal_eval(text.split(":", 1)[1].strip())
                updates["saldo_atual"] = a.get("saldo_creditos_api")
                if "id" in a:
                    updates["assinatura_id"] = a.get("id")
                if a.get("plano"):
                    updates["plano"] = a.get("plano")
                if a.get("status"):
                    updates["status_assinatura"] = a.get("status")
            except Exception:
                pass
            status_atual = "CREDITOS_INCLUIDOS"
        elif text.startswith("EMPRESAS_ENCONTRADAS:") and not state.get("empresa_id"):
            try:
                lista = ast.literal_eval(text.split(":", 1)[1].strip())
                if len(lista) == 1:
                    updates["empresa_id"] = lista[0]["id"]
                    updates["empresa_nome"] = lista[0].get("nome_fantasia")
            except Exception:
                pass
        elif text.startswith("ASSINATURAS_ENCONTRADAS:") and not state.get("assinatura_id"):
            try:
                assinaturas = ast.literal_eval(text.split(":", 1)[1].strip())
                if assinaturas:
                    a = assinaturas[0] if isinstance(assinaturas, list) else assinaturas
                    updates["assinatura_id"] = a["id"]
                    updates["plano"] = a.get("plano")
                    updates["status_assinatura"] = a.get("status")
                    updates["saldo_atual"] = a.get("saldo_creditos_api")
            except Exception:
                pass

    if status_atual == "EM_PROCESSAMENTO":
        if state.get("violacao_regra"):
            status_atual = "RECUSADO_REGRA_NEGOCIO"
        else:
            status_atual = "CONCLUIDO_CONSULTA_OU_RECUSA_ESCOPO"

    updates["status_operacao"] = status_atual
    return updates


def rota_apos_raciocinio(state: AgentState) -> Literal["validar_regras", "resposta_final"]:
    if state.get("iteracoes", 0) > MAX_ITERATIONS:
        return "resposta_final"
    last_message = state["messages"][-1]
    if isinstance(last_message, AIMessage) and last_message.tool_calls:
        return "validar_regras"
    return "resposta_final"


def rota_apos_validacao(state: AgentState) -> Literal["raciocinio", "executar_ferramentas"]:
    if state.get("violacao_regra"):
        return "raciocinio"
    return "executar_ferramentas"


def construir_grafo_agente():
    workflow = StateGraph(AgentState)

    workflow.add_node("raciocinio", no_raciocinio)
    workflow.add_node("validar_regras", no_validar_regras)
    workflow.add_node("executar_ferramentas", no_executar_ferramentas)
    workflow.add_node("resposta_final", no_resposta_final)

    workflow.add_edge(START, "raciocinio")
    workflow.add_conditional_edges(
        "raciocinio",
        rota_apos_raciocinio,
        {
            "validar_regras": "validar_regras",
            "resposta_final": "resposta_final",
        },
    )
    workflow.add_conditional_edges(
        "validar_regras",
        rota_apos_validacao,
        {
            "raciocinio": "raciocinio",
            "executar_ferramentas": "executar_ferramentas",
        },
    )
    workflow.add_edge("executar_ferramentas", "raciocinio")
    workflow.add_edge("resposta_final", END)

    return workflow.compile()


_agent_graph = None


def get_agent_graph():
    global _agent_graph
    if _agent_graph is None:
        _agent_graph = construir_grafo_agente()
    return _agent_graph


def run_agent(user_message: str) -> dict:
    """
    Executa o agente com uma mensagem do analista e retorna resposta estruturada.
    """
    graph = get_agent_graph()

    initial_state: AgentState = {
        "messages": [HumanMessage(content=user_message)],
        "empresa_id": None,
        "empresa_nome": None,
        "assinatura_id": None,
        "plano": None,
        "status_assinatura": None,
        "saldo_atual": None,
        "creditos_solicitados": None,
        "violacao_regra": None,
        "status_operacao": "EM_PROCESSAMENTO",
        "iteracoes": 0,
    }

    result = graph.invoke(
        initial_state,
        config={"recursion_limit": MAX_ITERATIONS + 5},
    )

    # Extrai última mensagem útil do assistente
    mensagem_final = ""
    for msg in reversed(result.get("messages", [])):
        if isinstance(msg, AIMessage) and msg.content and not msg.tool_calls:
            mensagem_final = msg.content
            break
    if not mensagem_final:
        for msg in reversed(result.get("messages", [])):
            if isinstance(msg, AIMessage) and msg.content:
                mensagem_final = msg.content
                break

    status = result.get("status_operacao", "CONCLUIDO")
    violacao = result.get("violacao_regra")

    # Fallback: detecta inclusão a partir das ToolMessages (caso status não tenha sido atualizado)
    creditos_incluidos = status == "CREDITOS_INCLUIDOS"
    quantidade = result.get("creditos_solicitados")
    for msg in result.get("messages", []):
        if not isinstance(msg, ToolMessage):
            continue
        text = str(msg.content)
        if text.startswith("CREDITOS_INCLUIDOS_SUCESSO:"):
            creditos_incluidos = True
            status = "CREDITOS_INCLUIDOS"
            try:
                a = ast.literal_eval(text.split(":", 1)[1].strip())
                if result.get("saldo_atual") is None:
                    result["saldo_atual"] = a.get("saldo_creditos_api")
            except Exception:
                pass
        # captura quantidade pedida em tool_calls do AIMessage
    if quantidade is None:
        for msg in result.get("messages", []):
            if isinstance(msg, AIMessage) and getattr(msg, "tool_calls", None):
                for tc in msg.tool_calls:
                    if tc.get("name") == "credit":
                        quantidade = tc.get("args", {}).get("quantidade")
                        break

    solicitada = quantidade is not None or creditos_incluidos

    if creditos_incluidos:
        parecer = "sucesso"
    elif status in ("RECUSADO_REGRA_NEGOCIO",) or violacao:
        parecer = "recusa"
    elif status == "LIMITE_ITERACOES_EXCEDIDO":
        parecer = "erro"
    else:
        lower = (mensagem_final or "").lower()
        if "ambiguidade" in lower or "mais de uma" in lower:
            parecer = "ambiguidade"
        elif "nenhuma empresa" in lower or "não encontr" in lower:
            parecer = "recusa"
        elif "recus" in lower or "não é permitido" in lower or "fora de escopo" in lower:
            parecer = "recusa"
        else:
            parecer = "sucesso"

    return {
        "parecer": parecer,
        "mensagem": mensagem_final or "Operação concluída.",
        "dados_consultados": {
            "empresa_id": result.get("empresa_id"),
            "nome_empresa": result.get("empresa_nome"),
            "assinatura_id": result.get("assinatura_id"),
            "plano": result.get("plano"),
            "status_assinatura": result.get("status_assinatura"),
            "saldo_anterior": None,
            "saldo_atual": result.get("saldo_atual"),
        },
        "operacao_creditos": {
            "solicitada": solicitada,
            "quantidade": quantidade,
            "realizada": creditos_incluidos,
            "motivo_recusa": None if creditos_incluidos else violacao,
        },
        "status_operacao": status,
        "error": None if parecer != "erro" else status,
    }
