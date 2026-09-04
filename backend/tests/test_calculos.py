from datetime import date

import pytest

from app.domain.enums import NivelAtividade, Sexo, TipoObjetivo
from app.domain.erros import RegraDeNegocioError
from app.services.calculos import (
    calcular_get,
    calcular_idade,
    calcular_macros,
    calcular_meta_calorica,
    calcular_perfil,
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


def test_calcular_macros_emagrecer_bate_com_referencia():
    macros = calcular_macros(2333.70, peso_kg=80, objetivo=TipoObjetivo.EMAGRECER)
    assert macros.proteina_g == pytest.approx(144.00, abs=0.01)
    assert macros.carboidrato_g == pytest.approx(293.57, abs=0.01)
    # 2333.70*0.25/9 = 64.82499999999999 em float -> round(x,2) = 64.82, nao 64.83
    # (o literal do plano foi conta de cabeca supondo arredondamento meio-para-cima;
    # a formula com round(x, 2) e a autoritativa - ver Global Constraint do plano).
    assert macros.gordura_g == pytest.approx(64.82, abs=0.01)


def test_calcular_macros_ganhar_massa_bate_com_referencia():
    macros = calcular_macros(3354.70, peso_kg=80, objetivo=TipoObjetivo.GANHAR_MASSA)
    assert macros.proteina_g == pytest.approx(160.00, abs=0.01)
    assert macros.gordura_g == pytest.approx(93.19, abs=0.01)
    assert macros.carboidrato_g == pytest.approx(469.01, abs=0.01)


def test_macros_somam_a_meta_calorica_com_folga():
    meta = 2333.70
    macros = calcular_macros(meta, peso_kg=80, objetivo=TipoObjetivo.EMAGRECER)
    soma_kcal = (
        macros.proteina_g * 4 + macros.carboidrato_g * 4 + macros.gordura_g * 9
    )
    # cada campo vem do seu proprio round(x, 2) independente, entao a soma nao bate
    # exato com a meta - folga generosa por causa disso, nao um erro de calculo.
    assert soma_kcal == pytest.approx(meta, abs=0.5)


def test_calcular_macros_estoura_regra_de_negocio_quando_meta_insuficiente():
    # meta 1200 kcal, peso 150 kg, EMAGRECER: proteina 1080 kcal + gordura 300 kcal
    # ja excedem a meta -> nao sobra kcal para carboidrato.
    with pytest.raises(RegraDeNegocioError):
        calcular_macros(1200, peso_kg=150, objetivo=TipoObjetivo.EMAGRECER)


def test_calcular_perfil_orquestra_tudo_encadeado():
    # os valores esperados vem ENCADEANDO calcular_idade -> calcular_tmb ->
    # calcular_get -> calcular_meta_calorica -> calcular_macros, nunca da formula
    # bruta recalculada a mao (o encadeamento arredonda em cada passo).
    resultado = calcular_perfil(
        sexo=Sexo.MASCULINO,
        data_nascimento=date(2001, 1, 1),
        peso_kg=80,
        altura_cm=180,
        nivel=NivelAtividade.MODERADO,
        objetivo=TipoObjetivo.EMAGRECER,
        hoje=date(2026, 6, 1),
    )
    assert resultado.idade == 25
    assert resultado.tmb_kcal == pytest.approx(1882.02, abs=0.01)
    assert resultado.get_kcal == pytest.approx(2917.13, abs=0.01)
    assert resultado.meta_kcal == pytest.approx(2333.70, abs=0.01)
    assert resultado.macros.proteina_g == pytest.approx(144.00, abs=0.01)
    assert resultado.macros.carboidrato_g == pytest.approx(293.57, abs=0.01)
    assert resultado.macros.gordura_g == pytest.approx(64.82, abs=0.01)
