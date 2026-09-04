from datetime import date

import pytest
from sqlalchemy.exc import IntegrityError

from app.domain.enums import Sexo
from app.models import Usuario


def _usuario(**overrides):
    dados = dict(
        nome="Felipe",
        email="felipe@exemplo.com",
        sexo=Sexo.MASCULINO,
        data_nascimento=date(2001, 1, 1),
        altura_cm=180,
    )
    dados.update(overrides)
    return Usuario(**dados)


def test_persiste_e_recupera_usuario(db):
    db.add(_usuario())
    db.commit()

    usuario = db.query(Usuario).filter_by(email="felipe@exemplo.com").one()
    assert usuario.id is not None
    assert usuario.sexo is Sexo.MASCULINO


def test_email_precisa_ser_unico(db):
    db.add(_usuario())
    db.add(_usuario())
    with pytest.raises(IntegrityError):
        db.commit()


def test_altura_fora_da_faixa_viola_check(db):
    db.add(_usuario(email="alturainvalida@exemplo.com", altura_cm=0))
    with pytest.raises(IntegrityError):
        db.commit()
