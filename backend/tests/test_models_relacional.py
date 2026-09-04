from datetime import date

import pytest
from sqlalchemy.exc import IntegrityError

from app.domain.enums import NivelAtividade, Sexo, TipoMacro, TipoObjetivo
from app.models import Macronutrientes, Objetivo, RegistroDiario, Usuario


@pytest.fixture
def usuario(db):
    u = Usuario(
        nome="Felipe",
        email="felipe@exemplo.com",
        sexo=Sexo.MASCULINO,
        data_nascimento=date(2001, 1, 1),
        altura_cm=180,
    )
    db.add(u)
    db.commit()
    return u


def novo_objetivo(usuario_id: int, ativo: bool = True) -> Objetivo:
    return Objetivo(
        usuario_id=usuario_id,
        tipo=TipoObjetivo.EMAGRECER,
        nivel_atividade=NivelAtividade.MODERADO,
        peso_kg=80,
        peso_meta_kg=72,
        tmb_kcal=1882.02,
        get_kcal=2917.13,
        meta_kcal=2333.70,
        data_inicio=date(2026, 6, 1),
        ativo=ativo,
    )


def test_apenas_um_objetivo_ativo_por_usuario(db, usuario):
    db.add(novo_objetivo(usuario.id))
    db.commit()
    db.add(novo_objetivo(usuario.id))
    with pytest.raises(IntegrityError):
        db.commit()


def test_objetivo_inativo_nao_conflita(db, usuario):
    db.add(novo_objetivo(usuario.id, ativo=True))
    db.add(novo_objetivo(usuario.id, ativo=False))
    db.add(novo_objetivo(usuario.id, ativo=False))
    db.commit()
    assert db.query(Objetivo).count() == 3


def test_um_registro_diario_por_dia(db, usuario):
    for _ in range(2):
        db.add(RegistroDiario(
            usuario_id=usuario.id, data=date(2026, 6, 1), peso_kg=80, calorias_kcal=2300
        ))
    with pytest.raises(IntegrityError):
        db.commit()


def test_macro_meta_exige_objetivo(db, usuario):
    objetivo = novo_objetivo(usuario.id)
    db.add(objetivo)
    db.flush()
    db.add(Macronutrientes(
        tipo=TipoMacro.META, objetivo_id=objetivo.id,
        proteina_g=144, carboidrato_g=293.57, gordura_g=64.83,
    ))
    db.commit()
    assert db.query(Macronutrientes).count() == 1


def test_macro_meta_com_registro_diario_viola_o_discriminador(db, usuario):
    objetivo = novo_objetivo(usuario.id)
    registro = RegistroDiario(
        usuario_id=usuario.id, data=date(2026, 6, 1), peso_kg=80, calorias_kcal=2300
    )
    db.add_all([objetivo, registro])
    db.flush()
    db.add(Macronutrientes(
        tipo=TipoMacro.META, objetivo_id=objetivo.id, registro_diario_id=registro.id,
        proteina_g=144, carboidrato_g=293.57, gordura_g=64.83,
    ))
    with pytest.raises(IntegrityError):
        db.commit()


def test_macro_consumo_sem_registro_diario_viola_o_discriminador(db, usuario):
    db.add(Macronutrientes(
        tipo=TipoMacro.CONSUMO, proteina_g=140, carboidrato_g=280, gordura_g=60,
    ))
    with pytest.raises(IntegrityError):
        db.commit()


# --- F7: a regra 1:1 com o dono (spec secao 4) nao tinha teste nenhum no plano ---

def test_uma_unica_meta_por_objetivo(db, usuario):
    objetivo = novo_objetivo(usuario.id)
    db.add(objetivo)
    db.flush()
    db.add(Macronutrientes(
        tipo=TipoMacro.META, objetivo_id=objetivo.id,
        proteina_g=144, carboidrato_g=293.57, gordura_g=64.83,
    ))
    db.commit()
    db.add(Macronutrientes(
        tipo=TipoMacro.META, objetivo_id=objetivo.id,
        proteina_g=150, carboidrato_g=300, gordura_g=70,
    ))
    with pytest.raises(IntegrityError):
        db.commit()


def test_um_unico_consumo_por_registro(db, usuario):
    registro = RegistroDiario(
        usuario_id=usuario.id, data=date(2026, 6, 1), peso_kg=80, calorias_kcal=2300
    )
    db.add(registro)
    db.flush()
    db.add(Macronutrientes(
        tipo=TipoMacro.CONSUMO, registro_diario_id=registro.id,
        proteina_g=140, carboidrato_g=280, gordura_g=60,
    ))
    db.commit()
    db.add(Macronutrientes(
        tipo=TipoMacro.CONSUMO, registro_diario_id=registro.id,
        proteina_g=145, carboidrato_g=285, gordura_g=65,
    ))
    with pytest.raises(IntegrityError):
        db.commit()


# --- fluxo que T8 usa: desativar o objetivo antigo e inserir o novo ativo no mesmo flush ---

def test_desativar_objetivo_antigo_e_inserir_novo_ativo_no_mesmo_flush(db, usuario):
    db.add(novo_objetivo(usuario.id, ativo=True))
    db.commit()

    db.query(Objetivo).filter(
        Objetivo.usuario_id == usuario.id, Objetivo.ativo.is_(True)
    ).update({"ativo": False})
    db.add(novo_objetivo(usuario.id, ativo=True))
    db.commit()

    ativos = db.query(Objetivo).filter(
        Objetivo.usuario_id == usuario.id, Objetivo.ativo.is_(True)
    ).count()
    assert ativos == 1
    assert db.query(Objetivo).count() == 2
