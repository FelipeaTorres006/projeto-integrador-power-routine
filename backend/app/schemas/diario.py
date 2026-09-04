from datetime import date

from pydantic import BaseModel, Field, field_validator

from app.domain.enums import TipoObjetivo
from app.schemas.perfil import MacrosLidos


class DiarioRegistroEntrada(BaseModel):
    """Corpo de POST /api/diario/registro -- o dia INTEIRO do usuario.

    A gravacao e substituicao total (F6 do spec de T9): um campo omitido aqui
    volta ao default na regravacao (observacoes vira None). O frontend precisa
    mandar o dia inteiro sempre, nao so o que mudou.
    """

    usuario_id: int = Field(gt=0)
    data: date
    peso_kg: float = Field(gt=20, lt=400)
    calorias_kcal: float = Field(ge=0, le=15000)
    proteina_g: float = Field(ge=0, le=1000)
    carboidrato_g: float = Field(ge=0, le=2000)
    gordura_g: float = Field(ge=0, le=1000)
    observacoes: str | None = Field(default=None, max_length=500)

    @field_validator("data")
    @classmethod
    def validar_data(cls, valor: date) -> date:
        """Barreira SO do Pydantic -- nao ha CHECK em registro_diario.data no
        banco. Hoje e aceito, amanha e 422 (com `detail` como lista, formato
        padrao de erro de validacao do Pydantic/FastAPI).
        """
        if valor > date.today():
            raise ValueError("nao e possivel registrar um dia no futuro")
        return valor


class RegistroLido(BaseModel):
    """Response de POST /api/diario/registro.

    Sem `ConfigDict(from_attributes=True)` de proposito: `macros` mora em outra
    tabela (Macronutrientes) e nenhum model tem `relationship()`, entao
    `model_validate(<linha ORM>)` levantaria. O router monta este schema campo
    a campo -- T10 tem que fazer o mesmo ao reusar este schema.
    """

    id: int
    usuario_id: int
    data: date
    peso_kg: float
    calorias_kcal: float
    observacoes: str | None
    macros: MacrosLidos


class ComparativoDia(BaseModel):
    """Um dia registrado, com o consumo ao lado da meta VIGENTE do usuario
    (nao da meta que valia naquele dia -- ver docstring de
    `diario_service.resumo`).
    """

    data: date
    peso_kg: float
    consumido_kcal: float
    meta_kcal: float
    diferenca_kcal: float
    aderencia_percentual: float
    macros_consumidos: MacrosLidos
    macros_meta: MacrosLidos


class DiarioResumo(BaseModel):
    """Response de GET /api/diario/{usuario_id}: o comparativo meta vs.
    consumo, do dia mais recente para o mais antigo.
    """

    usuario_id: int
    objetivo: TipoObjetivo
    meta_kcal: float
    registros: list[ComparativoDia]
