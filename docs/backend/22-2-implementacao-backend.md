# 22.2 Implementação do backend

## Árvore de pastas

```
backend/
├─ app/
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
│  │  ├─ calculos.py               # ← regras de negócio puras
│  │  ├─ usuario_service.py
│  │  ├─ perfil_service.py
│  │  └─ diario_service.py
│  └─ api/
│     ├─ handlers.py                # exceção de domínio -> resposta HTTP, um lugar só
│     └─ routers/
│        ├─ usuarios.py
│        ├─ perfil.py
│        └─ diario.py
├─ alembic/                        # migrations versionadas
├─ tests/
│  ├─ conftest.py
│  ├─ test_calculos.py             # unitários, sem banco
│  ├─ test_handlers.py
│  ├─ test_config.py
│  ├─ test_cors.py               # CORS do app real, sem banco
│  ├─ test_models_usuario.py
│  ├─ test_models_relacional.py
│  ├─ test_usuarios_api.py
│  ├─ test_perfil_api.py
│  └─ test_diario_api.py
├─ alembic.ini
├─ requirements.txt
└─ .env.example
```

### A fronteira arquitetural — e a prova, não só a alegação

`app/services/calculos.py` **não importa nada de FastAPI nem de SQLAlchemy**. É
código Python puro: recebe números e enums, devolve números e um dataclass
(`Macros`, `ResultadoPerfil`). Nenhuma linha desse arquivo sabe que existe um
banco de dados ou um servidor HTTP. Essa fronteira é o que permite testar as
fórmulas de Harris-Benedict, GET, meta calórica e macronutrientes isoladamente —
`tests/test_calculos.py` instancia as funções diretamente, sem cliente HTTP, sem
sessão de banco, sem fixture de banco de dados.

A alegação de que "as fórmulas rodam sem banco e sem servidor" é fácil de fazer e
fácil de deixar sem prova. A prova usada aqui: apontar `TEST_DATABASE_URL` para
uma porta morta (`localhost:59999`, onde nada está escutando) e rodar a suite
inteira.

```bash
# backend/.env, TEST_DATABASE_URL apontando para uma porta sem nada escutando
.venv/bin/python -m pytest -v
```

Resultado medido nesta árvore:

```
25 passed, 2 warnings, 60 errors in 11.02s
```

Os 25 testes que passam pertencem a exatamente três arquivos: `test_calculos.py`,
`test_config.py` e `test_handlers.py` — os únicos que não dependem de uma conexão
de banco. Os 60 erros são todos `sqlalchemy.exc.OperationalError` (conexão
recusada), disparados pelos testes que criam sessão de banco (`test_usuarios_api.py`,
`test_perfil_api.py`, `test_diario_api.py`, `test_models_usuario.py`,
`test_models_relacional.py`). O ponto de falha é a *conexão*, não a lógica: a
suite pura roda até o fim, verde, sem que a porta morta a afete em nada. É a
mesma prova que T5 fez, repetida nesta árvore — os números aqui (25/60) são
diferentes dos de T5 porque a suite cresceu de 6 testes puros para 25 ao longo
das tasks seguintes, mas a propriedade que importa (o conjunto puro não muda com
o banco fora do ar) se mantém idêntica.

## Serviços desenvolvidos

| Módulo | Responsabilidade |
|---|---|
| `app/services/calculos.py` | Regras de negócio puras: idade, TMB (Harris-Benedict), GET, meta calórica, macronutrientes. Sem I/O. |
| `app/services/usuario_service.py` | Cria e busca `Usuario`; deriva idade a partir da data de nascimento. |
| `app/services/perfil_service.py` | Orquestra `calcular_perfil` e congela o resultado como o novo `Objetivo` ativo; desativa (nunca apaga) o objetivo anterior. |
| `app/services/diario_service.py` | Registra (upsert idempotente) o dia do usuário; monta o comparativo dia-a-dia contra a meta vigente (`resumo`). |

## Regras de negócio em código

### 3.1 — Idade derivada

```python
def calcular_idade(data_nascimento: date, hoje: date) -> int:
    idade = hoje.year - data_nascimento.year
    if (hoje.month, hoje.day) < (data_nascimento.month, data_nascimento.day):
        idade -= 1
    return idade
```

`hoje` é parâmetro, não `date.today()` direto — o que torna a função determinística
e testável em qualquer data, sem mock de relógio.

