from datetime import date

import pytest
from sqlalchemy import select

from app.domain.enums import NivelAtividade, Sexo, TipoMacro, TipoObjetivo
from app.domain.erros import RecursoNaoEncontradoError
from app.models import Macronutrientes, Objetivo, Usuario
from app.schemas.perfil import PerfilCalcularEntrada
from app.services import perfil_service

USUARIO_VALIDO = {
    "nome": "Felipe",
    "email": "felipe@exemplo.com",
    "sexo": "masculino",
    "data_nascimento": "2001-01-01",
    "altura_cm": 180,
}

# F3: caso extremo achado no spike (varredura da grade plausivel) que dispara o
# 422 de DOMINIO via HTTP -- proteina + gordura ja estouram a meta calorica.
USUARIA_META_INSUFICIENTE = {
    "nome": "Maria",
    "email": "maria@exemplo.com",
    "sexo": "feminino",
    "data_nascimento": "1927-01-01",
    "altura_cm": 51,
}


def _criar_usuario(client, dados: dict = USUARIO_VALIDO) -> int:
    return client.post("/api/usuarios", json=dados).json()["id"]


def _perfil_valido(usuario_id: int) -> dict:
    return {
        "usuario_id": usuario_id,
        "peso_kg": 80,
        "nivel_atividade": "moderado",
        "objetivo": "emagrecer",
    }


def test_calcula_e_retorna_o_perfil(client):
    usuario_id = _criar_usuario(client)

    resposta = client.post("/api/perfil/calcular", json=_perfil_valido(usuario_id))

    assert resposta.status_code == 201
    corpo = resposta.json()
    assert corpo["usuario_id"] == usuario_id
    assert corpo["objetivo_id"] > 0
    assert corpo["tmb_kcal"] == 1882.02
    assert corpo["get_kcal"] == 2917.13
    assert corpo["meta_kcal"] == 2333.7
    assert corpo["macros"] == {
        "proteina_g": 144.0,
        "carboidrato_g": 293.57,
        "gordura_g": 64.82,
    }


def test_recalcular_desativa_o_objetivo_anterior(client):
    usuario_id = _criar_usuario(client)
    primeiro = client.post("/api/perfil/calcular", json=_perfil_valido(usuario_id)).json()

    segundo_payload = {**_perfil_valido(usuario_id), "objetivo": "ganhar_massa"}
    segundo = client.post("/api/perfil/calcular", json=segundo_payload).json()

    assert segundo["objetivo_id"] != primeiro["objetivo_id"]
    assert segundo["meta_kcal"] > primeiro["meta_kcal"]


def test_recalcular_preserva_o_historico(client, db):
    """F5: recalcular nunca apaga historico -- N calculos = N objetivos, 1 ativo,
    N linhas de meta (uma por objetivo). Assere contra o banco, nao a resposta.
    """
    usuario_id = _criar_usuario(client)
    client.post("/api/perfil/calcular", json=_perfil_valido(usuario_id))
    client.post(
        "/api/perfil/calcular", json={**_perfil_valido(usuario_id), "objetivo": "ganhar_massa"}
    )
    client.post(
        "/api/perfil/calcular", json={**_perfil_valido(usuario_id), "objetivo": "manter"}
    )

    objetivos = db.scalars(select(Objetivo).where(Objetivo.usuario_id == usuario_id)).all()
    assert len(objetivos) == 3
    assert sum(1 for o in objetivos if o.ativo) == 1

    for objetivo in objetivos:
        metas = db.scalars(
            select(Macronutrientes).where(
                Macronutrientes.objetivo_id == objetivo.id,
                Macronutrientes.tipo == TipoMacro.META,
            )
        ).all()
        assert len(metas) == 1


def test_usuario_inexistente_retorna_404(client):
    resposta = client.post("/api/perfil/calcular", json=_perfil_valido(9999))

    assert resposta.status_code == 404
    assert resposta.json()["detail"] == "usuario 9999 nao encontrado"


def test_peso_negativo_retorna_422(client):
    usuario_id = _criar_usuario(client)

    resposta = client.post(
        "/api/perfil/calcular", json={**_perfil_valido(usuario_id), "peso_kg": -10}
    )

    assert resposta.status_code == 422
    assert isinstance(resposta.json()["detail"], list)


def test_nivel_atividade_invalido_retorna_422(client):
    usuario_id = _criar_usuario(client)

    resposta = client.post(
        "/api/perfil/calcular",
        json={**_perfil_valido(usuario_id), "nivel_atividade": "hiperativo"},
    )

    assert resposta.status_code == 422
    assert isinstance(resposta.json()["detail"], list)


def test_meta_calorica_insuficiente_retorna_422(client):
    """F2/F3: 422 de DOMINIO (RegraDeNegocioError de calcular_macros), nao de
    Pydantic -- detail e STRING, formato diferente dos dois 422 acima.
    """
    usuario_id = _criar_usuario(client, USUARIA_META_INSUFICIENTE)

    resposta = client.post(
        "/api/perfil/calcular",
        json={
            "usuario_id": usuario_id,
            "peso_kg": 250,
            "nivel_atividade": "sedentario",
            "objetivo": "emagrecer",
        },
    )

    assert resposta.status_code == 422
    detalhe = resposta.json()["detail"]
    assert isinstance(detalhe, str)
    assert "meta calorica insuficiente" in detalhe


def test_o_422_de_dominio_nao_grava_nada(client, db):
    """F7: calcular ANTES de escrever -- um 422 de dominio nao deixa o usuario
    sem nenhum objetivo ativo ate o proximo calculo dar certo.
    """
    usuario_id = _criar_usuario(client, USUARIA_META_INSUFICIENTE)

    resposta = client.post(
        "/api/perfil/calcular",
        json={
            "usuario_id": usuario_id,
            "peso_kg": 250,
            "nivel_atividade": "sedentario",
            "objetivo": "emagrecer",
        },
    )
    assert resposta.status_code == 422

    assert db.scalar(select(Objetivo).where(Objetivo.usuario_id == usuario_id)) is None


@pytest.fixture
def usuario(db):
    u = Usuario(
        nome="Felipe",
        email="felipe.unit@exemplo.com",
        sexo=Sexo.MASCULINO,
        data_nascimento=date(2001, 1, 1),
        altura_cm=180,
    )
    db.add(u)
    db.commit()
    return u


def test_objetivo_ativo_sem_objetivo_levanta_recurso_nao_encontrado(db, usuario):
    """O contrato que T10 consome para descobrir a meta vigente do usuario."""
    with pytest.raises(RecursoNaoEncontradoError):
        perfil_service.objetivo_ativo(db, usuario.id)


def test_objetivo_ativo_devolve_o_ultimo_calculado(db, usuario):
    dados1 = PerfilCalcularEntrada(
        usuario_id=usuario.id,
        peso_kg=80,
        nivel_atividade=NivelAtividade.MODERADO,
        objetivo=TipoObjetivo.EMAGRECER,
    )
    perfil_service.calcular_e_salvar(db, dados1, hoje=date(2026, 6, 1))
    db.commit()

    dados2 = PerfilCalcularEntrada(
        usuario_id=usuario.id,
        peso_kg=80,
        nivel_atividade=NivelAtividade.MODERADO,
        objetivo=TipoObjetivo.GANHAR_MASSA,
    )
    objetivo2, _, _ = perfil_service.calcular_e_salvar(db, dados2, hoje=date(2026, 6, 1))
    db.commit()

    ativo = perfil_service.objetivo_ativo(db, usuario.id)
    assert ativo.id == objetivo2.id
    assert ativo.tipo == TipoObjetivo.GANHAR_MASSA
