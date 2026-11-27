"""Configurações centralizadas (compatibilidade). Preferir variáveis de ambiente."""

import os


class Settings:
    groq_api_key: str = os.getenv("GROQ_API_KEY", "")
    llm_model: str = os.getenv("LLM_MODEL", "openai/gpt-oss-120b")
    saas_api_base_url: str = os.getenv("SAAS_API_BASE_URL", "http://localhost:8002")
    agent_api_port: int = int(os.getenv("AGENT_API_PORT", "8000"))
    recursion_limit: int = int(os.getenv("AGENT_MAX_ITERATIONS", "10"))
    max_creditos_por_operacao: int = 3000


settings = Settings()
