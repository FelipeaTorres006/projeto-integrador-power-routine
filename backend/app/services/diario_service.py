from datetime import date

from sqlalchemy import and_, select
from sqlalchemy.orm import Session

from app.domain.enums import TipoMacro
from app.domain.erros import RegraDeNegocioError
from app.models import Macronutrientes, RegistroDiario
from app.schemas.diario import ComparativoDia, DiarioRegistroEntrada, DiarioResumo
from app.schemas.perfil import MacrosLidos
from app.services import perfil_service, usuario_service


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


_ZERADO = MacrosLidos(proteina_g=0, carboidrato_g=0, gordura_g=0)


def resumo(db: Session, usuario_id: int) -> DiarioResumo:
    """Compara, dia a dia, o consumo registrado com a meta VIGENTE do usuario
    -- nao com a meta que valia em cada dia. `registro_diario` nao guarda
    `objetivo_id` (decisao de T6); trocar de objetivo (novo POST /api/perfil/
    calcular) reescreve a nota de TODO o historico ja registrado, porque a
    comparacao sempre le o objetivo ativo de agora.

    So le, nunca grava, nunca chama flush.

    O comparativo inteiro sai de 4 SELECTs (usuario, objetivo ativo, macros da
    meta, o join dos dias) e esse numero e CONSTANTE, independente de quantos
    dias o usuario tem -- e essa invariancia que sustenta a decisao de
    modelagem da secao 18.1 (meta e consumo numa unica tabela, discriminados
    por `tipo`): o comparativo sai de UMA consulta, sem UNION e sem segunda
    tabela.
    """
    usuario = usuario_service.buscar_usuario(db, usuario_id)
    objetivo = perfil_service.objetivo_ativo(db, usuario.id)

    if objetivo.meta_kcal <= 0:
        raise RegraDeNegocioError(
            f"objetivo {objetivo.id} tem meta_kcal invalida ({objetivo.meta_kcal}); "
            "nao ha como comparar consumo contra uma meta zero ou negativa"
        )

    macros_meta_row = db.scalar(
        select(Macronutrientes).where(
            Macronutrientes.objetivo_id == objetivo.id, Macronutrientes.tipo == TipoMacro.META
        )
    )
    if macros_meta_row is None:
        raise RegraDeNegocioError(
            f"objetivo {objetivo.id} nao tem macros de meta gravados; "
            "o comparativo ficaria incoerente com macros_meta zerado ao lado de um meta_kcal real"
        )
    macros_meta = MacrosLidos.model_validate(macros_meta_row)

    # F4: o predicado `tipo == CONSUMO` fica no ON, nunca no WHERE -- no WHERE
    # o LEFT OUTER JOIN vira INNER JOIN na pratica e um dia sem linha de
    # consumo desaparece da lista em vez de aparecer zerado.
    linhas = db.execute(
        select(RegistroDiario, Macronutrientes)
        .outerjoin(
            Macronutrientes,
            and_(
                Macronutrientes.registro_diario_id == RegistroDiario.id,
                Macronutrientes.tipo == TipoMacro.CONSUMO,
            ),
        )
        .where(RegistroDiario.usuario_id == usuario.id)
        .order_by(RegistroDiario.data.desc())
    ).all()

    registros = [
        ComparativoDia(
            data=registro_dia.data,
            peso_kg=registro_dia.peso_kg,
            consumido_kcal=registro_dia.calorias_kcal,
            meta_kcal=objetivo.meta_kcal,
            diferenca_kcal=round(registro_dia.calorias_kcal - objetivo.meta_kcal, 2),
            aderencia_percentual=round(
                registro_dia.calorias_kcal / objetivo.meta_kcal * 100, 2
            ),
            macros_consumidos=MacrosLidos.model_validate(consumo) if consumo else _ZERADO,
            macros_meta=macros_meta,
        )
        for registro_dia, consumo in linhas
    ]

    return DiarioResumo(
        usuario_id=usuario.id,
        objetivo=objetivo.tipo,
        meta_kcal=objetivo.meta_kcal,
        registros=registros,
    )
