from datetime import date

import pytest

from app.domain.enums import Sexo
from app.services.calculos import calcular_idade, calcular_tmb


def test_calcular_idade_antes_do_aniversario():
    assert calcular_idade(date(2000, 12, 31), hoje=date(2026, 6, 1)) == 25


def test_calcular_idade_depois_do_aniversario():
    assert calcular_idade(date(2000, 1, 1), hoje=date(2026, 6, 1)) == 26


def test_calcular_idade_no_dia_do_aniversario():
    assert calcular_idade(date(2000, 6, 1), hoje=date(2026, 6, 1)) == 26


def test_tmb_masculino():
    # 88.362 + 13.397*80 + 4.799*180 - 5.677*25
    tmb = calcular_tmb(Sexo.MASCULINO, peso_kg=80, altura_cm=180, idade=25)
    assert tmb == pytest.approx(1882.02, abs=0.01)


def test_tmb_feminino():
    # 447.593 + 9.247*60 + 3.098*165 - 4.330*30
    tmb = calcular_tmb(Sexo.FEMININO, peso_kg=60, altura_cm=165, idade=30)
    assert tmb == pytest.approx(1383.68, abs=0.01)


def test_tmb_rejeita_peso_invalido():
    with pytest.raises(ValueError):
        calcular_tmb(Sexo.MASCULINO, peso_kg=0, altura_cm=180, idade=25)
