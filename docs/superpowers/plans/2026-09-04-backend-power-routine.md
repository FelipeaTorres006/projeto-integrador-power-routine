# Backend Power Routine — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Construir a API do Power Routine que calcula TMB, GET, meta calórica e macronutrientes a partir dos dados corporais do usuário, e persiste perfil e acompanhamento diário em PostgreSQL.

**Architecture:** Três camadas com fronteiras rígidas. `services/calculos.py` contém funções **puras** (só números entra, só números sai — sem banco, sem FastAPI), o que torna as regras de negócio testáveis isoladamente e documentáveis na seção 22.2. Acima dele, services de aplicação orquestram transações; acima deles, routers cuidam só de HTTP. O banco carrega as invariantes em `CHECK`/`UNIQUE`, sem confiar na aplicação.

**Tech Stack:** Python 3.12+, FastAPI, Pydantic v2, SQLAlchemy 2.x, Alembic, PostgreSQL 16+, psycopg 3, pytest, httpx.

**Spec:** `docs/superpowers/specs/2026-09-04-backend-power-routine.md`

---

## Global Constraints

- **Python 3.12 ou 3.13.** Esta máquina tinha 3.14.4, versão muito nova para a qual várias
  wheels binárias (psycopg, SQLAlchemy) ainda podem não existir. Se a instalação falhar,
  é este o motivo — use 3.12.
- **Idioma:** nomes de tabelas, colunas, campos JSON e mensagens de erro em **português**,
  sem acento e em `snake_case` (`peso_kg`, `nivel_atividade`, `data_nascimento`). O frontend
  já é em pt-BR; manter coerência.
- **Todo arredondamento é `round(x, 2)`.** Testes de float usam `pytest.approx(..., abs=0.01)`,
  nunca `==`.
- **Prefixo de rotas:** `/api`. Sem versionamento na URL (escopo acadêmico).
- **Sem autenticação.** `usuario_id` viaja no corpo da requisição.
- **Densidades energéticas:** proteína 4 kcal/g, carboidrato 4 kcal/g, gordura 9 kcal/g.
- **Todo código do backend vive em `backend/`.** O frontend estático permanece intocado na raiz.
- **Um commit por task**, seguindo Conventional Commits (`feat:`, `test:`, `chore:`).

---

## Preparação do ambiente (fazer uma vez, antes da Task 1)

Esta máquina não tinha `pip`, nem PostgreSQL, nem Docker. Em uma máquina Ubuntu limpa:

```bash
sudo apt update
sudo apt install -y python3-venv python3-pip postgresql postgresql-contrib
sudo systemctl enable --now postgresql
```

Criar usuário e bancos (um para desenvolvimento, um para testes):

```bash
sudo -u postgres psql -c "CREATE USER power WITH PASSWORD 'power';"
sudo -u postgres psql -c "CREATE DATABASE power_routine OWNER power;"
sudo -u postgres psql -c "CREATE DATABASE power_routine_test OWNER power;"
```

Conferir que conecta:

```bash
psql "postgresql://power:power@localhost:5432/power_routine" -c "SELECT version();"
```

## Como retomar esta sessão em outro computador

```bash
git clone git@github.com:FelipeaTorres006/projeto-integrador-power-routine.git
cd projeto-integrador-power-routine
git checkout backend/plano-api-fastapi
claude
```

O `CLAUDE.md` na raiz dá o contexto do frontend; esta spec e este plano dão o contexto
do backend. Peça ao Claude: *"leia docs/superpowers/plans/2026-09-04-backend-power-routine.md
e execute a Task N"*.

---

## File Structure

```
backend/
├─ app/
│  ├─ __init__.py
│  ├─ main.py                      # cria o FastAPI, registra routers e handlers
│  ├─ core/
│  │  └─ config.py                 # Settings (DATABASE_URL) via pydantic-settings
│  ├─ db/
│  │  ├─ base.py                   # DeclarativeBase + import de todos os models
│  │  └─ session.py                # engine, SessionLocal, dependência get_db
│  ├─ domain/
│  │  ├─ enums.py                  # Sexo, NivelAtividade, TipoObjetivo, TipoMacro
│  │  ├─ resultados.py             # dataclasses Macros, ResultadoPerfil
│  │  └─ erros.py                  # exceções de domínio
│  ├─ models/                      # SQLAlchemy — uma tabela por arquivo
│  │  ├─ usuario.py
│  │  ├─ objetivo.py
│  │  ├─ registro_diario.py
│  │  └─ macronutrientes.py
│  ├─ schemas/                     # Pydantic — contratos de entrada/saída
│  │  ├─ usuario.py
│  │  ├─ perfil.py
│  │  └─ diario.py
│  ├─ services/
│  │  ├─ calculos.py               # ← REGRAS DE NEGÓCIO PURAS (seção 22.2)
│  │  ├─ usuario_service.py
│  │  ├─ perfil_service.py
│  │  └─ diario_service.py
│  └─ api/
│     └─ routers/
│        ├─ usuarios.py
│        ├─ perfil.py
│        └─ diario.py
├─ alembic/                        # migrations versionadas
├─ tests/
│  ├─ conftest.py
│  ├─ test_calculos.py             # unitários, sem banco
│  ├─ test_usuarios_api.py
│  ├─ test_perfil_api.py
│  └─ test_diario_api.py
├─ alembic.ini
├─ requirements.txt
└─ .env.example
```

**Por que assim:** `services/calculos.py` não importa nada de FastAPI nem de SQLAlchemy.
Essa é a fronteira que sustenta o argumento arquitetural da apresentação — as fórmulas
de Harris-Benedict rodam e são testadas sem que exista banco, servidor ou HTTP.

---

## Interfaces (referência rápida)

Assinaturas que atravessam tasks. Um implementador que só vê a própria task consulta aqui.

```python
# app/domain/enums.py
class Sexo(str, Enum):            MASCULINO="masculino"; FEMININO="feminino"
class NivelAtividade(str, Enum):  SEDENTARIO="sedentario"; LEVE="leve"; MODERADO="moderado"; INTENSO="intenso"; MUITO_INTENSO="muito_intenso"
class TipoObjetivo(str, Enum):    EMAGRECER="emagrecer"; MANTER="manter"; GANHAR_MASSA="ganhar_massa"
class TipoMacro(str, Enum):       META="meta"; CONSUMO="consumo"

# app/domain/resultados.py
@dataclass(frozen=True) class Macros:         proteina_g: float; carboidrato_g: float; gordura_g: float
@dataclass(frozen=True) class ResultadoPerfil: idade:int; tmb_kcal:float; get_kcal:float; meta_kcal:float; macros:Macros

# app/services/calculos.py
def calcular_idade(data_nascimento: date, hoje: date) -> int
def calcular_tmb(sexo: Sexo, peso_kg: float, altura_cm: float, idade: int) -> float
def calcular_get(tmb: float, nivel: NivelAtividade) -> float
def calcular_meta_calorica(get: float, objetivo: TipoObjetivo) -> float
def calcular_macros(meta_kcal: float, peso_kg: float, objetivo: TipoObjetivo) -> Macros
def calcular_perfil(sexo, data_nascimento, peso_kg, altura_cm, nivel, objetivo, hoje) -> ResultadoPerfil
```

---

### Task 1: Bootstrap do projeto backend

**Files:**
- Create: `backend/requirements.txt`, `backend/.env.example`, `backend/app/__init__.py`,
  `backend/app/core/config.py`, `backend/pytest.ini`
- Modify: `.gitignore` (criar na raiz — ainda não existe)
- Test: `backend/tests/test_config.py`

**Interfaces:**
- Consumes: nada (primeira task)
- Produces: `app.core.config.Settings` com atributo `database_url: str`, e a instância
  `settings` importável por todas as tasks seguintes.

- [ ] **Step 1: Criar `.gitignore` na raiz**

```gitignore
# Python
__pycache__/
*.py[cod]
.venv/
venv/
.pytest_cache/

# Ambiente
.env

# Editor
.vscode/
.idea/
```

- [ ] **Step 2: Criar o virtualenv e as dependências**

`backend/requirements.txt`:

```
fastapi>=0.115
uvicorn[standard]>=0.32
sqlalchemy>=2.0
alembic>=1.14
psycopg[binary]>=3.2
pydantic>=2.9
pydantic-settings>=2.6
pytest>=8.3
httpx>=0.27
```

Rodar:

```bash
cd backend
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

Se `pip install` falhar em `psycopg`, é a versão do Python (ver Global Constraints).

- [ ] **Step 3: Criar `backend/.env.example`**

```
DATABASE_URL=postgresql+psycopg://power:power@localhost:5432/power_routine
TEST_DATABASE_URL=postgresql+psycopg://power:power@localhost:5432/power_routine_test
```

Copiar para `.env` (que fica fora do git):

```bash
cp .env.example .env
```

- [ ] **Step 4: Escrever o teste que falha**

`backend/tests/test_config.py`:

```python
from app.core.config import settings


def test_settings_carrega_database_url():
    assert settings.database_url.startswith("postgresql+psycopg://")


def test_settings_carrega_test_database_url():
    assert settings.test_database_url.endswith("_test")
