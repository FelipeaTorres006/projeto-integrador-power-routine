from datetime import date

from pydantic import BaseModel, ConfigDict, EmailStr, Field, field_validator

from app.domain.enums import Sexo
from app.services.calculos import calcular_idade

# F2: piso so tecnico -- impede idade == 0 chegar em calcular_tmb (T8) e estourar
# ValueError sem handler (500). D1 aberto no PR: manter em 1, ou usar um piso de
# politica (ex.: 14)?
IDADE_MINIMA_ANOS = 1


class UsuarioCriar(BaseModel):
    """Primeira camada de validacao: formato e faixa, antes de qualquer regra de negocio."""

    nome: str = Field(min_length=2, max_length=120)
    email: EmailStr
    sexo: Sexo
    data_nascimento: date
    altura_cm: float = Field(gt=50, lt=250)

    @field_validator("data_nascimento")
    @classmethod
    def validar_data_nascimento(cls, valor: date) -> date:
        hoje = date.today()
        if valor >= hoje:
            raise ValueError("data_nascimento deve estar no passado")
        if calcular_idade(valor, hoje) < IDADE_MINIMA_ANOS:
            raise ValueError(f"idade minima para cadastro e {IDADE_MINIMA_ANOS} ano(s)")
        return valor


class UsuarioLido(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    nome: str
    email: EmailStr
    sexo: Sexo
    data_nascimento: date
    altura_cm: float


class UsuarioDetalhe(UsuarioLido):
    idade: int
