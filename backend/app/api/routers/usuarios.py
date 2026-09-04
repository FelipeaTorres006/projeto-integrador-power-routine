from fastapi import APIRouter, Depends, status
from sqlalchemy.orm import Session

from app.db.session import get_db
from app.schemas.usuario import UsuarioCriar, UsuarioDetalhe, UsuarioLido
from app.services import usuario_service

router = APIRouter(prefix="/usuarios", tags=["usuarios"])


@router.post("", response_model=UsuarioLido, status_code=status.HTTP_201_CREATED)
def criar(dados: UsuarioCriar, db: Session = Depends(get_db)) -> UsuarioLido:
    """Cadastra um usuario. Sexo e data de nascimento sao obrigatorios para o calculo de TMB.

    F4: rota canonica sem barra final -- POST /api/usuarios/ (com barra) devolve
    307, so /api/usuarios (sem barra) responde 201.
    """
    return UsuarioLido.model_validate(usuario_service.criar_usuario(db, dados))


@router.get("/{usuario_id}", response_model=UsuarioDetalhe)
def ler(usuario_id: int, db: Session = Depends(get_db)) -> UsuarioDetalhe:
    """Retorna o usuario com a idade derivada da data de nascimento."""
    usuario = usuario_service.buscar_usuario(db, usuario_id)
    return UsuarioDetalhe(
        **UsuarioLido.model_validate(usuario).model_dump(),
        idade=usuario_service.idade_do_usuario(usuario),
    )
