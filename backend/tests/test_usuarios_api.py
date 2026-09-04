USUARIO_VALIDO = {
    "nome": "Felipe",
    "email": "felipe@exemplo.com",
    "sexo": "masculino",
    "data_nascimento": "2001-01-01",
    "altura_cm": 180,
}


def test_cria_usuario(client):
    resposta = client.post("/api/usuarios", json=USUARIO_VALIDO)
    assert resposta.status_code == 201
    corpo = resposta.json()
    assert corpo["id"] > 0
    assert corpo["email"] == "felipe@exemplo.com"


def test_le_usuario_com_idade_derivada(client):
    usuario_id = client.post("/api/usuarios", json=USUARIO_VALIDO).json()["id"]

    resposta = client.get(f"/api/usuarios/{usuario_id}")
    assert resposta.status_code == 200
    assert resposta.json()["idade"] >= 25


def test_usuario_inexistente_retorna_404(client):
    resposta = client.get("/api/usuarios/9999")
    assert resposta.status_code == 404


def test_rejeita_email_invalido(client):
    resposta = client.post("/api/usuarios", json={**USUARIO_VALIDO, "email": "nao-e-email"})
    assert resposta.status_code == 422


def test_rejeita_altura_fora_da_faixa(client):
    resposta = client.post("/api/usuarios", json={**USUARIO_VALIDO, "altura_cm": 400})
    assert resposta.status_code == 422


def test_rejeita_data_nascimento_no_futuro(client):
    resposta = client.post("/api/usuarios", json={**USUARIO_VALIDO, "data_nascimento": "2099-01-01"})
    assert resposta.status_code == 422


def test_email_duplicado_retorna_409(client):
    client.post("/api/usuarios", json=USUARIO_VALIDO)
    resposta = client.post("/api/usuarios", json=USUARIO_VALIDO)
    assert resposta.status_code == 409


def test_rejeita_nascido_no_ano_corrente(client):
    """F2: idade == 0 nao pode passar do schema, ou calcular_tmb estoura 500 em T8."""
    resposta = client.post(
        "/api/usuarios", json={**USUARIO_VALIDO, "data_nascimento": "2026-01-01"}
    )
    assert resposta.status_code == 422


def test_saude(client):
    resposta = client.get("/api/saude")
    assert resposta.status_code == 200
    assert resposta.json() == {"status": "ok"}
