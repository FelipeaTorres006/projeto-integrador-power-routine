from datetime import date, timedelta

import pytest
from sqlalchemy import select

from app.domain.enums import TipoMacro
from app.models import Macronutrientes, Objetivo, RegistroDiario

USUARIO_VALIDO = {
    "nome": "Felipe",
    "email": "felipe@exemplo.com",
    "sexo": "masculino",
    "data_nascimento": "2001-01-01",
    "altura_cm": 180,
}


def _criar_usuario(client, dados: dict = USUARIO_VALIDO) -> int:
    return client.post("/api/usuarios", json=dados).json()["id"]


@pytest.fixture
def usuario_id(client) -> int:
    novo_id = _criar_usuario(client)
    client.post(
        "/api/perfil/calcular",
        json={
            "usuario_id": novo_id,
            "peso_kg": 80,
            "nivel_atividade": "moderado",
            "objetivo": "emagrecer",
        },
    )
    return novo_id


def registro(usuario_id: int, **overrides) -> dict:
    return {
        "usuario_id": usuario_id,
        "data": "2026-06-01",
        "peso_kg": 80,
        "calorias_kcal": 2300,
        "proteina_g": 140,
        "carboidrato_g": 290,
        "gordura_g": 64,
        "observacoes": "treino de pernas",
    } | overrides


# --- os 6 testes do plano ---------------------------------------------------


def test_cria_registro_diario(client, usuario_id):
    resposta = client.post("/api/diario/registro", json=registro(usuario_id))

    assert resposta.status_code == 201
    corpo = resposta.json()
    assert corpo["data"] == "2026-06-01"
    assert corpo["macros"]["proteina_g"] == 140


def test_registro_do_mesmo_dia_atualiza_em_vez_de_duplicar(client, usuario_id):
    primeiro = client.post("/api/diario/registro", json=registro(usuario_id)).json()
    segundo = client.post(
        "/api/diario/registro", json=registro(usuario_id, calorias_kcal=2500, proteina_g=150)
    ).json()

    assert segundo["id"] == primeiro["id"]
    assert segundo["calorias_kcal"] == 2500
    assert segundo["macros"]["proteina_g"] == 150


def test_dias_diferentes_geram_registros_diferentes(client, usuario_id):
    primeiro = client.post("/api/diario/registro", json=registro(usuario_id)).json()
    segundo = client.post(
        "/api/diario/registro", json=registro(usuario_id, data="2026-06-02")
    ).json()

    assert segundo["id"] != primeiro["id"]


def test_usuario_inexistente_retorna_404(client):
    resposta = client.post("/api/diario/registro", json=registro(9999))
    assert resposta.status_code == 404


def test_rejeita_data_futura(client, usuario_id):
    resposta = client.post("/api/diario/registro", json=registro(usuario_id, data="2099-01-01"))
    assert resposta.status_code == 422
    assert isinstance(resposta.json()["detail"], list)


def test_rejeita_macro_negativo(client, usuario_id):
    resposta = client.post("/api/diario/registro", json=registro(usuario_id, proteina_g=-1))
    assert resposta.status_code == 422


# --- F2: idempotencia provada NO BANCO, nao so na resposta ------------------


def test_regravar_o_dia_tres_vezes_deixa_uma_linha_de_registro_e_uma_de_consumo(
    client, usuario_id, db
):
    client.post("/api/diario/registro", json=registro(usuario_id))
    client.post("/api/diario/registro", json=registro(usuario_id, calorias_kcal=2500))
    client.post("/api/diario/registro", json=registro(usuario_id, calorias_kcal=2600))

    db.expire_all()
    registros = db.scalars(
        select(RegistroDiario).where(RegistroDiario.usuario_id == usuario_id)
    ).all()
    assert len(registros) == 1
    assert registros[0].calorias_kcal == 2600

    consumos = db.scalars(
        select(Macronutrientes).where(
            Macronutrientes.registro_diario_id == registros[0].id,
            Macronutrientes.tipo == TipoMacro.CONSUMO,
        )
    ).all()
    assert len(consumos) == 1


# --- F3: a linha tipo=meta do objetivo sobrevive a reescrita do dia ---------


