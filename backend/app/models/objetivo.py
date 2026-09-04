from datetime import date

from sqlalchemy import Boolean, CheckConstraint, Date, Float, ForeignKey, Index, text
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base
from app.domain.enums import NivelAtividade, TipoObjetivo
from app.models.usuario import enum_pg


class Objetivo(Base):
    """Meta nutricional vigente de um usuário, com o resultado do cálculo congelado.

    Guardar tmb/get/meta é intencional: é o histórico do que foi prescrito naquele
    momento, e não muda se as fórmulas do sistema forem ajustadas depois.
    """

    __tablename__ = "objetivo"

    id: Mapped[int] = mapped_column(primary_key=True)
    usuario_id: Mapped[int] = mapped_column(
        ForeignKey("usuario.id", ondelete="CASCADE"), nullable=False, index=True
    )
    tipo: Mapped[TipoObjetivo] = mapped_column(enum_pg(TipoObjetivo, "tipo_objetivo"), nullable=False)
    nivel_atividade: Mapped[NivelAtividade] = mapped_column(
        enum_pg(NivelAtividade, "nivel_atividade"), nullable=False
    )
    peso_kg: Mapped[float] = mapped_column(Float, nullable=False)
    peso_meta_kg: Mapped[float | None] = mapped_column(Float, nullable=True)
    tmb_kcal: Mapped[float] = mapped_column(Float, nullable=False)
    get_kcal: Mapped[float] = mapped_column(Float, nullable=False)
    meta_kcal: Mapped[float] = mapped_column(Float, nullable=False)
    data_inicio: Mapped[date] = mapped_column(Date, nullable=False)
    ativo: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)

    __table_args__ = (
        CheckConstraint("peso_kg > 0", name="ck_objetivo_peso_positivo"),
        # Índice parcial: a unicidade só vale para as linhas ativas.
        Index(
            "ix_objetivo_um_ativo_por_usuario",
            "usuario_id",
            unique=True,
            postgresql_where=text("ativo"),
        ),
    )
