"""CORS de ponta a ponta no app real, sem banco.

Importa `app.main` de proposito: o que esta sob teste e a configuracao do
middleware que vai para producao, nao um app descartavel. `app.main` nao abre
conexao no import (o engine so conecta na primeira query), entao estes testes
rodam sem Postgres, como `test_calculos.py`.
"""

import pytest
from fastapi.testclient import TestClient

from app.main import app

ORIGEM_PAGES = "https://felipeatorres006.github.io"


@pytest.fixture
def cliente() -> TestClient:
    return TestClient(app)


def _preflight(cliente: TestClient, origem: str, metodo: str = "POST"):
    return cliente.options(
        "/api/usuarios",
        headers={
            "Origin": origem,
            "Access-Control-Request-Method": metodo,
            "Access-Control-Request-Headers": "content-type",
        },
    )


def test_preflight_do_github_pages_e_aceito(cliente):
    resposta = _preflight(cliente, ORIGEM_PAGES)
    assert resposta.status_code == 200
    assert resposta.headers["access-control-allow-origin"] == ORIGEM_PAGES


@pytest.mark.parametrize("origem", ["http://localhost:5500", "http://127.0.0.1:8080", "http://localhost"])
def test_preflight_de_localhost_e_aceito(cliente, origem):
    resposta = _preflight(cliente, origem)
    assert resposta.status_code == 200
    assert resposta.headers["access-control-allow-origin"] == origem


@pytest.mark.parametrize(
    "origem",
    [
        "https://site-malicioso.com",
        "https://felipeatorres006.github.io.site-malicioso.com",
        "http://localhost.site-malicioso.com",
        "null",  # pagina aberta via file://
    ],
)
def test_preflight_de_origem_desconhecida_e_recusado(cliente, origem):
    resposta = _preflight(cliente, origem)
    assert "access-control-allow-origin" not in resposta.headers


def test_preflight_recusa_metodo_que_a_api_nao_tem(cliente):
    resposta = _preflight(cliente, ORIGEM_PAGES, metodo="DELETE")
    assert resposta.status_code == 400


def test_get_simples_de_origem_permitida_recebe_o_cabecalho(cliente):
    resposta = cliente.get("/api/saude", headers={"Origin": ORIGEM_PAGES})
    assert resposta.status_code == 200
    assert resposta.headers["access-control-allow-origin"] == ORIGEM_PAGES


def test_sem_credenciais(cliente):
    """Sem cookie nem autenticacao, o navegador nao precisa enviar credenciais."""
    resposta = _preflight(cliente, ORIGEM_PAGES)
    assert "access-control-allow-credentials" not in resposta.headers