### 3.2 — TMB (Harris-Benedict revisada)

```
Masculino: 88.362 + (13.397 × peso_kg) + (4.799 × altura_cm) − (5.677 × idade)
Feminino:  447.593 + (9.247 × peso_kg) + (3.098 × altura_cm) − (4.330 × idade)
```

```python
_COEFICIENTES_TMB = {
    Sexo.MASCULINO: (88.362, 13.397, 4.799, 5.677),
    Sexo.FEMININO: (447.593, 9.247, 3.098, 4.330),
}

def calcular_tmb(sexo, peso_kg, altura_cm, idade) -> float:
    base, c_peso, c_altura, c_idade = _COEFICIENTES_TMB[sexo]
    tmb = base + (c_peso * peso_kg) + (c_altura * altura_cm) - (c_idade * idade)
    return round(tmb, 2)
```

### 3.3 — GET (Gasto Energético Total)

```python
_FATORES_ATIVIDADE = {
    NivelAtividade.SEDENTARIO: 1.2, NivelAtividade.LEVE: 1.375,
    NivelAtividade.MODERADO: 1.55, NivelAtividade.INTENSO: 1.725,
    NivelAtividade.MUITO_INTENSO: 1.9,
}

def calcular_get(tmb, nivel) -> float:
    return round(tmb * _FATORES_ATIVIDADE[nivel], 2)
```

### 3.4 — Meta calórica por objetivo

```python
_AJUSTES_OBJETIVO = {
    TipoObjetivo.EMAGRECER: 0.80, TipoObjetivo.MANTER: 1.00,
    TipoObjetivo.GANHAR_MASSA: 1.15,
}

def calcular_meta_calorica(get, objetivo) -> float:
    return round(get * _AJUSTES_OBJETIVO[objetivo], 2)
```

### 3.5 — Macronutrientes, com a regra de borda

```python
def calcular_macros(meta_kcal, peso_kg, objetivo) -> Macros:
    proteina_g = round(peso_kg * _PROTEINA_G_POR_KG[objetivo], 2)
    gordura_kcal = meta_kcal * _PERCENTUAL_GORDURA
    gordura_g = round(gordura_kcal / KCAL_POR_GRAMA_GORDURA, 2)

    carboidrato_kcal = meta_kcal - (proteina_g * KCAL_POR_GRAMA_PROTEINA) - gordura_kcal
    if carboidrato_kcal < 0:
        raise RegraDeNegocioError(
            "meta calorica insuficiente: proteina e gordura ja excedem as "
            f"calorias disponiveis ({meta_kcal} kcal para {peso_kg} kg)"
        )
    carboidrato_g = round(carboidrato_kcal / KCAL_POR_GRAMA_CARBOIDRATO, 2)
    return Macros(proteina_g=proteina_g, carboidrato_g=carboidrato_g, gordura_g=gordura_g)
```

**Exemplo numérico real** (medido via Swagger, corpo abaixo): usuário masculino
nascido em `2001-01-01` (25 anos em 2026), `peso_kg=80`, `altura_cm=180`,
`nivel_atividade=moderado`, `objetivo=emagrecer`.

```
tmb_kcal  = 1882.02
get_kcal  = 2917.13   (1882.02 × 1.55)
meta_kcal = 2333.70   (2917.13 × 0.80)

proteina_g    = 144.00    (80 × 1.8)
gordura_g     = 64.82     (2333.70 × 0.25 / 9 = 583.425 / 9 = 64.825, arredondado por round() a 64.82)
carboidrato_g = 293.57    ((2333.70 − 576 − 583.425) / 4)
```

`gordura_g = 64.82`, não `64.83` — o valor exato que sai do `round()` do Python
sobre `583.425 / 9`, medido nesta árvore e reproduzido de forma idêntica no
Swagger (ver figura `swagger-perfil-calcular.png`, abaixo) e no `GET` do dia
seguinte (`swagger-diario-resumo.png`).

### Três decisões de negócio

**1. Proteína e gordura fixadas antes do carboidrato.** A ordem em
`calcular_macros` não é arbitrária: proteína é uma função linear do peso corporal
(regra fisiológica), gordura é uma fração fixa da meta calórica, e o carboidrato
absorve o que sobra. Se a ordem fosse invertida — carboidrato calculado antes —
não haveria como aplicar a "regra de borda" (§3.5): o erro só é detectável depois
que se sabe quanto sobrou para o carboidrato.