def test_regravar_o_dia_nao_toca_a_linha_de_meta_do_objetivo(client, usuario_id, db):
    objetivo = db.scalar(
        select(Objetivo).where(Objetivo.usuario_id == usuario_id, Objetivo.ativo.is_(True))
    )
    meta = db.scalar(
        select(Macronutrientes).where(
            Macronutrientes.objetivo_id == objetivo.id, Macronutrientes.tipo == TipoMacro.META
        )
    )
    meta_id = meta.id
    meta_proteina_original = meta.proteina_g

    client.post("/api/diario/registro", json=registro(usuario_id))
    client.post("/api/diario/registro", json=registro(usuario_id, proteina_g=200))

    db.expire_all()
    meta_depois = db.get(Macronutrientes, meta_id)
    assert meta_depois.tipo == TipoMacro.META
    assert meta_depois.objetivo_id == objetivo.id
    assert meta_depois.registro_diario_id is None
    assert meta_depois.proteina_g == meta_proteina_original


# --- F4: fronteira hoje/amanha (o CHECK nao existe, so o Pydantic barra) ----


def test_data_de_hoje_e_aceita_e_amanha_e_rejeitada(client, usuario_id):
    hoje = date.today().isoformat()
    amanha = (date.today() + timedelta(days=1)).isoformat()

    resposta_hoje = client.post("/api/diario/registro", json=registro(usuario_id, data=hoje))
    assert resposta_hoje.status_code == 201

    resposta_amanha = client.post(
        "/api/diario/registro", json=registro(usuario_id, data=amanha)
    )
    assert resposta_amanha.status_code == 422
    assert isinstance(resposta_amanha.json()["detail"], list)


# --- F5: o UNIQUE e composto - dois usuarios podem ter o mesmo dia ---------


def test_dias_de_usuarios_diferentes_sao_isolados(client, usuario_id, db):
    outro_id = _criar_usuario(client, {**USUARIO_VALIDO, "email": "outro@exemplo.com"})

    resp_a = client.post(
        "/api/diario/registro", json=registro(usuario_id, data="2026-06-01")
    ).json()
    resp_b = client.post(
        "/api/diario/registro", json=registro(outro_id, data="2026-06-01")
    ).json()
    assert resp_a["id"] != resp_b["id"]

    client.post(
        "/api/diario/registro",
        json=registro(usuario_id, data="2026-06-01", calorias_kcal=9999),
    )

    db.expire_all()
    registro_b = db.get(RegistroDiario, resp_b["id"])
    assert registro_b.calorias_kcal == 2300


# --- F6: a reescrita e substituicao TOTAL, nao merge ------------------------


def test_regravar_sem_observacoes_apaga_a_anterior(client, usuario_id):
    primeiro = client.post("/api/diario/registro", json=registro(usuario_id)).json()
    assert primeiro["observacoes"] == "treino de pernas"

    corpo_sem_observacoes = {k: v for k, v in registro(usuario_id).items() if k != "observacoes"}
    segundo = client.post("/api/diario/registro", json=corpo_sem_observacoes).json()

    assert segundo["id"] == primeiro["id"]
    assert segundo["observacoes"] is None


# --- F13: registrar NAO exige objetivo ativo --------------------------------


def test_registra_o_dia_sem_objetivo_ativo(client):
    novo_id = _criar_usuario(client, {**USUARIO_VALIDO, "email": "sem-objetivo@exemplo.com"})

    resposta = client.post("/api/diario/registro", json=registro(novo_id))

    assert resposta.status_code == 201


# --- F15: fronteira de observacoes alinhada com o varchar(500) -------------


def test_fronteira_de_observacoes_500_ok_501_rejeitado(client, usuario_id):
    resposta_500 = client.post(
        "/api/diario/registro", json=registro(usuario_id, observacoes="a" * 500)
    )
    assert resposta_500.status_code == 201

    resposta_501 = client.post(
        "/api/diario/registro", json=registro(usuario_id, observacoes="a" * 501)
    )
    assert resposta_501.status_code == 422


# --- F10: corrida perdida vira 409 de verdade (com db.flush() na requisicao) ---


def test_corrida_no_mesmo_dia_vira_409_e_nao_500(client, usuario_id, monkeypatch):
    from app.services import diario_service

    client.post("/api/diario/registro", json=registro(usuario_id))

    # Simula duas requisicoes concorrentes: o SELECT desta requisicao nao ve o
    # registro que a outra ja gravou, entao ela tenta INSERT e esbarra no UNIQUE.
    monkeypatch.setattr(diario_service, "_registro_do_dia", lambda *args, **kwargs: None)

    resposta = client.post("/api/diario/registro", json=registro(usuario_id))

    assert resposta.status_code == 409
    assert resposta.json()["detail"] == "operacao viola uma restricao de integridade do banco"
