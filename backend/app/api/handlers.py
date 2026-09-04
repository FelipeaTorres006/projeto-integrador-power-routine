from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse
from sqlalchemy.exc import IntegrityError

from app.domain.erros import ConflitoError, RecursoNaoEncontradoError, RegraDeNegocioError


def registrar_handlers(app: FastAPI) -> None:
    """Traduz excecoes de dominio em respostas HTTP, em um lugar so.

    Nenhum service precisa conhecer status code; nenhum router precisa de try/except.
    Excecao nao mapeada aqui (ValueError de calculos.py, KeyError de enum, ...) vira
    500 -- deliberado: sao bugs, nao respostas.
    """

    @app.exception_handler(RecursoNaoEncontradoError)
    async def nao_encontrado(request: Request, exc: RecursoNaoEncontradoError):
        return JSONResponse(status_code=404, content={"detail": str(exc)})

    @app.exception_handler(RegraDeNegocioError)
    async def regra_violada(request: Request, exc: RegraDeNegocioError):
        return JSONResponse(status_code=422, content={"detail": str(exc)})

    @app.exception_handler(ConflitoError)
    async def conflito(request: Request, exc: ConflitoError):
        return JSONResponse(status_code=409, content={"detail": str(exc)})

    @app.exception_handler(IntegrityError)
    async def integridade(request: Request, exc: IntegrityError):
        # Ultima camada: uma constraint do banco barrou a operacao. F1: so chega
        # aqui de verdade se o service tiver dado flush() dentro da requisicao --
        # senao a violacao so aparece no commit do get_db e a resposta ja comecou.
        return JSONResponse(
            status_code=409,
            content={"detail": "operacao viola uma restricao de integridade do banco"},
        )
