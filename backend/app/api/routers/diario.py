from fastapi import APIRouter, Depends, status
from sqlalchemy.orm import Session

from app.db.session import get_db
from app.schemas.diario import DiarioRegistroEntrada, RegistroLido
from app.schemas.perfil import MacrosLidos
from app.services import diario_service

router = APIRouter(prefix="/diario", tags=["diario"])


@router.post("/registro", response_model=RegistroLido, status_code=status.HTTP_201_CREATED)
def registrar(dados: DiarioRegistroEntrada, db: Session = Depends(get_db)) -> RegistroLido:
    """Registra (ou regrava) o dia do usuario: peso, calorias e macros consumidos.

    Sem try/except: app.api.handlers.registrar_handlers e o unico lugar que
    traduz excecao de dominio em resposta HTTP.
    """
    registro, macros = diario_service.registrar(db, dados)
    return RegistroLido(
        id=registro.id,
        usuario_id=registro.usuario_id,
        data=registro.data,
        peso_kg=registro.peso_kg,
        calorias_kcal=registro.calorias_kcal,
        observacoes=registro.observacoes,
        macros=MacrosLidos.model_validate(macros),
    )
