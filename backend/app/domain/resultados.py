"""Resultados de dominio devolvidos por app.services.calculos.

Dataclasses puras (sem FastAPI, sem SQLAlchemy) que carregam a saida do
calculo de perfil e macronutrientes.
"""

from dataclasses import dataclass


@dataclass(frozen=True)
class Macros:
    """Alvo diario de macronutrientes, em gramas."""

    proteina_g: float
    carboidrato_g: float
    gordura_g: float


@dataclass(frozen=True)
class ResultadoPerfil:
    """Saida completa do orquestrador de perfil: idade, energia e macros."""

    idade: int
    tmb_kcal: float
    get_kcal: float
    meta_kcal: float
    macros: Macros
