"""Testa os 4 handlers de erro isoladamente, sem banco.

T7 produz o mapa excecao->status que T8, T9 e T10 consomem. Dois dos quatro
handlers (RegraDeNegocioError, ConflitoError) nao tem produtor em T7 -- sem
este arquivo, ficariam sem teste ate T8 comecar a gravar dados.

Usa um FastAPI() descartavel: nao importa app.main, nao toca em banco, respeita
a fronteira que T5 preservou ao tirar o autouse da fixture de banco.
"""

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlalchemy.exc import IntegrityError

from app.api.handlers import registrar_handlers
from app.domain.erros import ConflitoError, RecursoNaoEncontradoError, RegraDeNegocioError


@pytest.fixture
def app_de_prova() -> FastAPI:
    app = FastAPI()
    registrar_handlers(app)

    @app.get("/nao-encontrado")
    def _nao_encontrado():
        raise RecursoNaoEncontradoError("recurso 1 nao encontrado")

    @app.get("/regra-violada")
    def _regra_violada():
        raise RegraDeNegocioError("regra violada")

    @app.get("/conflito")
    def _conflito():
        raise ConflitoError("estado conflitante")

    @app.get("/integridade")
    def _integridade():
        raise IntegrityError("statement", {}, Exception("violacao de constraint"))

    return app


@pytest.fixture
def cliente_de_prova(app_de_prova: FastAPI) -> TestClient:
    with TestClient(app_de_prova) as c:
        yield c


def test_recurso_nao_encontrado_vira_404(cliente_de_prova):
    resposta = cliente_de_prova.get("/nao-encontrado")
    assert resposta.status_code == 404
    assert resposta.json() == {"detail": "recurso 1 nao encontrado"}


def test_regra_de_negocio_vira_422(cliente_de_prova):
    resposta = cliente_de_prova.get("/regra-violada")
    assert resposta.status_code == 422
    assert resposta.json() == {"detail": "regra violada"}


def test_conflito_vira_409(cliente_de_prova):
    resposta = cliente_de_prova.get("/conflito")
    assert resposta.status_code == 409
    assert resposta.json() == {"detail": "estado conflitante"}


def test_integrity_error_vira_409_sem_vazar_texto_do_postgres(cliente_de_prova):
    resposta = cliente_de_prova.get("/integridade")
    assert resposta.status_code == 409
    assert resposta.json() == {
        "detail": "operacao viola uma restricao de integridade do banco"
    }
