from datetime import date

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.domain.enums import TipoMacro
from app.domain.erros import RecursoNaoEncontradoError
from app.models import Macronutrientes, Objetivo
from app.schemas.perfil import PerfilCalcularEntrada
from app.services import usuario_service
from app.services.calculos import calcular_perfil


def _objetivo_ativo_ou_none(db: Session, usuario_id: int) -> Objetivo | None:
    """Query unica reusada por `objetivo_ativo` (que trata ausencia como erro) e
    por `calcular_e_salvar` (para quem ausencia e o caso normal: primeiro
    calculo do usuario). Evita duas copias do mesmo filtro divergirem.
    """
    return db.scalar(
        select(Objetivo).where(Objetivo.usuario_id == usuario_id, Objetivo.ativo.is_(True))
    )


def objetivo_ativo(db: Session, usuario_id: int) -> Objetivo:
    """O unico Objetivo com ativo=True do usuario -- a meta vigente que T10 le.

    O indice parcial `ix_objetivo_um_ativo_por_usuario` garante que existe no
    maximo um. Nao recalcula nada: tmb/get/meta sao o snapshot prescrito no
    momento do calculo (regra de T6), nunca um numero derivado na leitura.
    """
    objetivo = _objetivo_ativo_ou_none(db, usuario_id)
    if objetivo is None:
        raise RecursoNaoEncontradoError(
            f"usuario {usuario_id} nao possui objetivo ativo; chame POST /api/perfil/calcular"
        )
    return objetivo


def calcular_e_salvar(
    db: Session, dados: PerfilCalcularEntrada, hoje: date | None = None
) -> tuple[Objetivo, Macronutrientes, int]:
    """Calcula o perfil e o congela como o novo objetivo ativo do usuario.

    Ordem obrigatoria (F7 do spec de T8) -- carga util, nao estilo: calcular
    ANTES de qualquer escrita. Um 422 de dominio (calcular_macros estourando a
    meta calorica) tem que acontecer sem tocar o banco; se o calculo rodasse
    depois de desativar o objetivo anterior, esse 422 deixaria o usuario sem
    NENHUM objetivo ativo ate o proximo calculo dar certo.

    Nenhum db.commit() aqui -- quem grava a transacao e o get_db, uma vez so.
    O db.flush() intermediario entre desativar o anterior e inserir o novo nao
    e estritamente necessario (o unit of work do SQLAlchemy ja emite UPDATEs
    antes de INSERTs do mesmo mapper), mas nao dependemos desse detalhe
    interno -- custa uma ida ao banco e torna a ordem explicita.
    """
    usuario = usuario_service.buscar_usuario(db, dados.usuario_id)

    hoje_efetivo = hoje or date.today()
    resultado = calcular_perfil(
        sexo=usuario.sexo,
        data_nascimento=usuario.data_nascimento,
        peso_kg=dados.peso_kg,
        altura_cm=usuario.altura_cm,
        nivel=dados.nivel_atividade,
        objetivo=dados.objetivo,
        hoje=hoje_efetivo,
    )

    anterior = _objetivo_ativo_ou_none(db, dados.usuario_id)
    if anterior is not None:
        anterior.ativo = False
        db.flush()

    objetivo = Objetivo(
        usuario_id=dados.usuario_id,
        tipo=dados.objetivo,
        nivel_atividade=dados.nivel_atividade,
        peso_kg=dados.peso_kg,
        peso_meta_kg=dados.peso_meta_kg,
        tmb_kcal=resultado.tmb_kcal,
        get_kcal=resultado.get_kcal,
        meta_kcal=resultado.meta_kcal,
        data_inicio=hoje_efetivo,
        ativo=True,
    )
    db.add(objetivo)
    db.flush()  # F1/H7: obtem objetivo.id E antecipa a violacao de CHECK para aqui,
    # nao para o commit do get_db (onde o Starlette perderia a resposta 409/422).

    macros = Macronutrientes(
        tipo=TipoMacro.META,
        objetivo_id=objetivo.id,
        proteina_g=resultado.macros.proteina_g,
        carboidrato_g=resultado.macros.carboidrato_g,
        gordura_g=resultado.macros.gordura_g,
    )
    db.add(macros)
    db.flush()

    return objetivo, macros, resultado.idade
