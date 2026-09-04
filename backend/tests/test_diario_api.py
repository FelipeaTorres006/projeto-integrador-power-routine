import random
from datetime import date, timedelta

import pytest
from sqlalchemy import and_, event, select

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
def perfil(client) -> dict:
    """Corpo da resposta de POST /api/perfil/calcular -- fonte das expectativas
    numericas dos testes de T10 (F3): o literal 2333.70 expira em 2027-01-01,
    quando o usuario desta fixture faz 26 anos e a meta cai para 2326.66.
    Derivar da resposta real deixa a asserta mais forte e sem prazo de validade.
    """
    novo_id = _criar_usuario(client)
    return client.post(
        "/api/perfil/calcular",
        json={
            "usuario_id": novo_id,
            "peso_kg": 80,
            "nivel_atividade": "moderado",
            "objetivo": "emagrecer",
        },
    ).json()


@pytest.fixture
def usuario_id(perfil: dict) -> int:
    return perfil["usuario_id"]


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


# =============================================================================
# T10: GET /api/diario/{usuario_id} -- comparativo meta vs. consumo
# =============================================================================


# --- os 3 testes do plano (com asserta derivada de POST /api/perfil/calcular,
# F3: o literal 2333.70 expira em 2027-01-01) ---------------------------------


def test_get_comparativo_devolve_dias_do_mais_recente_ao_mais_antigo_com_meta_vigente(
    client, usuario_id, perfil
):
    client.post("/api/diario/registro", json=registro(usuario_id, data="2026-06-01"))
    client.post(
        "/api/diario/registro",
        json=registro(
            usuario_id,
            data="2026-06-02",
            calorias_kcal=2650,
            proteina_g=150,
            carboidrato_g=330,
            gordura_g=70,
        ),
    )

    resposta = client.get(f"/api/diario/{usuario_id}")
    assert resposta.status_code == 200
    corpo = resposta.json()

    assert corpo["usuario_id"] == usuario_id
    assert corpo["objetivo"] == "emagrecer"
    assert corpo["meta_kcal"] == perfil["meta_kcal"]
    assert len(corpo["registros"]) == 2
    assert corpo["registros"][0]["data"] == "2026-06-02"
    assert corpo["registros"][1]["data"] == "2026-06-01"

    dia1 = corpo["registros"][1]
    assert dia1["consumido_kcal"] == 2300
    assert dia1["meta_kcal"] == perfil["meta_kcal"]
    assert dia1["diferenca_kcal"] == round(2300 - perfil["meta_kcal"], 2)
    assert dia1["aderencia_percentual"] == round(2300 / perfil["meta_kcal"] * 100, 2)
    assert dia1["macros_consumidos"] == {
        "proteina_g": 140.0,
        "carboidrato_g": 290.0,
        "gordura_g": 64.0,
    }
    assert dia1["macros_meta"] == perfil["macros"]


def test_macros_meta_e_identico_em_todas_as_linhas_e_igual_ao_do_topo(client, usuario_id, perfil):
    client.post("/api/diario/registro", json=registro(usuario_id, data="2026-06-01"))
    client.post("/api/diario/registro", json=registro(usuario_id, data="2026-06-02"))

    resposta = client.get(f"/api/diario/{usuario_id}")
    corpo = resposta.json()

    assert len(corpo["registros"]) == 2
    for dia in corpo["registros"]:
        assert dia["macros_meta"] == perfil["macros"]


def test_usuario_inexistente_no_get_retorna_404(client):
    resposta = client.get("/api/diario/9999")
    assert resposta.status_code == 404


# --- F4: o predicado tipo=consumo tem que ficar no ON do LEFT OUTER JOIN,
# nunca no WHERE -- contraprova medida dos dois lados -----------------------