```

- [ ] **Step 5: Rodar o teste e confirmar que falha**

`backend/pytest.ini`:

```ini
[pytest]
pythonpath = .
testpaths = tests
```

Run: `cd backend && pytest tests/test_config.py -v`
Expected: FAIL com `ModuleNotFoundError: No module named 'app.core'`

- [ ] **Step 6: Implementar a configuração**

`backend/app/__init__.py` — arquivo vazio.
`backend/app/core/__init__.py` — arquivo vazio.

`backend/app/core/config.py`:

```python
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Configuração da aplicação, lida de variáveis de ambiente ou do arquivo .env."""

    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    database_url: str
    test_database_url: str


settings = Settings()
```

- [ ] **Step 7: Rodar o teste e confirmar que passa**

Run: `cd backend && pytest -v`
Expected: 2 passed

- [ ] **Step 8: Commit**

```bash
git add .gitignore backend/
git commit -m "chore: bootstrap do projeto backend com FastAPI e configuracao"
```

---

### Task 2: Enums de domínio, idade e TMB (Harris-Benedict)

**Files:**
- Create: `backend/app/domain/__init__.py`, `backend/app/domain/enums.py`,
  `backend/app/domain/erros.py`, `backend/app/services/__init__.py`,
  `backend/app/services/calculos.py`
- Test: `backend/tests/test_calculos.py`

**Interfaces:**
- Consumes: nada de tasks anteriores
- Produces: `Sexo`, `NivelAtividade`, `TipoObjetivo`, `TipoMacro` (enums `str`);
  `RegraDeNegocioError`; `calcular_idade(data_nascimento: date, hoje: date) -> int`;
  `calcular_tmb(sexo: Sexo, peso_kg: float, altura_cm: float, idade: int) -> float`

- [ ] **Step 1: Escrever os testes que falham**

`backend/tests/test_calculos.py`:

```python
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
```

- [ ] **Step 2: Rodar e confirmar que falha**

Run: `cd backend && pytest tests/test_calculos.py -v`
Expected: FAIL com `ModuleNotFoundError: No module named 'app.domain'`

- [ ] **Step 3: Implementar os enums**

`backend/app/domain/__init__.py` — arquivo vazio.

`backend/app/domain/enums.py`:

```python
from enum import Enum


class Sexo(str, Enum):
    MASCULINO = "masculino"
    FEMININO = "feminino"


class NivelAtividade(str, Enum):
    SEDENTARIO = "sedentario"
    LEVE = "leve"
    MODERADO = "moderado"
    INTENSO = "intenso"
    MUITO_INTENSO = "muito_intenso"


class TipoObjetivo(str, Enum):
    EMAGRECER = "emagrecer"
    MANTER = "manter"
    GANHAR_MASSA = "ganhar_massa"


class TipoMacro(str, Enum):
    """Discriminador da tabela macronutrientes: alvo prescrito vs. consumo real."""

    META = "meta"
    CONSUMO = "consumo"
```

- [ ] **Step 4: Implementar os erros de domínio**

`backend/app/domain/erros.py`:

```python
class RegraDeNegocioError(Exception):
    """Violação de uma regra de negócio — vira HTTP 422 na borda da API."""


class RecursoNaoEncontradoError(Exception):
    """Entidade referenciada não existe — vira HTTP 404 na borda da API."""


class ConflitoError(Exception):
    """Estado do banco impede a operação — vira HTTP 409 na borda da API."""
```

- [ ] **Step 5: Implementar idade e TMB**

`backend/app/services/__init__.py` — arquivo vazio.

`backend/app/services/calculos.py`:

```python
"""Regras de negócio do Power Routine.

