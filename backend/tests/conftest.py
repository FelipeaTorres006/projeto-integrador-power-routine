import pytest
from sqlalchemy import create_engine, text
from sqlalchemy.orm import sessionmaker

import app.models  # noqa: F401 -- registra todas as tabelas no metadata
from app.core.config import settings
from app.db.base import Base


@pytest.fixture(scope="session")
def engine():
    """O Postgres de teste e um container UNICO compartilhado por todas as
    worktrees do ciclo. `Base.metadata.drop_all` so conhece as tabelas desta
    branch e falha com DependentObjectsStillExist quando outra tarefa (T6, T7)
    ja deixou tabelas com FK para `usuario` no mesmo banco fisico. Por isso o
    schema inteiro e reiniciado, em vez de drop_all/create_all seletivo.
    """
    eng = create_engine(settings.test_database_url, future=True)
    with eng.begin() as conn:
        conn.execute(text("DROP SCHEMA public CASCADE"))
        conn.execute(text("CREATE SCHEMA public"))
    Base.metadata.create_all(eng)
    yield eng
    eng.dispose()


@pytest.fixture
def limpar_banco(engine):
    """Cada teste que usa banco comeca com o banco vazio e as sequences zeradas.

    NAO e autouse: so quem pede `db` (direto ou via `client`) paga o custo de
    banco vivo. `test_calculos.py` e `test_config.py` continuam rodando sem
    Postgres nenhum, como a fronteira arquitetural de T2 exige.
    """
    with engine.begin() as conn:
        for tabela in reversed(Base.metadata.sorted_tables):
            conn.execute(text(f'TRUNCATE TABLE "{tabela.name}" RESTART IDENTITY CASCADE'))


@pytest.fixture
def db(engine, limpar_banco):
    sessao = sessionmaker(bind=engine, autoflush=False, expire_on_commit=False)()
    yield sessao
    sessao.close()
