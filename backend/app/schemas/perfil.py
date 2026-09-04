from pydantic import BaseModel, ConfigDict, Field

from app.domain.enums import NivelAtividade, TipoObjetivo


class PerfilCalcularEntrada(BaseModel):
    """Corpo do POST /api/perfil/calcular.

    Faixa/formato fora do especificado (enum invalido, peso fora da faixa) vira
    422 do Pydantic -- detail em LISTA, diferente do 422 de dominio (detail
    STRING) que vem de app.services.perfil_service.
    """

    usuario_id: int = Field(gt=0)
    peso_kg: float = Field(gt=20, lt=400)
    nivel_atividade: NivelAtividade
    objetivo: TipoObjetivo
    peso_meta_kg: float | None = Field(default=None, gt=20, lt=400)


class MacrosLidos(BaseModel):
    """proteina/carboidrato/gordura, nessa ordem -- carboidrato no meio.

    from_attributes=True: aceita tanto a linha ORM Macronutrientes quanto a
    dataclass Macros de app.domain.resultados (mesmos nomes de atributo). T9
    deve reusar este schema para o consumo diario em vez de redeclarar os
    tres campos.
    """

    model_config = ConfigDict(from_attributes=True)

    proteina_g: float
    carboidrato_g: float
    gordura_g: float


class PerfilCalculado(BaseModel):
    """response_model do POST /api/perfil/calcular.

    Nao devolve tipo/peso_kg/peso_meta_kg/data_inicio -- quem precisa desses
    campos le o Objetivo via perfil_service.objetivo_ativo().
    """

    objetivo_id: int
    usuario_id: int
    idade: int
    tmb_kcal: float
    get_kcal: float
    meta_kcal: float
    macros: MacrosLidos