**2. Recalcular desativa o objetivo anterior, nunca apaga.**
`perfil_service.calcular_e_salvar` marca `anterior.ativo = False` em vez de
`db.delete(anterior)`. A tabela `objetivo` acumula o histórico completo de
prescrições do usuário; `GET /api/diario/{usuario_id}` sempre lê o objetivo com
`ativo = True` (garantido pelo índice único parcial
`ix_objetivo_um_ativo_por_usuario`), nunca um valor recalculado na leitura.
Consequência documentada: comparar um dia antigo contra a meta *vigente* (não a
que valia naquele dia) significa que recalcular o perfil reescreve
retroativamente a nota de todo o histórico já registrado — medido por T10
(`meta_kcal` de um dia passou de `2333.7` para `3354.7` só por trocar o
objetivo, sem tocar nos registros diários).

**3. Registro diário é idempotente por dia.**
`diario_service.registrar` faz upsert por `(usuario_id, data)`: a segunda
chamada para o mesmo dia reutiliza a mesma linha de `registro_diario` e a mesma
linha de `macronutrientes` (tipo `consumo`), com o mesmo `id`, em vez de duplicar
ou de recusar com 409. É substituição total do dia, não *merge* — um campo
omitido no corpo da segunda chamada volta ao valor padrão (`observacoes` viraria
`None`), então o cliente precisa sempre enviar o dia inteiro.

## Configuração de CORS

### O problema: duas origens diferentes

O frontend do Power Routine é servido pelo GitHub Pages, em
`https://felipeatorres006.github.io/projeto-integrador-power-routine/`. A API roda
no Render, em `https://power-routine-api-wcq1.onrender.com`. Para o navegador,
são **origens diferentes**, porque uma origem é a combinação de esquema, domínio e
porta, e os domínios aqui não coincidem. O caminho
`/projeto-integrador-power-routine/` não faz parte da origem.

Pela **política de mesma origem** (*same-origin policy*), o navegador não entrega
ao JavaScript de uma página a resposta de uma requisição feita para outra origem,
a menos que o servidor diga explicitamente que confia nela. Esse mecanismo de
autorização é o **CORS** (*Cross-Origin Resource Sharing*). Sem ele, todas as
chamadas `fetch` do `app.js` falham com erro de CORS no console, mesmo com a API
respondendo normalmente.

O fluxo tem duas etapas:

1. **Preflight.** Antes de um `POST` com `Content-Type: application/json`, o
   navegador envia sozinho um `OPTIONS` com os cabeçalhos `Origin`,
   `Access-Control-Request-Method` e `Access-Control-Request-Headers`,
   perguntando se aquela origem pode fazer aquele tipo de requisição.
2. **Requisição real.** Só acontece se a resposta do preflight trouxer
   `Access-Control-Allow-Origin` com a origem da página. A resposta da requisição
   real também precisa trazer esse cabeçalho para o JavaScript conseguir lê-la.

### A configuração no FastAPI

Na primeira versão, a API aceitava qualquer origem (`allow_origins=["*"]`). Nesta
fase, com a API publicada na internet, a autorização passou a ser uma **lista
explícita**: só o GitHub Pages e o ambiente de desenvolvimento local.

`app/main.py`:

```python
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins,
    allow_origin_regex=settings.cors_origin_regex,
    allow_methods=["GET", "POST"],
    allow_headers=["Content-Type"],
)
```

`app/core/config.py`:

```python
cors_origins: list[str] = ["https://felipeatorres006.github.io"]
cors_origin_regex: str = r"^http://(localhost|127\.0\.0\.1)(:\d+)?$"
```

Cada escolha, e por quê:

| Parâmetro | Valor | Motivo |
|---|---|---|
| `allow_origins` | só o GitHub Pages | Uma página em qualquer outro domínio não consegue ler as respostas da API pelo navegador. Configurável pela variável de ambiente `CORS_ORIGINS`, sem alterar código. |
| `allow_origin_regex` | `localhost` e `127.0.0.1`, em qualquer porta | Desenvolvimento local (`python3 -m http.server`, Live Server…) sem precisar listar cada porta. A expressão é ancorada (`^…$`), então `http://localhost.site-malicioso.com` **não** casa. |
| `allow_methods` | `GET`, `POST` | São os únicos métodos que a API expõe. Um preflight pedindo `DELETE` é recusado com 400. |
| `allow_headers` | `Content-Type` | O único cabeçalho não simples que o frontend envia (`application/json`). |
| `allow_credentials` | omitido (falso) | A API não tem cookie nem autenticação, então o navegador não precisa enviar credenciais entre origens. |

