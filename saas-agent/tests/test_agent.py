from agent.graph import executar_agente


def test_fluxo_nominal_inclui_creditos():
    resultado = executar_agente("Consulte o saldo da empresa Logística Sul e adicione 1.500 créditos extras")
    assert resultado["erro"] is None
    assert resultado["inclusao"]["incluido"] is True
    assert resultado["creditos_solicitados"] == 1500


def test_empresa_ambigua_bloqueia_operacao():
    resultado = executar_agente("Consulte o saldo da empresa Logística e adicione 500 créditos")
    assert resultado["erro"] == "empresa_ambigua"
    assert resultado["inclusao"] is None


def test_limite_de_creditos_bloqueia_operacao():
    resultado = executar_agente("Consulte o saldo da empresa Mercado Norte e adicione 5.000 créditos")
    assert resultado["erro"] == "limite_creditos"
    assert resultado["inclusao"] is None


def test_fora_de_escopo():
    resultado = executar_agente("Cancele a conta da empresa Mercado Norte")
    assert resultado["erro"] == "fora_escopo"
