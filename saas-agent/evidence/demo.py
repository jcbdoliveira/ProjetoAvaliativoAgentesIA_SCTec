import json

from dotenv import load_dotenv

load_dotenv()

from agent.graph import run_agent

CENARIOS = [
    ("Cenário 1 — fluxo nominal", "Consulte o saldo da empresa Logística Sul e adicione 1.500 créditos extras"),
    ("Cenário 2 — ambiguidade", "Consulte o saldo da empresa Logística e adicione 500 créditos"),
    ("Cenário 3 — limite", "Consulte o saldo da empresa Mercado Norte e adicione 5.000 créditos"),
]

for titulo, instrucao in CENARIOS:
    print(f"\n{titulo}\nPOST /agent/executar\n{json.dumps({'instrucao': instrucao}, ensure_ascii=False)}")
    print(json.dumps(run_agent(instrucao), ensure_ascii=False, indent=2))