Uma página aberta direto do disco (`file://`) tem origem `null` e é recusada.
Para rodar o frontend localmente, ele precisa ser servido por HTTP.

O CORS é uma proteção **do navegador**. Ele impede que outro site use o navegador
do visitante para ler a API, mas não impede chamadas feitas fora do navegador
(`curl`, Swagger, scripts). Essa diferença é esperada: a API é pública por decisão
de escopo (sem autenticação), e o CORS limita *quais páginas web* podem consumi-la.

### A prova: `tests/test_cors.py`

O teste importa o `app` real de `app.main`, com o mesmo middleware que vai para
produção, e não abre conexão com banco:

| Caso | Resultado esperado |
|---|---|
| Preflight de `https://felipeatorres006.github.io` | 200 e `access-control-allow-origin` ecoando a origem |
| Preflight de `http://localhost:5500`, `http://127.0.0.1:8080`, `http://localhost` | aceito |
| Preflight de `https://site-malicioso.com` | sem `access-control-allow-origin` |
| Preflight de `https://felipeatorres006.github.io.site-malicioso.com` | sem o cabeçalho (domínio que só *parece* o Pages) |
| Preflight de `http://localhost.site-malicioso.com` | sem o cabeçalho |
| Preflight de `null` (`file://`) | sem o cabeçalho |
| Preflight pedindo `DELETE` | 400 |
| `GET /api/saude` com `Origin` do Pages | 200 com o cabeçalho |
| Qualquer preflight | sem `access-control-allow-credentials` |

A mesma verificação foi repetida contra a API publicada:

```
$ curl -i -X OPTIONS https://power-routine-api-wcq1.onrender.com/api/usuarios \
    -H 'Origin: https://felipeatorres006.github.io' \
    -H 'Access-Control-Request-Method: POST' -H 'Access-Control-Request-Headers: content-type'
HTTP/2 200
access-control-allow-methods: GET, POST
access-control-allow-origin: https://felipeatorres006.github.io

$ curl -i -X OPTIONS https://power-routine-api-wcq1.onrender.com/api/usuarios \
    -H 'Origin: https://exemplo.com' -H 'Access-Control-Request-Method: POST'
HTTP/2 400
(sem access-control-allow-origin)
```

A suíte completa, com `test_cors.py` incluído, mede **100 passed** nesta fase.

## Publicação da API

| Camada | Onde | Plano |
|---|---|---|
| Frontend | GitHub Pages, branch `main` | gratuito |
| API | Render, Web Service `power-routine-api`, definido em `render.yaml` na raiz do repositório | gratuito |
| Banco | Neon, PostgreSQL 18, região AWS São Paulo | gratuito |

Três ajustes no backend tornaram esse arranjo possível:

- **A URL do Neon é aceita como vem.** O painel entrega `postgresql://…?sslmode=require`.
  Um validador em `Settings` troca o prefixo por `postgresql+psycopg://`, o driver
  instalado. Sem isso, o SQLAlchemy procuraria o `psycopg2`. Coberto em
  `tests/test_config.py`.
- **`pool_pre_ping=True` no engine** (`app/db/session.py`). O Neon suspende o
  banco após 5 minutos parado e encerra as conexões abertas. O ping descarta a
  conexão morta antes de usá-la. Sem ele, a primeira requisição depois de uma
  pausa responderia 500.
- **Migration no start do serviço.** O `startCommand` do Render é
  `alembic upgrade head && uvicorn …`. O comando de *pre-deploy* do Render é
  recurso pago, e `upgrade head` é idempotente: quando não há migration nova,
  não faz nada.

A connection string do banco fica só no painel do Render (`DATABASE_URL`) e no
`.env` local, que é ignorado pelo git. Nenhuma credencial está no repositório.

Limitação conhecida do plano gratuito: o serviço do Render "dorme" após 15 minutos
sem requisições, e a primeira chamada depois disso leva cerca de 1 minuto.

