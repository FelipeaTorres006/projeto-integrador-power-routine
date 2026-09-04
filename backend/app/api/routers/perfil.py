from fastapi import APIRouter, Depends, status
from sqlalchemy.orm import Session

from app.db.session import get_db
from app.schemas.perfil import MacrosLidos, PerfilCalcularEntrada, PerfilCalculado
from app.services import perfil_service

router = APIRouter(prefix="/perfil", tags=["perfil"])


@router.post("/calcular", response_model=PerfilCalculado, status_code=status.HTTP_201_CREATED)
def calcular(dados: PerfilCalcularEntrada, db: Session = Depends(get_db)) -> PerfilCalculado:
    """Calcula TMB/GET/meta calorica/macros e congela o resultado como o novo
    objetivo ativo do usuario. Recalcular nao apaga historico: o objetivo
    anterior e apenas desativado.

    Sem try/except: app.api.handlers.registrar_handlers e o unico lugar que
    traduz excecao de dominio em resposta HTTP.
    """
    objetivo, macros, idade = perfil_service.calcular_e_salvar(db, dados)
    return PerfilCalculado(
        objetivo_id=objetivo.id,
        usuario_id=objetivo.usuario_id,
        idade=idade,
        tmb_kcal=objetivo.tmb_kcal,
        get_kcal=objetivo.get_kcal,
        meta_kcal=objetivo.meta_kcal,
        macros=MacrosLidos.model_validate(macros),
    )
