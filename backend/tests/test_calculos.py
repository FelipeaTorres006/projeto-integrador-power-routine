from datetime import date

import pytest

from app.domain.enums import NivelAtividade, Sexo, TipoObjetivo
from app.services.calculos import (
    calcular_get,
    calcular_idade,
    calcular_meta_calorica,
    calcular_tmb,
)


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


def test_tmb_rejeita_altura_invalida():
    with pytest.raises(ValueError):
        calcular_tmb(Sexo.MASCULINO, peso_kg=80, altura_cm=0, idade=25)


def test_tmb_rejeita_idade_invalida():
    with pytest.raises(ValueError):
        calcular_tmb(Sexo.MASCULINO, peso_kg=80, altura_cm=180, idade=0)


def test_get_sedentario():
    get = calcular_get(1882.02, NivelAtividade.SEDENTARIO)
    assert get == pytest.approx(2258.42, abs=0.01)


def test_get_moderado():
    get = calcular_get(1882.02, NivelAtividade.MODERADO)
    assert get == pytest.approx(2917.13, abs=0.01)


def test_get_muito_intenso():
    get = calcular_get(1882.02, NivelAtividade.MUITO_INTENSO)
    assert get == pytest.approx(3575.84, abs=0.01)


def test_meta_calorica_emagrecer():
    meta = calcular_meta_calorica(2917.13, TipoObjetivo.EMAGRECER)
    assert meta == pytest.approx(2333.70, abs=0.01)


def test_meta_calorica_manter():
    meta = calcular_meta_calorica(2917.13, TipoObjetivo.MANTER)
    assert meta == pytest.approx(2917.13, abs=0.01)


def test_meta_calorica_ganhar_massa():
    meta = calcular_meta_calorica(2917.13, TipoObjetivo.GANHAR_MASSA)
    assert meta == pytest.approx(3354.70, abs=0.01)
