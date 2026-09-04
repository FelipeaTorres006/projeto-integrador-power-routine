from enum import Enum


class Sexo(str, Enum):
    MASCULINO = "masculino"
    FEMININO = "feminino"


class NivelAtividade(str, Enum):
    SEDENTARIO = "sedentario"
    LEVE = "leve"
    MODERADO = "moderado"
    INTENSO = "intenso"
    MUITO_INTENSO = "muito_intenso"


class TipoObjetivo(str, Enum):
    EMAGRECER = "emagrecer"
    MANTER = "manter"
    GANHAR_MASSA = "ganhar_massa"


class TipoMacro(str, Enum):
    """Discriminador da tabela macronutrientes: alvo prescrito vs. consumo real."""

    META = "meta"
    CONSUMO = "consumo"
