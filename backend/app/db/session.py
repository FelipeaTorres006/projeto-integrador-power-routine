from collections.abc import Generator

from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker

from app.core.config import settings

# pool_pre_ping: o Neon suspende o banco apos 5 min parado e derruba as conexoes;
# sem o ping, a primeira requisicao depois da pausa pegaria uma conexao morta (500).
engine = create_engine(settings.database_url, future=True, pool_pre_ping=True)
SessionLocal = sessionmaker(bind=engine, autoflush=False, expire_on_commit=False)


def get_db() -> Generator[Session, None, None]:
    """Uma transacao por requisicao: commit no sucesso, rollback em qualquer excecao.

    Os services usam `flush()` para obter IDs; o commit acontece aqui, uma vez so.
    """
    db = SessionLocal()
    try:
        yield db
        db.commit()
    except Exception:
        db.rollback()
        raise
    finally:
        db.close()
