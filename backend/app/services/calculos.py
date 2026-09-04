"""Regras de negócio do Power Routine.

Funções puras: recebem números, devolvem números. Não importam FastAPI nem
SQLAlchemy — é isso que permite testá-las sem banco e sem servidor.
"""

from datetime import date

from app.domain.enums import NivelAtividade, Sexo, TipoObjetivo

# Coeficientes da equação de Harris-Benedict revisada (Roza & Shizgal, 1984).
_COEFICIENTES_TMB = {
    Sexo.MASCULINO: (88.362, 13.397, 4.799, 5.677),
    Sexo.FEMININO: (447.593, 9.247, 3.098, 4.330),
}

# Multiplicador da TMB por nível de atividade física (fórmula de Harris-Benedict).
_FATORES_ATIVIDADE = {
    NivelAtividade.SEDENTARIO: 1.2,
    NivelAtividade.LEVE: 1.375,
    NivelAtividade.MODERADO: 1.55,
    NivelAtividade.INTENSO: 1.725,
    NivelAtividade.MUITO_INTENSO: 1.9,
}

# Ajuste do GET conforme o objetivo: déficit para emagrecer, superávit para ganhar massa.
_AJUSTES_OBJETIVO = {
    TipoObjetivo.EMAGRECER: 0.80,
    TipoObjetivo.MANTER: 1.00,
    TipoObjetivo.GANHAR_MASSA: 1.15,
}


def calcular_idade(data_nascimento: date, hoje: date) -> int:
    """Idade em anos completos. `hoje` é parâmetro para o cálculo ser determinístico."""
    idade = hoje.year - data_nascimento.year
    if (hoje.month, hoje.day) < (data_nascimento.month, data_nascimento.day):
        idade -= 1
    return idade


def calcular_tmb(sexo: Sexo, peso_kg: float, altura_cm: float, idade: int) -> float:
    """Taxa Metabólica Basal em kcal/dia (Harris-Benedict revisada)."""
    if peso_kg <= 0:
        raise ValueError("peso_kg deve ser maior que zero")
    if altura_cm <= 0:
        raise ValueError("altura_cm deve ser maior que zero")
    if idade <= 0:
        raise ValueError("idade deve ser maior que zero")

    base, c_peso, c_altura, c_idade = _COEFICIENTES_TMB[sexo]
    tmb = base + (c_peso * peso_kg) + (c_altura * altura_cm) - (c_idade * idade)
    return round(tmb, 2)


def calcular_get(tmb: float, nivel: NivelAtividade) -> float:
    """Gasto Energético Total em kcal/dia: TMB ajustada pelo nível de atividade física."""
    return round(tmb * _FATORES_ATIVIDADE[nivel], 2)


def calcular_meta_calorica(get: float, objetivo: TipoObjetivo) -> float:
    """Meta calórica diária: déficit para emagrecer, neutro para manter, superávit para ganhar massa."""
    return round(get * _AJUSTES_OBJETIVO[objetivo], 2)