Funções puras: recebem números, devolvem números. Não importam FastAPI nem
SQLAlchemy — é isso que permite testá-las sem banco e sem servidor.
"""

from datetime import date

from app.domain.enums import Sexo

# Coeficientes da equação de Harris-Benedict revisada (Roza & Shizgal, 1984).
_COEFICIENTES_TMB = {
    Sexo.MASCULINO: (88.362, 13.397, 4.799, 5.677),
    Sexo.FEMININO: (447.593, 9.247, 3.098, 4.330),
}


def calcular_idade(data_nascimento: date, hoje: date) -> int:
    """Idade em anos completos. `hoje` é parâmetro para o cálculo ser determinístico."""
    idade = hoje.year - data_nascimento.year
    if (hoje.month, hoje.day) < (data_nascimento.month, data_nascimento.day):
        idade -= 1
    return idade


def calcular_tmb(sexo: Sexo, peso_kg: float, altura_cm: float, idade: int) -> float:
    """Taxa Metabólica Basal em kcal/dia (Harris-Benedict revisada)."""
    if peso_kg <= 0:
        raise ValueError("peso_kg deve ser maior que zero")
    if altura_cm <= 0:
        raise ValueError("altura_cm deve ser maior que zero")
    if idade <= 0:
        raise ValueError("idade deve ser maior que zero")

    base, c_peso, c_altura, c_idade = _COEFICIENTES_TMB[sexo]
    tmb = base + (c_peso * peso_kg) + (c_altura * altura_cm) - (c_idade * idade)
    return round(tmb, 2)
```

- [ ] **Step 6: Rodar e confirmar que passa**

Run: `cd backend && pytest tests/test_calculos.py -v`
Expected: 6 passed

- [ ] **Step 7: Commit**

```bash
git add backend/app/domain backend/app/services backend/tests/test_calculos.py
git commit -m "feat: adiciona enums de dominio e calculo de TMB por Harris-Benedict"
```

---

### Task 3: GET (fator de atividade) e meta calórica por objetivo

**Files:**
- Modify: `backend/app/services/calculos.py`
- Test: `backend/tests/test_calculos.py` (acrescentar)

**Interfaces:**
- Consumes: `NivelAtividade`, `TipoObjetivo` da Task 2
- Produces: `calcular_get(tmb: float, nivel: NivelAtividade) -> float`;
  `calcular_meta_calorica(get: float, objetivo: TipoObjetivo) -> float`

- [ ] **Step 1: Escrever os testes que falham**

Acrescentar em `backend/tests/test_calculos.py` (e completar o import do topo para
`from app.domain.enums import NivelAtividade, Sexo, TipoObjetivo`):

```python
from app.services.calculos import calcular_get, calcular_meta_calorica


def test_get_sedentario():
    assert calcular_get(1882.02, NivelAtividade.SEDENTARIO) == pytest.approx(2258.42, abs=0.01)


def test_get_moderado():
    assert calcular_get(1882.02, NivelAtividade.MODERADO) == pytest.approx(2917.13, abs=0.01)


def test_get_muito_intenso():
    assert calcular_get(1882.02, NivelAtividade.MUITO_INTENSO) == pytest.approx(3575.84, abs=0.01)


def test_meta_emagrecer_aplica_deficit_de_20_porcento():
    assert calcular_meta_calorica(2917.13, TipoObjetivo.EMAGRECER) == pytest.approx(2333.70, abs=0.01)


def test_meta_manter_nao_altera_o_get():
    assert calcular_meta_calorica(2917.13, TipoObjetivo.MANTER) == pytest.approx(2917.13, abs=0.01)


def test_meta_ganhar_massa_aplica_superavit_de_15_porcento():
    assert calcular_meta_calorica(2917.13, TipoObjetivo.GANHAR_MASSA) == pytest.approx(3354.70, abs=0.01)
```

- [ ] **Step 2: Rodar e confirmar que falha**

Run: `cd backend && pytest tests/test_calculos.py -v`
Expected: FAIL com `ImportError: cannot import name 'calcular_get'`

- [ ] **Step 3: Implementar**

Acrescentar em `backend/app/services/calculos.py` (e completar o import do topo para
`from app.domain.enums import NivelAtividade, Sexo, TipoObjetivo`):

```python
# Multiplicadores de gasto energético por nível de atividade física.
_FATORES_ATIVIDADE = {
    NivelAtividade.SEDENTARIO: 1.2,
    NivelAtividade.LEVE: 1.375,
    NivelAtividade.MODERADO: 1.55,
    NivelAtividade.INTENSO: 1.725,
    NivelAtividade.MUITO_INTENSO: 1.9,
}

# Ajuste calórico aplicado ao GET conforme o objetivo do usuário.
_AJUSTES_OBJETIVO = {
    TipoObjetivo.EMAGRECER: 0.80,
    TipoObjetivo.MANTER: 1.00,
    TipoObjetivo.GANHAR_MASSA: 1.15,
}


def calcular_get(tmb: float, nivel: NivelAtividade) -> float:
    """Gasto Energético Total em kcal/dia: TMB ajustada pela atividade física."""
    return round(tmb * _FATORES_ATIVIDADE[nivel], 2)


def calcular_meta_calorica(get: float, objetivo: TipoObjetivo) -> float:
    """Meta calórica diária: déficit para emagrecer, superávit para ganhar massa."""
    return round(get * _AJUSTES_OBJETIVO[objetivo], 2)
```

- [ ] **Step 4: Rodar e confirmar que passa**

Run: `cd backend && pytest tests/test_calculos.py -v`
Expected: 12 passed

- [ ] **Step 5: Commit**

```bash
git add backend/app/services/calculos.py backend/tests/test_calculos.py
git commit -m "feat: adiciona calculo de GET e meta calorica por objetivo"
```

---

### Task 4: Macronutrientes e orquestrador do perfil

**Files:**
- Create: `backend/app/domain/resultados.py`
- Modify: `backend/app/services/calculos.py`
- Test: `backend/tests/test_calculos.py` (acrescentar)

**Interfaces:**
- Consumes: tudo das Tasks 2 e 3
- Produces: `Macros(proteina_g, carboidrato_g, gordura_g)`;
  `ResultadoPerfil(idade, tmb_kcal, get_kcal, meta_kcal, macros)`;
  `calcular_macros(meta_kcal: float, peso_kg: float, objetivo: TipoObjetivo) -> Macros`;
  `calcular_perfil(sexo, data_nascimento, peso_kg, altura_cm, nivel, objetivo, hoje) -> ResultadoPerfil`

- [ ] **Step 1: Escrever os testes que falham**

Acrescentar em `backend/tests/test_calculos.py`:

```python
from app.domain.erros import RegraDeNegocioError
from app.services.calculos import calcular_macros, calcular_perfil


def test_macros_emagrecer_usa_18g_de_proteina_por_kg():
    macros = calcular_macros(meta_kcal=2333.70, peso_kg=80, objetivo=TipoObjetivo.EMAGRECER)
    assert macros.proteina_g == pytest.approx(144.00, abs=0.01)
    assert macros.gordura_g == pytest.approx(64.83, abs=0.01)
    assert macros.carboidrato_g == pytest.approx(293.57, abs=0.01)


def test_macros_ganhar_massa_usa_20g_de_proteina_por_kg():
    macros = calcular_macros(meta_kcal=3354.70, peso_kg=80, objetivo=TipoObjetivo.GANHAR_MASSA)
    assert macros.proteina_g == pytest.approx(160.00, abs=0.01)


def test_macros_somam_a_meta_calorica():
    macros = calcular_macros(meta_kcal=2333.70, peso_kg=80, objetivo=TipoObjetivo.EMAGRECER)
    total = macros.proteina_g * 4 + macros.carboidrato_g * 4 + macros.gordura_g * 9
    assert total == pytest.approx(2333.70, abs=0.5)


def test_macros_rejeita_meta_baixa_demais_para_o_peso():
    # 150 kg exigem 270 g de proteína (1080 kcal) + 25% de gordura: não cabe em 1200 kcal.
    with pytest.raises(RegraDeNegocioError):
        calcular_macros(meta_kcal=1200, peso_kg=150, objetivo=TipoObjetivo.EMAGRECER)


def test_calcular_perfil_encadeia_tudo():
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
```

- [ ] **Step 2: Rodar e confirmar que falha**

Run: `cd backend && pytest tests/test_calculos.py -v`
Expected: FAIL com `ModuleNotFoundError: No module named 'app.domain.resultados'`

- [ ] **Step 3: Implementar os resultados**

`backend/app/domain/resultados.py`:

```python
from dataclasses import dataclass


@dataclass(frozen=True)
class Macros:
    """Distribuição de macronutrientes em gramas."""

    proteina_g: float
    carboidrato_g: float
    gordura_g: float


@dataclass(frozen=True)
class ResultadoPerfil:
    """Saída completa do cálculo nutricional de um usuário."""

    idade: int
    tmb_kcal: float
    get_kcal: float
    meta_kcal: float
    macros: Macros
```

- [ ] **Step 4: Implementar macros e orquestrador**

Acrescentar em `backend/app/services/calculos.py`:

```python
KCAL_POR_GRAMA_PROTEINA = 4
KCAL_POR_GRAMA_CARBOIDRATO = 4
KCAL_POR_GRAMA_GORDURA = 9

# Gramas de proteína por quilo de peso corporal.
_PROTEINA_G_POR_KG = {
    TipoObjetivo.EMAGRECER: 1.8,
    TipoObjetivo.MANTER: 1.8,
    TipoObjetivo.GANHAR_MASSA: 2.0,
}

# Fração da meta calórica destinada a gordura.
_PERCENTUAL_GORDURA = 0.25


def calcular_macros(meta_kcal: float, peso_kg: float, objetivo: TipoObjetivo) -> Macros:
    """Distribui a meta calórica em macronutrientes.

    Proteína e gordura são fixadas primeiro (a proteína protege a massa magra,
    a gordura sustenta a função hormonal); o carboidrato absorve o que sobrar.
    """
    proteina_g = round(peso_kg * _PROTEINA_G_POR_KG[objetivo], 2)
    proteina_kcal = proteina_g * KCAL_POR_GRAMA_PROTEINA

    gordura_kcal = meta_kcal * _PERCENTUAL_GORDURA
    gordura_g = round(gordura_kcal / KCAL_POR_GRAMA_GORDURA, 2)

    carboidrato_kcal = meta_kcal - proteina_kcal - gordura_kcal
    if carboidrato_kcal < 0:
        raise RegraDeNegocioError(
            "meta calorica insuficiente: proteina e gordura ja excedem as calorias "
            f"disponiveis ({meta_kcal:.0f} kcal para {peso_kg:.0f} kg)"
        )

    return Macros(
        proteina_g=proteina_g,
        carboidrato_g=round(carboidrato_kcal / KCAL_POR_GRAMA_CARBOIDRATO, 2),
        gordura_g=gordura_g,
    )


def calcular_perfil(
    sexo: Sexo,
    data_nascimento: date,
    peso_kg: float,
    altura_cm: float,
    nivel: NivelAtividade,
    objetivo: TipoObjetivo,
    hoje: date,
) -> ResultadoPerfil:
    """Encadeia idade -> TMB -> GET -> meta calórica -> macronutrientes."""
    idade = calcular_idade(data_nascimento, hoje)
    tmb = calcular_tmb(sexo, peso_kg, altura_cm, idade)
    get = calcular_get(tmb, nivel)
    meta_kcal = calcular_meta_calorica(get, objetivo)
    macros = calcular_macros(meta_kcal, peso_kg, objetivo)
    return ResultadoPerfil(idade=idade, tmb_kcal=tmb, get_kcal=get, meta_kcal=meta_kcal, macros=macros)
```

Completar os imports do topo do arquivo:

```python
from app.domain.enums import NivelAtividade, Sexo, TipoObjetivo
from app.domain.erros import RegraDeNegocioError
from app.domain.resultados import Macros, ResultadoPerfil
```

- [ ] **Step 5: Rodar e confirmar que passa**

Run: `cd backend && pytest tests/test_calculos.py -v`
Expected: 17 passed

- [ ] **Step 6: Commit**

```bash
git add backend/app/domain/resultados.py backend/app/services/calculos.py backend/tests/test_calculos.py
git commit -m "feat: adiciona calculo de macronutrientes e orquestrador do perfil"
```

---

### Task 5: Infraestrutura de banco, modelo `Usuario` e Alembic

**Files:**
- Create: `backend/app/db/__init__.py`, `backend/app/db/base.py`, `backend/app/db/session.py`,
  `backend/app/models/__init__.py`, `backend/app/models/usuario.py`,
  `backend/alembic.ini`, `backend/alembic/env.py`, `backend/tests/conftest.py`
- Test: `backend/tests/test_models_usuario.py`

**Interfaces:**
- Consumes: `settings` (Task 1), `Sexo` (Task 2)
- Produces: `Base` (DeclarativeBase); `engine`, `SessionLocal`, `get_db` (dependência FastAPI);
  modelo `Usuario` com colunas `id, nome, email, sexo, data_nascimento, altura_cm`;
  fixtures pytest `engine` e `db`.

- [ ] **Step 1: Escrever o teste que falha**

`backend/tests/test_models_usuario.py`:

```python
from datetime import date

import pytest
from sqlalchemy.exc import IntegrityError

from app.domain.enums import Sexo
from app.models import Usuario


def test_persiste_e_recupera_usuario(db):
    db.add(Usuario(
        nome="Felipe",
        email="felipe@exemplo.com",
        sexo=Sexo.MASCULINO,
        data_nascimento=date(2001, 1, 1),
        altura_cm=180,
    ))
    db.commit()

    usuario = db.query(Usuario).filter_by(email="felipe@exemplo.com").one()
    assert usuario.id is not None
    assert usuario.sexo is Sexo.MASCULINO


def test_email_precisa_ser_unico(db):
    for _ in range(2):
        db.add(Usuario(
            nome="Felipe",
            email="repetido@exemplo.com",
            sexo=Sexo.MASCULINO,
            data_nascimento=date(2001, 1, 1),
            altura_cm=180,
        ))
    with pytest.raises(IntegrityError):
        db.commit()
```

- [ ] **Step 2: Rodar e confirmar que falha**

Run: `cd backend && pytest tests/test_models_usuario.py -v`
Expected: FAIL com `ModuleNotFoundError: No module named 'app.models'`

- [ ] **Step 3: Implementar a base declarativa e a sessão**

`backend/app/db/__init__.py` — arquivo vazio.

`backend/app/db/base.py`:

```python
from sqlalchemy.orm import DeclarativeBase


class Base(DeclarativeBase):
    """Base declarativa compartilhada por todos os modelos."""
```

`backend/app/db/session.py`:

```python
from collections.abc import Generator

from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker

from app.core.config import settings

engine = create_engine(settings.database_url, future=True)
SessionLocal = sessionmaker(bind=engine, autoflush=False, expire_on_commit=False)


def get_db() -> Generator[Session, None, None]:
    """Uma transação por requisição: commit no sucesso, rollback em qualquer exceção.

    Os services usam `flush()` para obter IDs; o commit acontece aqui, uma vez só.
    """
    db = SessionLocal()
    try:
        yield db
        db.commit()
    except Exception:
        db.rollback()
        raise
    finally:
        db.close()
```

- [ ] **Step 4: Implementar o modelo `Usuario`**

`backend/app/models/usuario.py`:

```python
from datetime import date

from sqlalchemy import CheckConstraint, Date, Enum as SAEnum, Float, String
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base
from app.domain.enums import Sexo


def enum_pg(enum_cls, nome: str) -> SAEnum:
    """Mapeia um Enum Python para um ENUM do PostgreSQL usando os *valores* (minúsculos)."""
    return SAEnum(enum_cls, name=nome, values_callable=lambda e: [item.value for item in e])


class Usuario(Base):
    __tablename__ = "usuario"

    id: Mapped[int] = mapped_column(primary_key=True)
    nome: Mapped[str] = mapped_column(String(120), nullable=False)
    email: Mapped[str] = mapped_column(String(255), unique=True, nullable=False)
    sexo: Mapped[Sexo] = mapped_column(enum_pg(Sexo, "sexo"), nullable=False)
    data_nascimento: Mapped[date] = mapped_column(Date, nullable=False)
    altura_cm: Mapped[float] = mapped_column(Float, nullable=False)

    __table_args__ = (
        CheckConstraint("altura_cm > 0 AND altura_cm < 300", name="ck_usuario_altura_valida"),
    )
```

`backend/app/models/__init__.py`:

```python
from app.models.usuario import Usuario

__all__ = ["Usuario"]
```

- [ ] **Step 5: Implementar as fixtures de teste**

`backend/tests/conftest.py`:

```python
import pytest
from sqlalchemy import create_engine, text
from sqlalchemy.orm import sessionmaker

import app.models  # noqa: F401 -- registra todas as tabelas no metadata
from app.core.config import settings
from app.db.base import Base


@pytest.fixture(scope="session")
def engine():
    eng = create_engine(settings.test_database_url, future=True)
    Base.metadata.drop_all(eng)
    Base.metadata.create_all(eng)
    yield eng
    eng.dispose()


@pytest.fixture(autouse=True)
def limpar_banco(engine):
    """Cada teste começa com o banco vazio e as sequences zeradas."""
    with engine.begin() as conn:
        for tabela in reversed(Base.metadata.sorted_tables):
            conn.execute(text(f'TRUNCATE TABLE "{tabela.name}" RESTART IDENTITY CASCADE'))


@pytest.fixture
def db(engine):
    sessao = sessionmaker(bind=engine, autoflush=False, expire_on_commit=False)()
    yield sessao
    sessao.close()
```

- [ ] **Step 6: Rodar e confirmar que passa**

Run: `cd backend && pytest -v`
Expected: 19 passed

- [ ] **Step 7: Configurar o Alembic e gerar a primeira migration**

```bash
cd backend
alembic init alembic
```

Editar `backend/alembic/env.py` — substituir o miolo de configuração por:

```python
import app.models  # noqa: F401 -- registra todas as tabelas no metadata
from app.core.config import settings
from app.db.base import Base

config.set_main_option("sqlalchemy.url", settings.database_url)
target_metadata = Base.metadata
```

Gerar e aplicar:

```bash
alembic revision --autogenerate -m "cria tabela usuario"
alembic upgrade head
```

Conferir no banco:

```bash
psql "postgresql://power:power@localhost:5432/power_routine" -c "\d usuario"
```

- [ ] **Step 8: Commit**

```bash
git add backend/
git commit -m "feat: adiciona infraestrutura de banco, modelo Usuario e migrations"
```

---

### Task 6: Modelos `Objetivo`, `RegistroDiario` e `Macronutrientes`

**Files:**
- Create: `backend/app/models/objetivo.py`, `backend/app/models/registro_diario.py`,
  `backend/app/models/macronutrientes.py`
- Modify: `backend/app/models/__init__.py`
- Test: `backend/tests/test_models_relacional.py`

**Interfaces:**
- Consumes: `Base`, `enum_pg`, `Usuario` (Task 5); enums (Task 2)
- Produces: `Objetivo(id, usuario_id, tipo, nivel_atividade, peso_kg, peso_meta_kg,
  tmb_kcal, get_kcal, meta_kcal, data_inicio, ativo)`;
  `RegistroDiario(id, usuario_id, data, peso_kg, calorias_kcal, observacoes)`;
  `Macronutrientes(id, tipo, objetivo_id, registro_diario_id, proteina_g, carboidrato_g, gordura_g)`

- [ ] **Step 1: Escrever os testes que falham**

`backend/tests/test_models_relacional.py`:

```python
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
```

- [ ] **Step 2: Rodar e confirmar que falha**

Run: `cd backend && pytest tests/test_models_relacional.py -v`
Expected: FAIL com `ImportError: cannot import name 'Objetivo' from 'app.models'`

- [ ] **Step 3: Implementar `Objetivo`**

`backend/app/models/objetivo.py`:

```python
from datetime import date

from sqlalchemy import Boolean, CheckConstraint, Date, Float, ForeignKey, Index, text
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base
from app.domain.enums import NivelAtividade, TipoObjetivo
from app.models.usuario import enum_pg


class Objetivo(Base):
    """Meta nutricional vigente de um usuário, com o resultado do cálculo congelado.

    Guardar tmb/get/meta é intencional: é o histórico do que foi prescrito naquele
    momento, e não muda se as fórmulas do sistema forem ajustadas depois.
    """

    __tablename__ = "objetivo"

    id: Mapped[int] = mapped_column(primary_key=True)
    usuario_id: Mapped[int] = mapped_column(
        ForeignKey("usuario.id", ondelete="CASCADE"), nullable=False, index=True
    )
    tipo: Mapped[TipoObjetivo] = mapped_column(enum_pg(TipoObjetivo, "tipo_objetivo"), nullable=False)
    nivel_atividade: Mapped[NivelAtividade] = mapped_column(
        enum_pg(NivelAtividade, "nivel_atividade"), nullable=False
    )
    peso_kg: Mapped[float] = mapped_column(Float, nullable=False)
    peso_meta_kg: Mapped[float | None] = mapped_column(Float, nullable=True)
    tmb_kcal: Mapped[float] = mapped_column(Float, nullable=False)
    get_kcal: Mapped[float] = mapped_column(Float, nullable=False)
    meta_kcal: Mapped[float] = mapped_column(Float, nullable=False)
    data_inicio: Mapped[date] = mapped_column(Date, nullable=False)
    ativo: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)

    __table_args__ = (
        CheckConstraint("peso_kg > 0", name="ck_objetivo_peso_positivo"),
        # Índice parcial: a unicidade só vale para as linhas ativas.
        Index(
            "ix_objetivo_um_ativo_por_usuario",
            "usuario_id",
            unique=True,
            postgresql_where=text("ativo"),
        ),
    )
```

- [ ] **Step 4: Implementar `RegistroDiario`**

`backend/app/models/registro_diario.py`:

```python
from datetime import date

from sqlalchemy import CheckConstraint, Date, Float, ForeignKey, String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base


class RegistroDiario(Base):
    """Uma linha por usuário por dia."""

    __tablename__ = "registro_diario"

    id: Mapped[int] = mapped_column(primary_key=True)
    usuario_id: Mapped[int] = mapped_column(
        ForeignKey("usuario.id", ondelete="CASCADE"), nullable=False, index=True
    )
    data: Mapped[date] = mapped_column(Date, nullable=False)
    peso_kg: Mapped[float] = mapped_column(Float, nullable=False)
    calorias_kcal: Mapped[float] = mapped_column(Float, nullable=False)
    observacoes: Mapped[str | None] = mapped_column(String(500), nullable=True)

    __table_args__ = (
        UniqueConstraint("usuario_id", "data", name="uq_registro_diario_usuario_data"),
        CheckConstraint("peso_kg > 0", name="ck_registro_peso_positivo"),
        CheckConstraint("calorias_kcal >= 0", name="ck_registro_calorias_nao_negativas"),
    )
```

- [ ] **Step 5: Implementar `Macronutrientes` com o discriminador**

`backend/app/models/macronutrientes.py`:

```python
from sqlalchemy import CheckConstraint, Float, ForeignKey, Index, text
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base
from app.domain.enums import TipoMacro
from app.models.usuario import enum_pg


class Macronutrientes(Base):
    """Distribuição de macros — prescrita (`meta`) ou realizada (`consumo`).

    Uma tabela só, discriminada por `tipo`. Cada linha aponta para exatamente um
    dono: `meta` pertence a um Objetivo, `consumo` pertence a um RegistroDiario.
    O CHECK abaixo torna qualquer outra combinação impossível no banco.
    """

    __tablename__ = "macronutrientes"

    id: Mapped[int] = mapped_column(primary_key=True)
    tipo: Mapped[TipoMacro] = mapped_column(enum_pg(TipoMacro, "tipo_macro"), nullable=False)
    objetivo_id: Mapped[int | None] = mapped_column(
        ForeignKey("objetivo.id", ondelete="CASCADE"), nullable=True
    )
    registro_diario_id: Mapped[int | None] = mapped_column(
        ForeignKey("registro_diario.id", ondelete="CASCADE"), nullable=True
    )
    proteina_g: Mapped[float] = mapped_column(Float, nullable=False)
    carboidrato_g: Mapped[float] = mapped_column(Float, nullable=False)
    gordura_g: Mapped[float] = mapped_column(Float, nullable=False)

    __table_args__ = (
        CheckConstraint(
            "(tipo = 'meta' AND objetivo_id IS NOT NULL AND registro_diario_id IS NULL)"
            " OR "
            "(tipo = 'consumo' AND registro_diario_id IS NOT NULL AND objetivo_id IS NULL)",
            name="ck_macronutrientes_discriminador",
        ),
        CheckConstraint(
            "proteina_g >= 0 AND carboidrato_g >= 0 AND gordura_g >= 0",
            name="ck_macronutrientes_nao_negativo",
        ),
        # 1:1 com cada dono, garantido por índices parciais.
        Index(
            "ix_macro_meta_unica_por_objetivo",
            "objetivo_id",
            unique=True,
            postgresql_where=text("tipo = 'meta'"),
        ),
        Index(
            "ix_macro_consumo_unico_por_registro",
            "registro_diario_id",
            unique=True,
            postgresql_where=text("tipo = 'consumo'"),
        ),
    )
```

`backend/app/models/__init__.py`:

```python
from app.models.macronutrientes import Macronutrientes
from app.models.objetivo import Objetivo
from app.models.registro_diario import RegistroDiario
from app.models.usuario import Usuario

__all__ = ["Macronutrientes", "Objetivo", "RegistroDiario", "Usuario"]
```

- [ ] **Step 6: Rodar e confirmar que passa**

Run: `cd backend && pytest -v`
Expected: 25 passed

- [ ] **Step 7: Gerar a migration**

```bash
cd backend
alembic revision --autogenerate -m "cria objetivo, registro_diario e macronutrientes"
alembic upgrade head
psql "postgresql://power:power@localhost:5432/power_routine" -c "\d macronutrientes"
```

Conferir que o `CHECK ck_macronutrientes_discriminador` aparece na saída do `\d` — esse
print é evidência direta da seção 18.2.

- [ ] **Step 8: Commit**

```bash
git add backend/
git commit -m "feat: adiciona modelo relacional completo com discriminador de macros"
```

---

### Task 7: App FastAPI, tratamento de erros e endpoints de usuário

**Files:**
- Create: `backend/app/main.py`, `backend/app/api/__init__.py`, `backend/app/api/handlers.py`,
  `backend/app/api/routers/__init__.py`, `backend/app/api/routers/usuarios.py`,
  `backend/app/schemas/__init__.py`, `backend/app/schemas/usuario.py`,
  `backend/app/services/usuario_service.py`
- Modify: `backend/requirements.txt` (acrescentar `email-validator`), `backend/tests/conftest.py`
- Test: `backend/tests/test_usuarios_api.py`

**Interfaces:**
- Consumes: `get_db` (Task 5), `Usuario` (Task 5), `calcular_idade` (Task 2), erros (Task 2)
- Produces: `app` (instância FastAPI); schemas `UsuarioCriar`, `UsuarioLido`, `UsuarioDetalhe`;
  `usuario_service.criar_usuario(db, dados) -> Usuario`,
  `usuario_service.buscar_usuario(db, usuario_id) -> Usuario`; fixture pytest `client`.

- [ ] **Step 1: Acrescentar a dependência de validação de e-mail**

Acrescentar em `backend/requirements.txt`:

```
email-validator>=2.2
```

```bash
cd backend && pip install -r requirements.txt
```

- [ ] **Step 2: Escrever o teste que falha**

`backend/tests/test_usuarios_api.py`:

```python
USUARIO_VALIDO = {
    "nome": "Felipe",
    "email": "felipe@exemplo.com",
    "sexo": "masculino",
    "data_nascimento": "2001-01-01",
    "altura_cm": 180,
}


def test_cria_usuario(client):
    resposta = client.post("/api/usuarios", json=USUARIO_VALIDO)
    assert resposta.status_code == 201
    corpo = resposta.json()
    assert corpo["id"] > 0
    assert corpo["email"] == "felipe@exemplo.com"


def test_le_usuario_com_idade_derivada(client):
    usuario_id = client.post("/api/usuarios", json=USUARIO_VALIDO).json()["id"]

    resposta = client.get(f"/api/usuarios/{usuario_id}")
    assert resposta.status_code == 200
    assert resposta.json()["idade"] >= 25


def test_usuario_inexistente_retorna_404(client):
    resposta = client.get("/api/usuarios/9999")
    assert resposta.status_code == 404


def test_rejeita_email_invalido(client):
    resposta = client.post("/api/usuarios", json={**USUARIO_VALIDO, "email": "nao-e-email"})
    assert resposta.status_code == 422


def test_rejeita_altura_fora_da_faixa(client):
    resposta = client.post("/api/usuarios", json={**USUARIO_VALIDO, "altura_cm": 400})
    assert resposta.status_code == 422


def test_rejeita_data_nascimento_no_futuro(client):
    resposta = client.post("/api/usuarios", json={**USUARIO_VALIDO, "data_nascimento": "2099-01-01"})
    assert resposta.status_code == 422


def test_email_duplicado_retorna_409(client):
    client.post("/api/usuarios", json=USUARIO_VALIDO)
    resposta = client.post("/api/usuarios", json=USUARIO_VALIDO)
    assert resposta.status_code == 409
```

- [ ] **Step 3: Rodar e confirmar que falha**

Run: `cd backend && pytest tests/test_usuarios_api.py -v`
Expected: FAIL com `fixture 'client' not found`

- [ ] **Step 4: Acrescentar a fixture `client`**

Acrescentar em `backend/tests/conftest.py`:

```python
from fastapi.testclient import TestClient

from app.db.session import get_db
from app.main import app


@pytest.fixture
def client(db):
    """Cliente HTTP que compartilha a sessão do teste, para o TRUNCATE alcançar tudo."""

    def _get_db():
        try:
            yield db
            db.commit()
        except Exception:
            db.rollback()
            raise

    app.dependency_overrides[get_db] = _get_db
    with TestClient(app) as c:
        yield c
    app.dependency_overrides.clear()
```

- [ ] **Step 5: Implementar os schemas**

`backend/app/schemas/__init__.py` — arquivo vazio.

`backend/app/schemas/usuario.py`:

```python
from datetime import date

from pydantic import BaseModel, ConfigDict, EmailStr, Field, field_validator

from app.domain.enums import Sexo


class UsuarioCriar(BaseModel):
    """Primeira camada de validação: formato e faixa, antes de qualquer regra de negócio."""

    nome: str = Field(min_length=2, max_length=120)
    email: EmailStr
    sexo: Sexo
    data_nascimento: date
    altura_cm: float = Field(gt=50, lt=250)

    @field_validator("data_nascimento")
    @classmethod
    def validar_data_nascimento(cls, valor: date) -> date:
        if valor >= date.today():
            raise ValueError("data_nascimento deve estar no passado")
        return valor


class UsuarioLido(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    nome: str
    email: EmailStr
    sexo: Sexo
    data_nascimento: date
    altura_cm: float


class UsuarioDetalhe(UsuarioLido):
    idade: int
```

- [ ] **Step 6: Implementar o service**

`backend/app/services/usuario_service.py`:

```python
from datetime import date

from sqlalchemy.orm import Session

from app.domain.erros import RecursoNaoEncontradoError
from app.models import Usuario
from app.schemas.usuario import UsuarioCriar
from app.services.calculos import calcular_idade


def criar_usuario(db: Session, dados: UsuarioCriar) -> Usuario:
    usuario = Usuario(**dados.model_dump())
    db.add(usuario)
    db.flush()  # obtém o id sem encerrar a transação — o commit é do get_db
    return usuario


def buscar_usuario(db: Session, usuario_id: int) -> Usuario:
    usuario = db.get(Usuario, usuario_id)
    if usuario is None:
        raise RecursoNaoEncontradoError(f"usuario {usuario_id} nao encontrado")
    return usuario


def idade_do_usuario(usuario: Usuario, hoje: date | None = None) -> int:
    return calcular_idade(usuario.data_nascimento, hoje or date.today())
```

- [ ] **Step 7: Implementar os handlers de erro**

`backend/app/api/__init__.py` e `backend/app/api/routers/__init__.py` — arquivos vazios.

`backend/app/api/handlers.py`:

```python
from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse
from sqlalchemy.exc import IntegrityError

from app.domain.erros import ConflitoError, RecursoNaoEncontradoError, RegraDeNegocioError


def registrar_handlers(app: FastAPI) -> None:
    """Traduz exceções de domínio em respostas HTTP, em um lugar só.

    Nenhum service precisa conhecer status code; nenhum router precisa de try/except.
    """

    @app.exception_handler(RecursoNaoEncontradoError)
    async def nao_encontrado(request: Request, exc: RecursoNaoEncontradoError):
        return JSONResponse(status_code=404, content={"detail": str(exc)})

    @app.exception_handler(RegraDeNegocioError)
    async def regra_violada(request: Request, exc: RegraDeNegocioError):
        return JSONResponse(status_code=422, content={"detail": str(exc)})

    @app.exception_handler(ConflitoError)
    async def conflito(request: Request, exc: ConflitoError):
        return JSONResponse(status_code=409, content={"detail": str(exc)})

    @app.exception_handler(IntegrityError)
    async def integridade(request: Request, exc: IntegrityError):
        # Última camada: uma constraint do banco barrou a operação.
        return JSONResponse(
            status_code=409,
            content={"detail": "operacao viola uma restricao de integridade do banco"},
        )
```

- [ ] **Step 8: Implementar o router e o app**

`backend/app/api/routers/usuarios.py`:

```python
from fastapi import APIRouter, Depends, status
from sqlalchemy.orm import Session

from app.db.session import get_db
from app.schemas.usuario import UsuarioCriar, UsuarioDetalhe, UsuarioLido
from app.services import usuario_service

router = APIRouter(prefix="/usuarios", tags=["usuarios"])


@router.post("", response_model=UsuarioLido, status_code=status.HTTP_201_CREATED)
def criar(dados: UsuarioCriar, db: Session = Depends(get_db)) -> UsuarioLido:
    """Cadastra um usuário. Sexo e data de nascimento são obrigatórios para o cálculo de TMB."""
    return UsuarioLido.model_validate(usuario_service.criar_usuario(db, dados))


@router.get("/{usuario_id}", response_model=UsuarioDetalhe)
def ler(usuario_id: int, db: Session = Depends(get_db)) -> UsuarioDetalhe:
    """Retorna o usuário com a idade derivada da data de nascimento."""
    usuario = usuario_service.buscar_usuario(db, usuario_id)
    return UsuarioDetalhe(
        **UsuarioLido.model_validate(usuario).model_dump(),
        idade=usuario_service.idade_do_usuario(usuario),
    )
```

`backend/app/main.py`:

```python
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api.handlers import registrar_handlers
from app.api.routers import usuarios

app = FastAPI(
    title="Power Routine API",
    version="1.0.0",
    description=(
        "API do projeto integrador Power Routine. Calcula TMB (Harris-Benedict), "
        "GET, meta calorica e macronutrientes, e registra o acompanhamento diario."
    ),
)

# O frontend estático é servido de outra origem (file:// ou http.server).
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

registrar_handlers(app)
app.include_router(usuarios.router, prefix="/api")


@app.get("/api/saude", tags=["infra"])
def saude() -> dict[str, str]:
    return {"status": "ok"}
```

- [ ] **Step 9: Rodar e confirmar que passa**

Run: `cd backend && pytest -v`
Expected: 32 passed

- [ ] **Step 10: Subir o servidor e conferir o Swagger**

```bash
cd backend && uvicorn app.main:app --reload
```

Abrir `http://127.0.0.1:8000/docs` — **primeiro print da seção 22.2**.

- [ ] **Step 11: Commit**

```bash
git add backend/
git commit -m "feat: adiciona app FastAPI, handlers de erro e endpoints de usuario"
```

---

### Task 8: `POST /api/perfil/calcular`

**Files:**
- Create: `backend/app/schemas/perfil.py`, `backend/app/services/perfil_service.py`,
  `backend/app/api/routers/perfil.py`
- Modify: `backend/app/main.py`
- Test: `backend/tests/test_perfil_api.py`

**Interfaces:**
- Consumes: `calcular_perfil` (Task 4), `Objetivo`/`Macronutrientes` (Task 6),
  `buscar_usuario` (Task 7)
- Produces: schemas `PerfilCalcularEntrada`, `MacrosLidos`, `PerfilCalculado`;
  `perfil_service.calcular_e_salvar(db, dados) -> tuple[Objetivo, Macronutrientes, int]`;
  `perfil_service.objetivo_ativo(db, usuario_id) -> Objetivo`

- [ ] **Step 1: Escrever o teste que falha**

`backend/tests/test_perfil_api.py`:

```python
import pytest

USUARIO_VALIDO = {
    "nome": "Felipe",
    "email": "felipe@exemplo.com",
    "sexo": "masculino",
    "data_nascimento": "2001-01-01",
    "altura_cm": 180,
}


@pytest.fixture
def usuario_id(client) -> int:
    return client.post("/api/usuarios", json=USUARIO_VALIDO).json()["id"]


def test_calcula_e_retorna_o_perfil(client, usuario_id):
    resposta = client.post("/api/perfil/calcular", json={
        "usuario_id": usuario_id,
        "peso_kg": 80,
        "nivel_atividade": "moderado",
        "objetivo": "emagrecer",
        "peso_meta_kg": 72,
    })

    assert resposta.status_code == 201
    corpo = resposta.json()
    assert corpo["tmb_kcal"] == pytest.approx(1882.02, abs=1)
    assert corpo["get_kcal"] == pytest.approx(2917.13, abs=1)
    assert corpo["meta_kcal"] == pytest.approx(2333.70, abs=1)
    assert corpo["macros"]["proteina_g"] == pytest.approx(144.00, abs=0.01)


def test_recalcular_desativa_o_objetivo_anterior(client, usuario_id):
    payload = {
        "usuario_id": usuario_id,
        "peso_kg": 80,
        "nivel_atividade": "moderado",
        "objetivo": "emagrecer",
    }
    primeiro = client.post("/api/perfil/calcular", json=payload).json()
    segundo = client.post("/api/perfil/calcular", json={**payload, "objetivo": "ganhar_massa"}).json()

    assert segundo["objetivo_id"] != primeiro["objetivo_id"]
    assert segundo["meta_kcal"] > primeiro["meta_kcal"]


def test_usuario_inexistente_retorna_404(client):
    resposta = client.post("/api/perfil/calcular", json={
        "usuario_id": 9999, "peso_kg": 80, "nivel_atividade": "moderado", "objetivo": "manter",
    })
    assert resposta.status_code == 404


def test_peso_negativo_retorna_422(client, usuario_id):
    resposta = client.post("/api/perfil/calcular", json={
        "usuario_id": usuario_id, "peso_kg": -5, "nivel_atividade": "moderado", "objetivo": "manter",
    })
    assert resposta.status_code == 422


def test_nivel_atividade_invalido_retorna_422(client, usuario_id):
    resposta = client.post("/api/perfil/calcular", json={
        "usuario_id": usuario_id, "peso_kg": 80, "nivel_atividade": "voando", "objetivo": "manter",
    })
    assert resposta.status_code == 422
```

- [ ] **Step 2: Rodar e confirmar que falha**

Run: `cd backend && pytest tests/test_perfil_api.py -v`
Expected: FAIL com `404 Not Found` (a rota ainda não existe)

- [ ] **Step 3: Implementar os schemas**

`backend/app/schemas/perfil.py`:

```python
from pydantic import BaseModel, ConfigDict, Field

from app.domain.enums import NivelAtividade, TipoObjetivo


class PerfilCalcularEntrada(BaseModel):
    usuario_id: int = Field(gt=0)
    peso_kg: float = Field(gt=20, lt=400)
    nivel_atividade: NivelAtividade
    objetivo: TipoObjetivo
    peso_meta_kg: float | None = Field(default=None, gt=20, lt=400)


class MacrosLidos(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    proteina_g: float
    carboidrato_g: float
    gordura_g: float


class PerfilCalculado(BaseModel):
    objetivo_id: int
    usuario_id: int
    idade: int
    tmb_kcal: float
    get_kcal: float
    meta_kcal: float
    macros: MacrosLidos
```

- [ ] **Step 4: Implementar o service**

`backend/app/services/perfil_service.py`:

```python
from datetime import date

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.domain.enums import TipoMacro
from app.domain.erros import RecursoNaoEncontradoError
from app.models import Macronutrientes, Objetivo
from app.schemas.perfil import PerfilCalcularEntrada
from app.services import usuario_service
from app.services.calculos import calcular_perfil


def objetivo_ativo(db: Session, usuario_id: int) -> Objetivo:
    objetivo = db.scalar(
        select(Objetivo).where(Objetivo.usuario_id == usuario_id, Objetivo.ativo.is_(True))
    )
    if objetivo is None:
        raise RecursoNaoEncontradoError(
            f"usuario {usuario_id} nao possui objetivo ativo; chame POST /api/perfil/calcular"
        )
    return objetivo


def calcular_e_salvar(
    db: Session, dados: PerfilCalcularEntrada, hoje: date | None = None
) -> tuple[Objetivo, Macronutrientes, int]:
    """Calcula o perfil e o congela como o Objetivo ativo do usuário.

    Recalcular não apaga histórico: o objetivo anterior é apenas desativado, o que
    preserva a série de prescrições e libera o índice parcial de unicidade.
    """
    hoje = hoje or date.today()
    usuario = usuario_service.buscar_usuario(db, dados.usuario_id)

    resultado = calcular_perfil(
        sexo=usuario.sexo,
        data_nascimento=usuario.data_nascimento,
        peso_kg=dados.peso_kg,
        altura_cm=usuario.altura_cm,
        nivel=dados.nivel_atividade,
        objetivo=dados.objetivo,
        hoje=hoje,
    )

    anterior = db.scalar(
        select(Objetivo).where(Objetivo.usuario_id == usuario.id, Objetivo.ativo.is_(True))
    )
    if anterior is not None:
        anterior.ativo = False
        db.flush()  # libera o indice parcial antes de inserir o novo objetivo ativo

    objetivo = Objetivo(
        usuario_id=usuario.id,
        tipo=dados.objetivo,
        nivel_atividade=dados.nivel_atividade,
        peso_kg=dados.peso_kg,
        peso_meta_kg=dados.peso_meta_kg,
        tmb_kcal=resultado.tmb_kcal,
        get_kcal=resultado.get_kcal,
        meta_kcal=resultado.meta_kcal,
        data_inicio=hoje,
        ativo=True,
    )
    db.add(objetivo)
    db.flush()

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
```

- [ ] **Step 5: Implementar o router e registrá-lo**

`backend/app/api/routers/perfil.py`:

```python
from fastapi import APIRouter, Depends, status
from sqlalchemy.orm import Session

from app.db.session import get_db
from app.schemas.perfil import MacrosLidos, PerfilCalcularEntrada, PerfilCalculado
from app.services import perfil_service

router = APIRouter(prefix="/perfil", tags=["perfil"])


@router.post("/calcular", response_model=PerfilCalculado, status_code=status.HTTP_201_CREATED)
def calcular(dados: PerfilCalcularEntrada, db: Session = Depends(get_db)) -> PerfilCalculado:
    """Calcula TMB, GET, meta calórica e macronutrientes, e grava o objetivo ativo."""
    objetivo, macros, idade = perfil_service.calcular_e_salvar(db, dados)
    return PerfilCalculado(
        objetivo_id=objetivo.id,
        usuario_id=objetivo.usuario_id,
        idade=idade,
        tmb_kcal=objetivo.tmb_kcal,
        get_kcal=objetivo.get_kcal,
        meta_kcal=objetivo.meta_kcal,
        macros=MacrosLidos.model_validate(macros),
    )
```

Em `backend/app/main.py`, trocar o import e acrescentar o router:

```python
from app.api.routers import perfil, usuarios

app.include_router(usuarios.router, prefix="/api")
app.include_router(perfil.router, prefix="/api")
```

- [ ] **Step 6: Rodar e confirmar que passa**

Run: `cd backend && pytest -v`
Expected: 37 passed

- [ ] **Step 7: Commit**

```bash
git add backend/
git commit -m "feat: adiciona endpoint POST /api/perfil/calcular"
```

---

### Task 9: `POST /api/diario/registro`

**Files:**
- Create: `backend/app/schemas/diario.py`, `backend/app/services/diario_service.py`,
  `backend/app/api/routers/diario.py`
- Modify: `backend/app/main.py`
- Test: `backend/tests/test_diario_api.py`

**Interfaces:**
- Consumes: `RegistroDiario`/`Macronutrientes` (Task 6), `buscar_usuario` (Task 7),
  `MacrosLidos` (Task 8)
- Produces: schemas `DiarioRegistroEntrada`, `RegistroLido`;
  `diario_service.registrar(db, dados) -> tuple[RegistroDiario, Macronutrientes]`

- [ ] **Step 1: Escrever o teste que falha**

`backend/tests/test_diario_api.py`:

```python
import pytest

USUARIO_VALIDO = {
    "nome": "Felipe",
    "email": "felipe@exemplo.com",
    "sexo": "masculino",
    "data_nascimento": "2001-01-01",
    "altura_cm": 180,
}


@pytest.fixture
def usuario_id(client) -> int:
    novo_id = client.post("/api/usuarios", json=USUARIO_VALIDO).json()["id"]
    client.post("/api/perfil/calcular", json={
        "usuario_id": novo_id,
        "peso_kg": 80,
        "nivel_atividade": "moderado",
        "objetivo": "emagrecer",
    })
    return novo_id


def registro(usuario_id: int, **overrides) -> dict:
    return {
        "usuario_id": usuario_id,
        "data": "2026-06-01",
        "peso_kg": 80,
        "calorias_kcal": 2300,
        "proteina_g": 140,
        "carboidrato_g": 290,
        "gordura_g": 64,
        "observacoes": "treino de pernas",
    } | overrides


def test_cria_registro_diario(client, usuario_id):
    resposta = client.post("/api/diario/registro", json=registro(usuario_id))

    assert resposta.status_code == 201
    corpo = resposta.json()
    assert corpo["data"] == "2026-06-01"
    assert corpo["macros"]["proteina_g"] == 140


def test_registro_do_mesmo_dia_atualiza_em_vez_de_duplicar(client, usuario_id):
    primeiro = client.post("/api/diario/registro", json=registro(usuario_id)).json()
    segundo = client.post(
        "/api/diario/registro", json=registro(usuario_id, calorias_kcal=2500, proteina_g=150)
    ).json()

    assert segundo["id"] == primeiro["id"]
    assert segundo["calorias_kcal"] == 2500
    assert segundo["macros"]["proteina_g"] == 150


def test_dias_diferentes_geram_registros_diferentes(client, usuario_id):
    primeiro = client.post("/api/diario/registro", json=registro(usuario_id)).json()
    segundo = client.post(
        "/api/diario/registro", json=registro(usuario_id, data="2026-06-02")
    ).json()

    assert segundo["id"] != primeiro["id"]


def test_usuario_inexistente_retorna_404(client):
    resposta = client.post("/api/diario/registro", json=registro(9999))
    assert resposta.status_code == 404


def test_rejeita_data_futura(client, usuario_id):
    resposta = client.post("/api/diario/registro", json=registro(usuario_id, data="2099-01-01"))
    assert resposta.status_code == 422


def test_rejeita_macro_negativo(client, usuario_id):
    resposta = client.post("/api/diario/registro", json=registro(usuario_id, proteina_g=-1))
    assert resposta.status_code == 422
```

- [ ] **Step 2: Rodar e confirmar que falha**

Run: `cd backend && pytest tests/test_diario_api.py -v`
Expected: FAIL com `404 Not Found` (a rota ainda não existe)

- [ ] **Step 3: Implementar os schemas**

`backend/app/schemas/diario.py`:

```python
from datetime import date

from pydantic import BaseModel, Field, field_validator

from app.schemas.perfil import MacrosLidos


class DiarioRegistroEntrada(BaseModel):
    usuario_id: int = Field(gt=0)
    data: date
    peso_kg: float = Field(gt=20, lt=400)
    calorias_kcal: float = Field(ge=0, le=15000)
    proteina_g: float = Field(ge=0, le=1000)
    carboidrato_g: float = Field(ge=0, le=2000)
    gordura_g: float = Field(ge=0, le=1000)
    observacoes: str | None = Field(default=None, max_length=500)

    @field_validator("data")
    @classmethod
    def validar_data(cls, valor: date) -> date:
        if valor > date.today():
            raise ValueError("nao e possivel registrar um dia no futuro")
        return valor


class RegistroLido(BaseModel):
    id: int
    usuario_id: int
    data: date
    peso_kg: float
    calorias_kcal: float
    observacoes: str | None
    macros: MacrosLidos
```

- [ ] **Step 4: Implementar o service**

`backend/app/services/diario_service.py`:

```python
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.domain.enums import TipoMacro
from app.models import Macronutrientes, RegistroDiario
from app.schemas.diario import DiarioRegistroEntrada
from app.services import usuario_service


def registrar(
    db: Session, dados: DiarioRegistroEntrada
) -> tuple[RegistroDiario, Macronutrientes]:
    """Grava o dia do usuário. Idempotente por (usuario_id, data): regrava, não duplica.

    A alternativa — deixar o UNIQUE estourar e devolver 409 — obrigaria o frontend a
    saber se o dia já existe antes de enviar. Regravar é o comportamento útil aqui.
    """
    usuario = usuario_service.buscar_usuario(db, dados.usuario_id)

    registro = db.scalar(
        select(RegistroDiario).where(
            RegistroDiario.usuario_id == usuario.id, RegistroDiario.data == dados.data
        )
    )
    if registro is None:
        registro = RegistroDiario(usuario_id=usuario.id, data=dados.data)
        db.add(registro)

    registro.peso_kg = dados.peso_kg
    registro.calorias_kcal = dados.calorias_kcal
    registro.observacoes = dados.observacoes
    db.flush()

    macros = db.scalar(
        select(Macronutrientes).where(
            Macronutrientes.registro_diario_id == registro.id,
            Macronutrientes.tipo == TipoMacro.CONSUMO,
        )
    )
    if macros is None:
        macros = Macronutrientes(tipo=TipoMacro.CONSUMO, registro_diario_id=registro.id)
        db.add(macros)

    macros.proteina_g = dados.proteina_g
    macros.carboidrato_g = dados.carboidrato_g
    macros.gordura_g = dados.gordura_g
    db.flush()

    return registro, macros
```

- [ ] **Step 5: Implementar o router e registrá-lo**

`backend/app/api/routers/diario.py`:

```python
from fastapi import APIRouter, Depends, status
from sqlalchemy.orm import Session

from app.db.session import get_db
from app.schemas.diario import DiarioRegistroEntrada, RegistroLido
from app.schemas.perfil import MacrosLidos
from app.services import diario_service

router = APIRouter(prefix="/diario", tags=["diario"])


@router.post("/registro", response_model=RegistroLido, status_code=status.HTTP_201_CREATED)
def registrar(dados: DiarioRegistroEntrada, db: Session = Depends(get_db)) -> RegistroLido:
    """Registra (ou regrava) o dia do usuário: peso, calorias e macros consumidos."""
    registro, macros = diario_service.registrar(db, dados)
    return RegistroLido(
        id=registro.id,
        usuario_id=registro.usuario_id,
        data=registro.data,
        peso_kg=registro.peso_kg,
        calorias_kcal=registro.calorias_kcal,
        observacoes=registro.observacoes,
        macros=MacrosLidos.model_validate(macros),
    )
```

Em `backend/app/main.py`:

```python
from app.api.routers import diario, perfil, usuarios

app.include_router(usuarios.router, prefix="/api")
app.include_router(perfil.router, prefix="/api")
app.include_router(diario.router, prefix="/api")
```

- [ ] **Step 6: Rodar e confirmar que passa**

Run: `cd backend && pytest -v`
Expected: 43 passed

- [ ] **Step 7: Commit**

```bash
git add backend/
git commit -m "feat: adiciona endpoint POST /api/diario/registro com upsert por dia"
```

---

### Task 10: `GET /api/diario/{usuario_id}` — comparativo meta vs. consumo

**Files:**
- Modify: `backend/app/schemas/diario.py`, `backend/app/services/diario_service.py`,
  `backend/app/api/routers/diario.py`
- Test: `backend/tests/test_diario_api.py` (acrescentar)

**Interfaces:**
- Consumes: `objetivo_ativo` (Task 8), `TipoMacro` (Task 2)
- Produces: schemas `ComparativoDia`, `DiarioResumo`;
  `diario_service.resumo(db, usuario_id) -> DiarioResumo`

Esta é a task que justifica o discriminador: `meta` e `consumo` moram na mesma tabela,
então o comparativo sai de uma consulta só.

- [ ] **Step 1: Escrever os testes que falham**

Acrescentar em `backend/tests/test_diario_api.py`:

```python
def test_resumo_compara_consumo_com_a_meta(client, usuario_id):
    client.post("/api/diario/registro", json=registro(usuario_id))

    resposta = client.get(f"/api/diario/{usuario_id}")

    assert resposta.status_code == 200
    corpo = resposta.json()
    assert corpo["objetivo"] == "emagrecer"
    assert corpo["meta_kcal"] == pytest.approx(2333.70, abs=1)

    dia = corpo["registros"][0]
    assert dia["consumido_kcal"] == 2300
    assert dia["diferenca_kcal"] == pytest.approx(-33.70, abs=1)
    assert dia["aderencia_percentual"] == pytest.approx(98.56, abs=0.5)
    assert dia["macros_consumidos"]["proteina_g"] == 140
    assert dia["macros_meta"]["proteina_g"] == pytest.approx(144.00, abs=0.01)


def test_resumo_ordena_do_mais_recente_para_o_mais_antigo(client, usuario_id):
    client.post("/api/diario/registro", json=registro(usuario_id, data="2026-06-01"))
    client.post("/api/diario/registro", json=registro(usuario_id, data="2026-06-03"))
    client.post("/api/diario/registro", json=registro(usuario_id, data="2026-06-02"))

    datas = [d["data"] for d in client.get(f"/api/diario/{usuario_id}").json()["registros"]]
    assert datas == ["2026-06-03", "2026-06-02", "2026-06-01"]


def test_resumo_sem_objetivo_ativo_retorna_404(client):
    novo_id = client.post("/api/usuarios", json={
        **USUARIO_VALIDO, "email": "sem-objetivo@exemplo.com"
    }).json()["id"]

    assert client.get(f"/api/diario/{novo_id}").status_code == 404
```

- [ ] **Step 2: Rodar e confirmar que falha**

Run: `cd backend && pytest tests/test_diario_api.py -v`
Expected: FAIL com `405 Method Not Allowed` ou `404` — a rota GET ainda não existe

- [ ] **Step 3: Implementar os schemas**

Acrescentar em `backend/app/schemas/diario.py`:

```python
from app.domain.enums import TipoObjetivo


class ComparativoDia(BaseModel):
    data: date
    peso_kg: float
    consumido_kcal: float
    meta_kcal: float
    diferenca_kcal: float
    aderencia_percentual: float
    macros_consumidos: MacrosLidos
    macros_meta: MacrosLidos


class DiarioResumo(BaseModel):
    usuario_id: int
    objetivo: TipoObjetivo
    meta_kcal: float
    registros: list[ComparativoDia]
```

- [ ] **Step 4: Implementar o service**

Acrescentar em `backend/app/services/diario_service.py`:

```python
from app.schemas.diario import ComparativoDia, DiarioResumo
from app.schemas.perfil import MacrosLidos
from app.services import perfil_service


def resumo(db: Session, usuario_id: int) -> DiarioResumo:
    """Junta cada dia registrado com a meta vigente do usuário."""
    usuario = usuario_service.buscar_usuario(db, usuario_id)
    objetivo = perfil_service.objetivo_ativo(db, usuario.id)

    macros_meta = db.scalar(
        select(Macronutrientes).where(
            Macronutrientes.objetivo_id == objetivo.id,
            Macronutrientes.tipo == TipoMacro.META,
        )
    )

    linhas = db.execute(
        select(RegistroDiario, Macronutrientes)
        .outerjoin(
            Macronutrientes,
            (Macronutrientes.registro_diario_id == RegistroDiario.id)
            & (Macronutrientes.tipo == TipoMacro.CONSUMO),
        )
        .where(RegistroDiario.usuario_id == usuario.id)
        .order_by(RegistroDiario.data.desc())
    ).all()

    zerado = MacrosLidos(proteina_g=0, carboidrato_g=0, gordura_g=0)
    registros = [
        ComparativoDia(
            data=registro.data,
            peso_kg=registro.peso_kg,
            consumido_kcal=registro.calorias_kcal,
            meta_kcal=objetivo.meta_kcal,
            diferenca_kcal=round(registro.calorias_kcal - objetivo.meta_kcal, 2),
            aderencia_percentual=round(registro.calorias_kcal / objetivo.meta_kcal * 100, 2),
            macros_consumidos=MacrosLidos.model_validate(macros) if macros else zerado,
            macros_meta=MacrosLidos.model_validate(macros_meta) if macros_meta else zerado,
        )
        for registro, macros in linhas
    ]

    return DiarioResumo(
        usuario_id=usuario.id,
        objetivo=objetivo.tipo,
        meta_kcal=objetivo.meta_kcal,
        registros=registros,
    )
```

- [ ] **Step 5: Implementar a rota**

Acrescentar em `backend/app/api/routers/diario.py`:

```python
from app.schemas.diario import DiarioResumo


@router.get("/{usuario_id}", response_model=DiarioResumo)
def resumo(usuario_id: int, db: Session = Depends(get_db)) -> DiarioResumo:
    """Lista os dias registrados comparados com a meta vigente, do mais recente ao mais antigo."""
    return diario_service.resumo(db, usuario_id)
```

- [ ] **Step 6: Rodar e confirmar que passa**

Run: `cd backend && pytest -v`
Expected: 46 passed

- [ ] **Step 7: Commit**

```bash
git add backend/
git commit -m "feat: adiciona GET /api/diario/{usuario_id} com comparativo meta vs consumo"
```

---

### Task 11: Documentação acadêmica e coleta de evidências

**Files:**
- Create: `backend/README.md`, `docs/backend/18-modelo-de-dados.md`,
  `docs/backend/22-2-implementacao-backend.md`, `docs/backend/evidencias/` (diretório)
- Modify: `CLAUDE.md` (acrescentar a seção do backend)

**Interfaces:**
- Consumes: tudo. Nenhum código novo — esta task transforma o que existe nas seções
  18.1, 18.2 e 22.2 do documento acadêmico.

- [ ] **Step 1: Escrever o `backend/README.md`**

Deve conter, nesta ordem: pré-requisitos (Python 3.12+, PostgreSQL 16+), os comandos de
criação dos bancos (copiar da seção "Preparação do ambiente" deste plano), como criar o
venv e instalar, `cp .env.example .env`, `alembic upgrade head`, `uvicorn app.main:app --reload`,
`pytest -v`, e a URL do Swagger (`http://127.0.0.1:8000/docs`).

- [ ] **Step 2: Gerar o diagrama do banco para a seção 18.1**

```bash
cd backend && source .venv/bin/activate
psql "postgresql://power:power@localhost:5432/power_routine" -c "\d usuario"        > ../docs/backend/evidencias/schema-usuario.txt
psql "postgresql://power:power@localhost:5432/power_routine" -c "\d objetivo"       > ../docs/backend/evidencias/schema-objetivo.txt
psql "postgresql://power:power@localhost:5432/power_routine" -c "\d registro_diario" > ../docs/backend/evidencias/schema-registro-diario.txt
psql "postgresql://power:power@localhost:5432/power_routine" -c "\d macronutrientes" > ../docs/backend/evidencias/schema-macronutrientes.txt
```

- [ ] **Step 3: Escrever `docs/backend/18-modelo-de-dados.md`**

Duas subseções:

**18.1 — Modelo relacional.** O diagrama abaixo, a descrição de cada tabela com tipos e
constraints (copiar dos arquivos gerados no Step 2), e a justificativa das três decisões
de modelagem: (a) `data_nascimento` em vez de `idade`; (b) snapshot de `tmb_kcal/get_kcal/
meta_kcal` em `Objetivo`, preservando o histórico da prescrição; (c) `Macronutrientes`
com discriminador, permitindo o comparativo meta vs. consumo em uma consulta.

```mermaid
erDiagram
    USUARIO ||--o{ OBJETIVO : possui
    USUARIO ||--o{ REGISTRO_DIARIO : registra
    OBJETIVO ||--o| MACRONUTRIENTES : "meta"
    REGISTRO_DIARIO ||--o| MACRONUTRIENTES : "consumo"
```

**18.2 — Pipeline de persistência e validação.** As três camadas, com o exemplo concreto
de um `peso_kg` inválido sendo barrado em cada uma:

| Camada | Onde | O que barra | Resposta |
|---|---|---|---|
| Pydantic | `app/schemas/` | `peso_kg` fora de (20, 400); enum inválido; data futura | 422 |
| Service | `app/services/` | usuário inexistente; meta calórica insuficiente | 404 / 422 |
| PostgreSQL | `app/models/` | `CHECK`, `UNIQUE`, FK, discriminador de macros | 409 |

Descrever a transação: `get_db` abre a sessão, o service usa `flush()` para obter IDs, o
commit acontece uma única vez no fim da requisição, e qualquer exceção dispara rollback.

- [ ] **Step 4: Coletar as evidências da seção 22.2**

Salvar em `docs/backend/evidencias/`:

1. `swagger-visao-geral.png` — `http://127.0.0.1:8000/docs` com as três tags expandidas
2. `swagger-perfil-calcular.png` — o "Try it out" de `POST /api/perfil/calcular` com o JSON de resposta
3. `swagger-diario-registro.png` — idem para `POST /api/diario/registro`
4. `swagger-diario-resumo.png` — o `GET /api/diario/{usuario_id}` mostrando o comparativo
5. `pytest-verde.png` — a saída de `pytest -v` com todos os testes passando
6. `codigo-calculos.png` — `app/services/calculos.py` aberto no editor
7. `codigo-macronutrientes.png` — `app/models/macronutrientes.py`, destacando o `CHECK`

- [ ] **Step 5: Escrever `docs/backend/22-2-implementacao-backend.md`**

Quatro partes:

1. **Árvore de pastas** — colar a árvore da seção "File Structure" deste plano, com a
   frase que explica a fronteira: `services/calculos.py` não importa FastAPI nem SQLAlchemy.
2. **Serviços desenvolvidos** — uma tabela com `calculos.py`, `usuario_service.py`,
   `perfil_service.py`, `diario_service.py` e a responsabilidade de cada um.
3. **Regras de negócio em código** — as fórmulas da spec ao lado do trecho de código que
   as implementa, e as três decisões de negócio: proteína e gordura fixadas antes do
   carboidrato; recálculo desativa em vez de apagar; registro diário é idempotente por dia.
4. **Evidências** — inserir as sete imagens do Step 4 com legenda.

- [ ] **Step 6: Acrescentar a seção do backend ao `CLAUDE.md` da raiz**

Depois da seção "Architecture" existente, acrescentar:

```markdown
## Backend (`backend/`)

API FastAPI + SQLAlchemy + PostgreSQL. Ver `backend/README.md` para subir o ambiente.

- `app/services/calculos.py` — regras de negócio **puras** (Harris-Benedict, GET, meta,
  macros). Não importa FastAPI nem SQLAlchemy; é testável sem banco. Nunca coloque acesso
  a dados aqui.
- Uma transação por requisição: `get_db` faz o commit, os services só fazem `flush()`.
- Erros de domínio (`app/domain/erros.py`) viram HTTP em `app/api/handlers.py` —
  routers não têm `try/except`.
- Rodar: `cd backend && pytest -v`. Um único teste: `pytest tests/test_calculos.py::test_tmb_masculino -v`.
```

- [ ] **Step 7: Commit**

```bash
git add backend/README.md docs/backend/ CLAUDE.md
git commit -m "docs: adiciona secoes 18.1, 18.2 e 22.2 com evidencias do backend"
```

---

## Self-Review

**Cobertura da spec:**

| Requisito da spec | Task |
|---|---|
| §3.1 Idade derivada | 2 |
| §3.2 TMB Harris-Benedict | 2 |
| §3.3 GET por nível de atividade | 3 |
| §3.4 Meta calórica por objetivo | 3 |
| §3.5 Macros + regra de borda | 4 |
| §4 Modelo relacional e integridade | 5, 6 |
| §5 Endpoints | 7, 8, 9, 10 |
| §6 Pipeline de validação (3 camadas) | 7 (handlers), 5 (transação), 6 (CHECKs) |
| §7 Contrato com o frontend | documentado na spec; a mudança é do frontend |
| 18.1 / 18.2 / 22.2 | 11 |

**Riscos conhecidos:**

- **Python 3.14** — wheels de `psycopg`/`SQLAlchemy` podem não existir. Use 3.12.
- **`test_le_usuario_com_idade_derivada`** compara com `>= 25` porque a idade depende da
  data em que o teste roda. É proposital: as asserções exatas de idade estão em
  `test_calculos.py`, que injeta `hoje`.
- **`aderencia_percentual`** divide por `objetivo.meta_kcal`. Não há divisão por zero
  porque `calcular_macros` já falha antes disso com meta insuficiente, mas se algum dia
  a meta puder ser 0, esta é a linha a proteger.

---

## Execution Handoff

Plano salvo. Duas formas de executar:

1. **Subagent-Driven (recomendada)** — um subagente novo por task, com revisão entre elas.
   Peça: *"execute este plano com superpowers:subagent-driven-development"*.
2. **Inline** — executar as tasks nesta sessão em lotes, com checkpoints.
   Peça: *"execute este plano com superpowers:executing-plans"*.
