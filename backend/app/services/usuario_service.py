from datetime import date

from sqlalchemy.orm import Session

from app.domain.erros import RecursoNaoEncontradoError
from app.models import Usuario
from app.schemas.usuario import UsuarioCriar
from app.services.calculos import calcular_idade


def criar_usuario(db: Session, dados: UsuarioCriar) -> Usuario:
    usuario = Usuario(**dados.model_dump())
    db.add(usuario)
    db.flush()  # F1: obtem o id E faz a violacao de UNIQUE acontecer aqui, nao no commit do get_db
    return usuario


def buscar_usuario(db: Session, usuario_id: int) -> Usuario:
    usuario = db.get(Usuario, usuario_id)
    if usuario is None:
        raise RecursoNaoEncontradoError(f"usuario {usuario_id} nao encontrado")
    return usuario


def idade_do_usuario(usuario: Usuario, hoje: date | None = None) -> int:
    return calcular_idade(usuario.data_nascimento, hoje or date.today())
