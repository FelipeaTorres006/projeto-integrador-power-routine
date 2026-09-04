"""Regras de negócio do Power Routine.

Funções puras: recebem números, devolvem números. Não importam FastAPI nem
SQLAlchemy — é isso que permite testá-las sem banco e sem servidor.
"""

from datetime import date

from app.domain.enums import NivelAtividade, Sexo, TipoObjetivo
from app.domain.erros import RegraDeNegocioError
from app.domain.resultados import Macros, ResultadoPerfil

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

# Densidade energética por grama de macronutriente (kcal/g) — públicas: T8/T9
# comparam consumo contra meta e reusam esses números em vez de repetir 4/4/9.
KCAL_POR_GRAMA_PROTEINA = 4
KCAL_POR_GRAMA_CARBOIDRATO = 4
KCAL_POR_GRAMA_GORDURA = 9

# Gramas de proteína por kg de peso corporal, por objetivo — regra de negócio.
_PROTEINA_G_POR_KG = {
    TipoObjetivo.EMAGRECER: 1.8,
    TipoObjetivo.MANTER: 1.8,
    TipoObjetivo.GANHAR_MASSA: 2.0,
}

# Percentual da meta calórica reservado a gordura — regra de negócio fixa.
_PERCENTUAL_GORDURA = 0.25


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


def calcular_macros(meta_kcal: float, peso_kg: float, objetivo: TipoObjetivo) -> Macros:
    """Alvo diário de macronutrientes: proteína e gordura fixas primeiro, carboidrato absorve o resto."""
    proteina_g = round(peso_kg * _PROTEINA_G_POR_KG[objetivo], 2)
    gordura_kcal = meta_kcal * _PERCENTUAL_GORDURA
    gordura_g = round(gordura_kcal / KCAL_POR_GRAMA_GORDURA, 2)

    carboidrato_kcal = meta_kcal - (proteina_g * KCAL_POR_GRAMA_PROTEINA) - gordura_kcal
    if carboidrato_kcal < 0:
        raise RegraDeNegocioError(
            "meta calorica insuficiente: proteina e gordura ja excedem as "
            f"calorias disponiveis ({meta_kcal} kcal para {peso_kg} kg)"
        )
    carboidrato_g = round(carboidrato_kcal / KCAL_POR_GRAMA_CARBOIDRATO, 2)

    return Macros(proteina_g=proteina_g, carboidrato_g=carboidrato_g, gordura_g=gordura_g)


def calcular_perfil(
    sexo: Sexo,
    data_nascimento: date,
    peso_kg: float,
    altura_cm: float,
    nivel: NivelAtividade,
    objetivo: TipoObjetivo,
    hoje: date,
) -> ResultadoPerfil:
    """Orquestra idade -> TMB -> GET -> meta calórica -> macros num único resultado."""
    idade = calcular_idade(data_nascimento, hoje)
    tmb_kcal = calcular_tmb(sexo, peso_kg=peso_kg, altura_cm=altura_cm, idade=idade)
    get_kcal = calcular_get(tmb_kcal, nivel)
    meta_kcal = calcular_meta_calorica(get_kcal, objetivo)
    macros = calcular_macros(meta_kcal, peso_kg=peso_kg, objetivo=objetivo)

    return ResultadoPerfil(
        idade=idade,
        tmb_kcal=tmb_kcal,
        get_kcal=get_kcal,
        meta_kcal=meta_kcal,
        macros=macros,
    )
