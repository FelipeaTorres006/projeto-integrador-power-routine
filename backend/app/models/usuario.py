from datetime import date

from sqlalchemy import CheckConstraint, Date, Enum as SAEnum, Float, String
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base
from app.domain.enums import Sexo


def enum_pg(enum_cls, nome: str) -> SAEnum:
    """Mapeia um Enum Python para um ENUM nativo do PostgreSQL usando os valores.

    Os rotulos gravados no banco sao os `.value` (minusculos, snake_case), nunca
    os nomes MAIUSCULOS dos membros do Enum.
    """
    return SAEnum(enum_cls, name=nome, values_callable=lambda e: [item.value for item in e])


class Usuario(Base):
    __tablename__ = "usuario"

    id: Mapped[int] = mapped_column(primary_key=True)
    nome: Mapped[str] = mapped_column(String(120), nullable=False)
    email: Mapped[str] = mapped_column(String(255), unique=True, nullable=False)
    sexo: Mapped[Sexo] = mapped_column(enum_pg(Sexo, "sexo"), nullable=False)
    data_nascimento: Mapped[date] = mapped_column(Date, nullable=False)
    altura_cm: Mapped[float] = mapped_column(Float, nullable=False)

    __table_args__ = (
        CheckConstraint("altura_cm > 0 AND altura_cm < 300", name="ck_usuario_altura_valida"),
    )
