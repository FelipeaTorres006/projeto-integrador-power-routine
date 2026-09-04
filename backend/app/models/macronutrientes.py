from sqlalchemy import CheckConstraint, Float, ForeignKey, Index, text
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base
from app.domain.enums import TipoMacro
from app.models.usuario import enum_pg


class Macronutrientes(Base):
    """Distribuição de macros — prescrita (`meta`) ou realizada (`consumo`).

    Uma tabela só, discriminada por `tipo`. Cada linha aponta para exatamente um
    dono: `meta` pertence a um Objetivo, `consumo` pertence a um RegistroDiario.
    O CHECK abaixo torna qualquer outra combinação impossível no banco.
    """

    __tablename__ = "macronutrientes"

    id: Mapped[int] = mapped_column(primary_key=True)
    tipo: Mapped[TipoMacro] = mapped_column(enum_pg(TipoMacro, "tipo_macro"), nullable=False)
    objetivo_id: Mapped[int | None] = mapped_column(
        ForeignKey("objetivo.id", ondelete="CASCADE"), nullable=True
    )
    registro_diario_id: Mapped[int | None] = mapped_column(
        ForeignKey("registro_diario.id", ondelete="CASCADE"), nullable=True
    )
    proteina_g: Mapped[float] = mapped_column(Float, nullable=False)
    carboidrato_g: Mapped[float] = mapped_column(Float, nullable=False)
    gordura_g: Mapped[float] = mapped_column(Float, nullable=False)

    __table_args__ = (
        CheckConstraint(
            "(tipo = 'meta' AND objetivo_id IS NOT NULL AND registro_diario_id IS NULL)"
            " OR "
            "(tipo = 'consumo' AND registro_diario_id IS NOT NULL AND objetivo_id IS NULL)",
            name="ck_macronutrientes_discriminador",
        ),
        CheckConstraint(
            "proteina_g >= 0 AND carboidrato_g >= 0 AND gordura_g >= 0",
            name="ck_macronutrientes_nao_negativo",
        ),
        # 1:1 com cada dono, garantido por índices parciais.
        Index(
            "ix_macro_meta_unica_por_objetivo",
            "objetivo_id",
            unique=True,
            postgresql_where=text("tipo = 'meta'"),
        ),
        Index(
            "ix_macro_consumo_unico_por_registro",
            "registro_diario_id",
            unique=True,
            postgresql_where=text("tipo = 'consumo'"),
        ),
    )
