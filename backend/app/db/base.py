from sqlalchemy.orm import DeclarativeBase


class Base(DeclarativeBase):
    """Base declarativa compartilhada por todos os modelos.

    Nao importa os models (importar aqui seria circular: um model importa
    `Base` daqui). O registro das tabelas no metadata acontece via
    ``import app.models`` em quem precisa do metadata completo — o
    `conftest.py` dos testes e o `alembic/env.py`.
    """