## Evidências

Nove figuras. As quatro primeiras são **capturas de tela reais**, tiradas
navegando o Swagger UI em `http://127.0.0.1:8000/docs` com a API rodando contra o
banco `power_routine`. As três últimas são **imagens renderizadas** — o conteúdo é
real (a saída literal de `pytest -v` e os dois arquivos-fonte tal como estão no
repositório), mas a imagem foi tipografada (Pygments para o código, uma página HTML
em estilo terminal para a saída do pytest) e fotografada no Chrome, em vez de
fotografada diretamente do terminal ou do editor. A legenda de cada figura diz qual
é qual. Se o professor exigir capturas reais dessas três, é só reabrir o terminal e
o editor e substituir os três arquivos — o restante do documento não muda.

**Figura 1 — captura real.** `swagger-visao-geral.png`: `http://127.0.0.1:8000/docs`
com as três tags (`usuarios`, `perfil`, `diario`) expandidas, mostrando todas as
rotas da API.

**Figura 2 — captura real.** `swagger-perfil-calcular.png`: "Try it out" de `POST
/api/perfil/calcular` com o corpo `{"usuario_id": 1, "peso_kg": 80,
"nivel_atividade": "moderado", "objetivo": "emagrecer"}` e a resposta 201 —
`meta_kcal=2333.7`, `gordura_g=64.82`, os mesmos números do exemplo numérico acima.

**Figura 3 — captura real.** `swagger-diario-registro.png`: "Try it out" de `POST
/api/diario/registro` registrando o dia `2026-06-01` do mesmo usuário, resposta 201
com `id=1`.

**Figura 4 — captura real.** `swagger-diario-resumo.png`: `GET
/api/diario/1`, depois de registrados dois dias (`2026-06-01` e `2026-06-02`),
mostrando o comparativo — cada dia com `consumido_kcal`, `meta_kcal`,
`diferenca_kcal` e `aderencia_percentual` ao lado da meta vigente.

**Figura 5 — imagem renderizada.** `pytest-verde.png`: saída literal de
`.venv/bin/python -m pytest -v` nesta árvore — **85 passed** — tipografada em
uma página HTML de estilo terminal e fotografada no Chrome. O número 85 é o que
esta invocação mediu; nenhum número deste documento vem do plano original (os
"Expected: N passed" ali estavam sistematicamente desatualizados, como cada task
do ciclo registrou ao rodar a suite de fato).

**Figura 6 — imagem renderizada.** `codigo-calculos.png`: `app/services/calculos.py`
com destaque de sintaxe via Pygments — o arquivo que sustenta o argumento da
fronteira arquitetural acima.

**Figura 7 — imagem renderizada.** `codigo-macronutrientes.png`:
`app/models/macronutrientes.py`, com o bloco do `CheckConstraint` que produz
`ck_macronutrientes_discriminador` (linhas 32–37) realçado — a evidência direta da
terceira decisão de modelagem da seção 18.1.

Os quatro dumps de schema (`schema-usuario.txt`, `schema-objetivo.txt`,
`schema-registro-diario.txt`, `schema-macronutrientes.txt`), saída literal de
`psql \d`, também estão em `docs/backend/evidencias/` e são citados na seção 18.1.

**Figuras 8 e 9 — capturas reais, com marcações.** Painel *Network* do Chrome
DevTools, a mesma interface aberta pelo F12, conectado ao frontend publicado no
GitHub Pages enquanto o fluxo cadastro → perfil → registro diário era executado.
As requisições, os status e o JSON são os do tráfego real com a API no Render. Os
retângulos e rótulos vermelhos foram desenhados depois, sobre a captura.

- `network-diario-200-headers.png` (Figura 8): aba *Headers* de
  `GET https://power-routine-api-wcq1.onrender.com/api/diario/3`, com
  **Status Code 200 OK**, `Access-Control-Allow-Origin: https://felipeatorres006.github.io`
  (o CORS da seção acima em funcionamento) e `Content-Type: application/json`.
- `network-diario-200-json.png` (Figura 9): aba *Preview* da mesma requisição,
  com o JSON do comparativo diário. Cada dia traz `consumido_kcal`, `meta_kcal`,
  `diferenca_kcal`, `aderencia_percentual` e os macros consumidos e da meta.