def test_dia_sem_linha_de_consumo_aparece_zerado_contraprova_predicado_no_where(
    client, usuario_id, db
):
    client.post("/api/diario/registro", json=registro(usuario_id, data="2026-06-01"))
    client.post("/api/diario/registro", json=registro(usuario_id, data="2026-06-02"))

    db.expire_all()
    registro_sem_consumo = db.scalar(
        select(RegistroDiario).where(
            RegistroDiario.usuario_id == usuario_id, RegistroDiario.data == date(2026, 6, 2)
        )
    )
    consumo = db.scalar(
        select(Macronutrientes).where(
            Macronutrientes.registro_diario_id == registro_sem_consumo.id,
            Macronutrientes.tipo == TipoMacro.CONSUMO,
        )
    )
    db.delete(consumo)
    db.flush()

    resposta = client.get(f"/api/diario/{usuario_id}")
    assert resposta.status_code == 200
    dias = resposta.json()["registros"]
    assert len(dias) == 2
    dia_sem_consumo = next(d for d in dias if d["data"] == "2026-06-02")
    assert dia_sem_consumo["macros_consumidos"] == {
        "proteina_g": 0,
        "carboidrato_g": 0,
        "gordura_g": 0,
    }

    # Contraprova: o MESMO predicado, movido do ON para o WHERE, perde a linha
    # sem consumo -- o LEFT JOIN vira INNER JOIN na pratica.
    consulta_com_predicado_no_on = (
        select(RegistroDiario, Macronutrientes)
        .outerjoin(
            Macronutrientes,
            and_(
                Macronutrientes.registro_diario_id == RegistroDiario.id,
                Macronutrientes.tipo == TipoMacro.CONSUMO,
            ),
        )
        .where(RegistroDiario.usuario_id == usuario_id)
    )
    linhas_com_predicado_no_on = db.execute(consulta_com_predicado_no_on).all()
    assert len(linhas_com_predicado_no_on) == 2

    consulta_com_predicado_no_where = (
        select(RegistroDiario, Macronutrientes)
        .outerjoin(Macronutrientes, Macronutrientes.registro_diario_id == RegistroDiario.id)
        .where(
            RegistroDiario.usuario_id == usuario_id,
            Macronutrientes.tipo == TipoMacro.CONSUMO,
        )
    )
    linhas_com_predicado_no_where = db.execute(consulta_com_predicado_no_where).all()
    assert len(linhas_com_predicado_no_where) == 1


# --- F6: ordenacao correta em 31 dias embaralhados, atravessando a virada
# de mes (18/05 -> 17/06), nao so em 3 dias em ordem -------------------------


def test_ordenacao_correta_com_31_dias_embaralhados_atravessando_virada_de_mes(
    client, usuario_id
):
    dias = [date(2026, 5, 18) + timedelta(days=i) for i in range(31)]
    embaralhados = dias.copy()
    random.Random(42).shuffle(embaralhados)
    for dia in embaralhados:
        client.post("/api/diario/registro", json=registro(usuario_id, data=dia.isoformat()))

    resposta = client.get(f"/api/diario/{usuario_id}")
    assert resposta.status_code == 200
    datas_retornadas = [r["data"] for r in resposta.json()["registros"]]
    assert len(datas_retornadas) == 31
    assert datas_retornadas == sorted(datas_retornadas, reverse=True)


# --- F5: nao ha N+1 -- o numero de SELECTs e constante com o numero de dias,
# nao um valor magico fixo (o valor absoluto e refem de detalhes do SQLAlchemy) --


def test_get_dispara_numero_constante_de_selects_independente_da_quantidade_de_dias(
    client, db
):
    def contar_selects_do_get(quantidade_dias: int) -> int:
        novo_id = _criar_usuario(
            client, {**USUARIO_VALIDO, "email": f"selects-{quantidade_dias}@exemplo.com"}
        )
        client.post(
            "/api/perfil/calcular",
            json={
                "usuario_id": novo_id,
                "peso_kg": 80,
                "nivel_atividade": "moderado",
                "objetivo": "emagrecer",
            },
        )
        for i in range(quantidade_dias):
            client.post(
                "/api/diario/registro",
                json=registro(novo_id, data=(date(2026, 1, 1) + timedelta(days=i)).isoformat()),
            )

        statements: list[str] = []

        def escuta(conn, cursor, statement, parameters, context, executemany):
            statements.append(statement)

        engine = db.get_bind()
        event.listen(engine, "before_cursor_execute", escuta)
        try:
            resposta = client.get(f"/api/diario/{novo_id}")
        finally:
            event.remove(engine, "before_cursor_execute", escuta)

        assert resposta.status_code == 200
        assert len(resposta.json()["registros"]) == quantidade_dias
        return len(statements)

    contagem_1_dia = contar_selects_do_get(1)
    contagem_20_dias = contar_selects_do_get(20)

    assert contagem_1_dia == contagem_20_dias


# --- F7: usuario com objetivo ativo e ZERO dias devolve 200, nao 404 --------


def test_usuario_com_objetivo_e_sem_dias_devolve_200_com_lista_vazia(client, usuario_id, perfil):
    resposta = client.get(f"/api/diario/{usuario_id}")
    assert resposta.status_code == 200
    corpo = resposta.json()
    assert corpo["registros"] == []
    assert corpo["usuario_id"] == usuario_id
    assert corpo["meta_kcal"] == perfil["meta_kcal"]


# --- F9: os dois 404 do GET tem causas e mensagens diferentes ---------------


def test_404_de_usuario_inexistente_e_404_de_sem_objetivo_tem_mensagens_diferentes(client):
    resposta_usuario_inexistente = client.get("/api/diario/9999")
    assert resposta_usuario_inexistente.status_code == 404

    novo_id = _criar_usuario(client, {**USUARIO_VALIDO, "email": "sem-objetivo-get@exemplo.com"})
    resposta_sem_objetivo = client.get(f"/api/diario/{novo_id}")
    assert resposta_sem_objetivo.status_code == 404

    assert (
        resposta_usuario_inexistente.json()["detail"] != resposta_sem_objetivo.json()["detail"]
    )


