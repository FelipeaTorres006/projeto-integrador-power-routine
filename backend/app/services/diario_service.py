from datetime import date

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.domain.enums import TipoMacro
from app.models import Macronutrientes, RegistroDiario
from app.schemas.diario import DiarioRegistroEntrada
from app.services import usuario_service


def _registro_do_dia(db: Session, usuario_id: int, dia: date) -> RegistroDiario | None:
    """Isolado para o F10 ser testavel: um teste pode fazer esta funcao mentir
    (retornar None mesmo com a linha ja gravada) e provar que a corrida vira
    409 de verdade, e nao um DELETE+INSERT ou um 500.
    """
    return db.scalar(
        select(RegistroDiario).where(
            RegistroDiario.usuario_id == usuario_id, RegistroDiario.data == dia
        )
    )


def _consumo_do_registro(db: Session, registro_id: int) -> Macronutrientes | None:
    return db.scalar(
        select(Macronutrientes).where(
            Macronutrientes.registro_diario_id == registro_id,
            Macronutrientes.tipo == TipoMacro.CONSUMO,
        )
    )


def registrar(
    db: Session, dados: DiarioRegistroEntrada
) -> tuple[RegistroDiario, Macronutrientes]:
    """Grava o dia do usuario. Idempotente por (usuario_id, data): regrava, nao
    duplica -- o UPDATE reusa a MESMA linha de registro_diario e a MESMA linha
    de macronutrientes tipo=consumo (id inalterado entre regravacoes).

    A regravacao e substituicao TOTAL do dia, nao merge: um campo omitido no
    corpo volta ao default (observacoes vira None). O frontend precisa mandar
    o dia inteiro sempre.

    NAO exige objetivo ativo: um usuario que nunca chamou POST /api/perfil/
    calcular grava o dia normalmente. Quem exige objetivo ativo e o GET de T10.

    A alternativa a este upsert -- deixar o UNIQUE estourar e devolver 409 --
    obrigaria o frontend a saber se o dia ja existe antes de enviar; regravar
    e o comportamento util aqui.

    db.flush() apos cada gravacao (regra dura de T7, medida NESTE endpoint):
    sem ele, uma corrida perdida entre duas requisicoes concorrentes so
    estouraria o UNIQUE no commit do get_db, com a resposta ja iniciada -- o
    409 viraria erro de servidor. Nunca db.commit() aqui: quem comita e o
    get_db, uma vez so.
    """
    usuario = usuario_service.buscar_usuario(db, dados.usuario_id)

    registro = _registro_do_dia(db, usuario.id, dados.data)
    if registro is None:
        registro = RegistroDiario(usuario_id=usuario.id, data=dados.data)
        db.add(registro)

    registro.peso_kg = dados.peso_kg
    registro.calorias_kcal = dados.calorias_kcal
    registro.observacoes = dados.observacoes
    db.flush()

    macros = _consumo_do_registro(db, registro.id)
    if macros is None:
        macros = Macronutrientes(tipo=TipoMacro.CONSUMO, registro_diario_id=registro.id)
        db.add(macros)

    macros.proteina_g = dados.proteina_g
    macros.carboidrato_g = dados.carboidrato_g
    macros.gordura_g = dados.gordura_g
    db.flush()

    return registro, macros
