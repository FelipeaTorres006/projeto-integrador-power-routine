# 22.3 Integração entre frontend e backend

O frontend e o backend do Power Routine estão integrados e publicados. A página
estática (HTML, CSS e JavaScript puro) consome a API REST em FastAPI por HTTPS, e
todos os dados exibidos no painel (metas, histórico, gráficos e classificação de
aderência) vêm do banco PostgreSQL, por meio da API.

## Arquitetura em produção

```
Navegador
   │  https://felipeatorres006.github.io/projeto-integrador-power-routine/
   ▼
GitHub Pages ── entrega index.html, styles.css, app.js
   │
   │  fetch() com JSON, por HTTPS, autorizado por CORS
   ▼
Render ── API FastAPI (power-routine-api-wcq1.onrender.com)
   │
   │  SQLAlchemy + psycopg, conexão com TLS
   ▼
Neon ── PostgreSQL 18 (AWS São Paulo)
```

As três camadas usam planos gratuitos e são independentes. O Pages publica a
branch `main` a cada push. O Render reconstrói a API a partir da mesma branch,
seguindo o `render.yaml`. O banco fica fora do Render para não expirar, porque o
Postgres gratuito do Render é apagado após 30 dias.

## Como o frontend encontra a API

O endereço da API é decidido em tempo de execução, no início do `app.js`:

```javascript
const API_URL = (window.location.hostname === "localhost" || window.location.hostname === "127.0.0.1")
  ? "http://localhost:8000/api"
  : "https://power-routine-api-wcq1.onrender.com/api";
```

O mesmo arquivo funciona sem alteração nos dois ambientes. Servido localmente, o
frontend fala com a API local, e no GitHub Pages fala com a API publicada.

## Fluxo de chamadas implementado

| Ação do usuário | Requisição | Resposta | O que o frontend faz com ela |
|---|---|---|---|
| Envia o formulário "Preencha seus dados" | `POST /api/usuarios` (nome, e-mail, sexo, data de nascimento, altura) | **201** + usuário com `id` | Guarda `usuario_id` no estado da página |
| (em seguida, automaticamente) | `POST /api/perfil/calcular` (`usuario_id`, peso, nível de atividade, objetivo) | **201** + TMB, GET, meta calórica e macros | Preenche os cartões do Início e o gráfico de macronutrientes |
| Registra um dia na aba "Registrar Dia" | `POST /api/diario/registro` (data, peso, calorias, proteína, carboidrato, gordura) | **201** | Recarrega o resumo e abre a aba Progresso |
| Abre Início ou Progresso, ou acabou de registrar | `GET /api/diario/{usuario_id}` | **200** + comparativo dia a dia | Monta o histórico, o status de aderência e os gráficos de calorias e de evolução do peso |

O cadastro e o cálculo do perfil formam uma única ação para o usuário: um envio
de formulário gera as duas chamadas em sequência. A tela só passa para o painel
quando as duas respondem com sucesso.

Os valores das listas do formulário (`masculino`/`feminino`, `sedentario` …
`muito_intenso`, `emagrecer`/`manter`/`ganhar_massa`) são exatamente os valores
dos enums do backend (`app/domain/enums.py`). Assim o JSON enviado é aceito sem
nenhuma conversão.

## Tratamento de erros

A API devolve erros em dois formatos: uma mensagem de texto (404 recurso
inexistente, 409 e-mail já cadastrado, 422 regra de negócio) ou uma lista de
campos inválidos (422 de validação do Pydantic). A função `extrairErro`, no
`app.js`, converte os dois formatos numa frase legível, como
`peso_kg: Input should be greater than 20`. O usuário vê essa frase no aviso
(*toast*) da tela. Falhas de rede ou respostas sem JSON viram
`Falha no servidor (status)`. O botão de envio fica desabilitado durante a
requisição para evitar cadastros duplicados.

## Classificação de aderência

Com o comparativo recebido de `GET /api/diario/{usuario_id}`, o frontend
classifica cada dia pelo limiar de ±8% sobre a meta:

| Aderência (consumo ÷ meta) | Status exibido |
|---|---|
| entre 92% e 108% | Dentro da Meta (verde) |
| abaixo de 92% | Abaixo da Meta (azul) |
| acima de 108% | Acima da Meta (vermelho) |

A aderência percentual vem calculada pela API (`aderencia_percentual`). O
frontend só aplica a faixa e escolhe a cor.

## Segurança da comunicação

- **HTTPS de ponta a ponta.** O Pages e o Render só servem por HTTPS, e a conexão
  da API com o Neon exige TLS (`sslmode=require`).
- **CORS restrito.** A API só autoriza o navegador a entregar respostas para
  páginas do GitHub Pages e do `localhost` (ver seção 22.2, "Configuração de
  CORS").
- **Credenciais fora do código.** A string de conexão do banco existe apenas como
  variável de ambiente no Render e no `.env` local, que é ignorado pelo git.

## Evidência

As Figuras 8 e 9 da seção 22.2 mostram o painel *Network* do DevTools com o
frontend publicado. `GET /api/diario/{id}` responde **200 OK**, com o cabeçalho
`Access-Control-Allow-Origin: https://felipeatorres006.github.io` e o JSON do
comparativo diário. Na mesma captura aparecem as respostas **201** das chamadas
de cadastro, cálculo de perfil e registro diário.

## Limitações conhecidas

- **Sem login.** A tela de login é ilustrativa, uma decisão de escopo. O
  `usuario_id` vive só na memória da página, então recarregar a página volta para
  o início, embora os dados continuem no banco.
- **Primeira requisição lenta.** No plano gratuito, a API "dorme" após 15 minutos
  sem uso, e a primeira requisição depois disso leva cerca de 1 minuto.
