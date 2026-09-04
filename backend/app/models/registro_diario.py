from datetime import date

from sqlalchemy import CheckConstraint, Date, Float, ForeignKey, String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base


class RegistroDiario(Base):
    """Uma linha por usuário por dia."""

    __tablename__ = "registro_diario"

    id: Mapped[int] = mapped_column(primary_key=True)
    usuario_id: Mapped[int] = mapped_column(
        ForeignKey("usuario.id", ondelete="CASCADE"), nullable=False, index=True
    )
    data: Mapped[date] = mapped_column(Date, nullable=False)
    peso_kg: Mapped[float] = mapped_column(Float, nullable=False)
    calorias_kcal: Mapped[float] = mapped_column(Float, nullable=False)
    observacoes: Mapped[str | None] = mapped_column(String(500), nullable=True)

    __table_args__ = (
        UniqueConstraint("usuario_id", "data", name="uq_registro_diario_usuario_data"),
        CheckConstraint("peso_kg > 0", name="ck_registro_peso_positivo"),
        CheckConstraint("calorias_kcal >= 0", name="ck_registro_calorias_nao_negativas"),
    )
