# Power Routine — Backend

API em FastAPI + PostgreSQL para o projeto integrador Power Routine. Calcula TMB
(Harris-Benedict), GET, meta calórica e macronutrientes, e registra o
acompanhamento diário do usuário comparado com a meta vigente.

Tudo neste README parte de dentro do diretório `backend/` — `pytest.ini` fixa
`pythonpath = .` e as configurações são lidas de um `.env` resolvido pelo
diretório de trabalho (`SettingsConfigDict(env_file=".env")`). Rodar `pytest`
ou `alembic` da raiz do repositório não encontra nem o `pytest.ini` nem o
`.env`.

## Pré-requisitos

- Python 3.12 ou 3.13
- Docker (recomendado) **ou** um PostgreSQL 16 já instalado e acessível

Este ambiente não tinha PostgreSQL instalado nativamente — o banco do ciclo de
desenvolvimento roda inteiro dentro de um container Docker chamado
`power-routine-db`. É o caminho documentado abaixo; instalar o PostgreSQL via
`sudo apt install postgresql` é uma alternativa possível, mas não é o que foi
usado nem testado aqui.

## 1. Banco de dados (container Docker)

Se o Docker Desktop ainda não estiver de pé:

```bash
systemctl --user start docker-desktop
```

Subir o container (uma vez só; nas próximas vezes basta `docker start`):

```bash
docker run --name power-routine-db \
  -e POSTGRES_USER=power \
  -e POSTGRES_PASSWORD=power \
  -e POSTGRES_DB=power_routine \
  -p 5432:5432 \
  -d postgres:16

# nas próximas vezes, se o container já existir mas estiver parado:
docker start power-routine-db
```

Criar o banco de teste (nome com sufixo `_test` no **fim** — é o que
`tests/test_config.py` exige):

```bash
docker exec power-routine-db psql -U power -d postgres \
  -c "CREATE DATABASE power_routine_test"
```

Verificar que o container está respondendo:

```bash
docker exec power-routine-db psql -U power -d power_routine -c "\dt"
```

## 2. Ambiente Python

A partir de `backend/`:

```bash
cp .env.example .env        # obrigatório antes do primeiro run; .env é gitignorado
python3.12 -m venv .venv
.venv/bin/pip install -r requirements.txt
```

Edite `.env` se os nomes de banco ou credenciais forem diferentes do padrão
(`power`/`power`, banco `power_routine`, banco de teste
`power_routine_test`):

```
DATABASE_URL=postgresql+psycopg://power:power@localhost:5432/power_routine
TEST_DATABASE_URL=postgresql+psycopg://power:power@localhost:5432/power_routine_test
```

## 3. Migrations

Ainda dentro de `backend/`:

```bash
.venv/bin/python -m alembic upgrade head
```

## 4. Rodar a API

```bash
.venv/bin/python -m uvicorn app.main:app --reload
```

Swagger UI (documentação interativa, com "Try it out"):
http://127.0.0.1:8000/docs

Verificação rápida:

```bash
curl http://127.0.0.1:8000/api/saude
# {"status":"ok"}
```

## 5. Rodar os testes

```bash
.venv/bin/python -m pytest -v
```

`pytest` usa `TEST_DATABASE_URL` (nunca `DATABASE_URL`) — os testes de banco
não tocam nos dados que a demo do Swagger produziu. Ver
`docs/backend/22-2-implementacao-backend.md` para a contagem real de testes
medida nesta árvore e para a prova de que os testes de `test_calculos.py`
passam mesmo sem nenhum banco no ar.

## Rotas

| Método | Rota | Sucesso |
|---|---|---|
| `POST` | `/api/usuarios` | 201 |
| `GET` | `/api/usuarios/{usuario_id}` | 200 |
| `POST` | `/api/perfil/calcular` | 201 |
| `POST` | `/api/diario/registro` | 201 |
| `GET` | `/api/diario/{usuario_id}` | 200 |
| `GET` | `/api/saude` | 200 |

Detalhes de cada rota (erros possíveis, corpos de exemplo, semântica) estão no
Swagger UI e em `docs/backend/22-2-implementacao-backend.md`.

## Documentação acadêmica

- `docs/backend/18-modelo-de-dados.md` — modelo relacional (18.1) e pipeline
  de validação (18.2).
- `docs/backend/22-2-implementacao-backend.md` — arquitetura, serviços, regras
  de negócio e evidências (22.2).
- `docs/backend/evidencias/` — capturas de tela, dumps de schema e imagens
  renderizadas que sustentam os dois documentos acima.