# --- F1: nao existe CHECK em objetivo.meta_kcal -- 0/negativo e gravavel
# direto no banco e o GET tem que virar 422, nao ZeroDivisionError -> 500 ----


def test_meta_kcal_zero_ou_negativa_no_banco_vira_422_em_vez_de_500(client, usuario_id, db):
    objetivo = db.scalar(
        select(Objetivo).where(Objetivo.usuario_id == usuario_id, Objetivo.ativo.is_(True))
    )
    objetivo.meta_kcal = 0
    db.flush()

    resposta = client.get(f"/api/diario/{usuario_id}")
    assert resposta.status_code == 422
    assert isinstance(resposta.json()["detail"], str)


# --- F2: a linha tipo=meta ausente tem que virar 422, nao macros_meta
# zerado em silencio ao lado de um meta_kcal real ----------------------------


def test_linha_de_meta_ausente_vira_422_em_vez_de_zerado_silencioso(client, usuario_id, db):
    objetivo = db.scalar(
        select(Objetivo).where(Objetivo.usuario_id == usuario_id, Objetivo.ativo.is_(True))
    )
    meta = db.scalar(
        select(Macronutrientes).where(
            Macronutrientes.objetivo_id == objetivo.id, Macronutrientes.tipo == TipoMacro.META
        )
    )
    db.delete(meta)
    db.flush()

    resposta = client.get(f"/api/diario/{usuario_id}")
    assert resposta.status_code == 422
    assert isinstance(resposta.json()["detail"], str)


# --- F8: dias antigos sao comparados com a meta VIGENTE, nao com a que
# valia no dia -- documentado, nao e bug -------------------------------------


def test_dia_antigo_e_comparado_com_a_meta_vigente_nao_a_que_valia_no_dia(
    client, usuario_id, perfil
):
    client.post("/api/diario/registro", json=registro(usuario_id, data="2026-06-01"))

    meta_antes = client.get(f"/api/diario/{usuario_id}").json()["registros"][0]["meta_kcal"]
    assert meta_antes == perfil["meta_kcal"]

    novo_perfil = client.post(
        "/api/perfil/calcular",
        json={
            "usuario_id": usuario_id,
            "peso_kg": 80,
            "nivel_atividade": "moderado",
            "objetivo": "ganhar_massa",
        },
    ).json()
    assert novo_perfil["meta_kcal"] != meta_antes

    meta_depois = client.get(f"/api/diario/{usuario_id}").json()["registros"][0]["meta_kcal"]
    assert meta_depois == novo_perfil["meta_kcal"]
    assert meta_depois != meta_antes


# --- isolamento: o resumo de A nao mostra os dias de B, e as metas diferem --


def test_isolamento_entre_usuarios_diferentes(client, usuario_id, perfil):
    outro_id = _criar_usuario(client, {**USUARIO_VALIDO, "email": "isolamento@exemplo.com"})
    client.post(
        "/api/perfil/calcular",
        json={
            "usuario_id": outro_id,
            "peso_kg": 100,
            "nivel_atividade": "intenso",
            "objetivo": "ganhar_massa",
        },
    )

    client.post("/api/diario/registro", json=registro(usuario_id, data="2026-06-01"))
    client.post(
        "/api/diario/registro",
        json=registro(outro_id, data="2026-06-05", calorias_kcal=3000),
    )

    resposta_a = client.get(f"/api/diario/{usuario_id}").json()
    resposta_b = client.get(f"/api/diario/{outro_id}").json()

    assert len(resposta_a["registros"]) == 1
    assert resposta_a["registros"][0]["data"] == "2026-06-01"
    assert len(resposta_b["registros"]) == 1
    assert resposta_b["registros"][0]["data"] == "2026-06-05"
    assert resposta_a["meta_kcal"] != resposta_b["meta_kcal"]


# --- F13: aderencia_percentual nao e limitada a 100 -------------------------


def test_aderencia_zero_quando_consumo_e_zero(client, usuario_id):
    client.post("/api/diario/registro", json=registro(usuario_id, calorias_kcal=0))

    resposta = client.get(f"/api/diario/{usuario_id}")
    dia = resposta.json()["registros"][0]
    assert dia["consumido_kcal"] == 0
    assert dia["aderencia_percentual"] == 0.0


def test_aderencia_pode_passar_de_100_quando_estoura_a_meta(client, usuario_id, perfil):
    client.post("/api/diario/registro", json=registro(usuario_id, calorias_kcal=15000))

    resposta = client.get(f"/api/diario/{usuario_id}")
    dia = resposta.json()["registros"][0]
    esperado = round(15000 / perfil["meta_kcal"] * 100, 2)
    assert dia["aderencia_percentual"] == esperado
    assert dia["aderencia_percentual"] > 100
