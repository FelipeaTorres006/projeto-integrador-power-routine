# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project

Power Routine — "projeto integrador" (academic capstone). A single-page nutrition app: static
frontend at the repo root (no build step, no package manager) talking to a FastAPI backend in
`backend/`. Deployed as: frontend on GitHub Pages (`main`, repo root), API on Render
(`render.yaml`, free plan), Postgres on Neon (free plan).

UI text, identifiers, and comments are in **Brazilian Portuguese** (`<html lang="pt-BR">`). Keep new
user-facing strings and DOM ids in Portuguese to match.

## Running the frontend

```bash
python3 -m http.server 5500         # then http://localhost:5500 — needs the API on :8000
```

`file://` no longer works end to end: its `Origin` is `null`, which the API's CORS rejects. Verify
changes by walking the flow: login → cadastro/perfil → dashboard → Diário → Progresso.

## Frontend architecture

Three files at the repo root:

- `index.html` — **all three screens exist in the DOM at once**, as sibling `<section class="view">`
  elements (`#view-login`, `#view-form`, `#view-dash`). Nothing is ever created or removed.
- `app.js` — the entire application. Loaded with a plain `<script>` at the end of `<body>`; listeners
  are registered at the top level, so every element it queries must already exist in `index.html`.
- `styles.css` — dark theme driven by CSS custom properties on `:root`. Use the variables rather
  than hardcoding colors.

### Navigation is CSS-class visibility, not routing

1. **Screens** — `goTo(viewId)` strips `.active` from every `.view` and sets it on the target.
2. **Dashboard tabs** — `.nav-item[data-tab]` buttons map to `.tab-content` panels by id; the click
   handler mirrors the same strip-then-set pattern and (re)loads data for Início/Progresso/Evolução.

### Talking to the API

`API_URL` (top of `app.js`) is `http://localhost:8000/api` when the page is served from
localhost/127.0.0.1, otherwise the Render URL. The flow is: `#infoForm` submit → `POST /usuarios` →
`POST /perfil/calcular` → dashboard; `#diarioForm` → `POST /diario/registro` → `GET /diario/{id}`.
The `<option value>`s of `#sexo`, `#nivel_atividade` and `#objetivo` must match the backend enums
(`backend/app/domain/enums.py`) exactly. `extrairErro` turns FastAPI error bodies (422 lists, 404/409
strings) into the message for `showToast`, the only user feedback channel.

`state` is in-memory only (no `localStorage`): a refresh drops `usuario_id`, though the data stays
in the database. Login (`#loginForm`) is cosmetic — there is no authentication anywhere.

`classificarMargem8Pct` classifies a day as inside/below/above the goal with a ±8% band, computed
client-side. Charts use Chart.js, the PDF report uses jsPDF; both and Font Awesome/Outfit come from
CDNs in `<head>`. Local images live in `img/`.

## Backend (`backend/`)

API FastAPI + SQLAlchemy + PostgreSQL. Ver `backend/README.md` para subir o ambiente
(inclui os comandos do container Docker — Postgres não é assumido como instalado
nativamente).

- `app/services/calculos.py` — regras de negócio **puras** (Harris-Benedict, GET, meta,
  macros). Não importa FastAPI nem SQLAlchemy; é testável sem banco. Nunca coloque acesso
  a dados aqui.
- Uma transação por requisição: `get_db` faz o commit, os services só fazem `flush()` —
  sem isso, uma violação de constraint só aparece no commit do `get_db`, com a resposta
  já iniciada, e vira 500 em vez de 404/409/422.
- Erros de domínio (`app/domain/erros.py`) viram HTTP em `app/api/handlers.py` —
  routers não têm `try/except`.
- `pytest` e `alembic` só rodam de **dentro** de `backend/`: `pytest.ini` fixa
  `pythonpath = .` e as configurações (`app/core/config.py`) resolvem `.env` pelo
  diretório de trabalho. Rodar da raiz do repositório não encontra nenhum dos dois.
- Rodar: `cd backend && .venv/bin/python -m pytest -v`. Um único teste:
  `cd backend && .venv/bin/python -m pytest tests/test_calculos.py::test_tmb_masculino -v`.
- Documentação acadêmica das seções 18, 22.2 e 22.3 em `docs/backend/` (evidências em `docs/backend/evidencias/`).
- CORS (`app/main.py`, configurado em `app/core/config.py`): só a origem do GitHub Pages
  e `localhost`/`127.0.0.1` em qualquer porta; provado em `tests/test_cors.py`. Uma
  origem nova de frontend precisa entrar em `cors_origins` (ou `CORS_ORIGINS` no Render).
- `DATABASE_URL` aceita a string do Neon como vem (`postgresql://…`); o validator troca o
  prefixo para `postgresql+psycopg://`. `TEST_DATABASE_URL` é opcional fora do pytest e
  precisa ser um database separado terminado em `_test` (o conftest apaga o schema).
