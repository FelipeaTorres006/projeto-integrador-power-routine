# Spec — Backend Power Routine (API + Banco de Dados)

**Autor:** Felipe Antônio — Líder de Backend & Banco de Dados
**Data:** 2026-09-04
**Projeto:** Power Routine (projeto integrador)

---

## 1. Objetivo

Construir a API do Power Routine que transforma os dados corporais de um usuário em
uma prescrição nutricional (TMB, GET, meta calórica e macronutrientes) e registra o
acompanhamento diário, persistindo tudo em um banco relacional.

Entregáveis acadêmicos cobertos por esta spec:

| Seção do documento | Conteúdo |
|---|---|
| 18.1 | Modelo de dados relacional (Usuario, Objetivo, RegistroDiario, Macronutrientes) |
| 18.2 | Pipeline de persistência e validação |
| 22.2 | Implementação backend: árvore de pastas, serviços, regras de negócio, evidências |

## 2. Decisões tomadas

| Decisão | Escolha | Motivo |
|---|---|---|
| Framework | **FastAPI** | Gera Swagger UI em `/docs` automaticamente — as evidências da seção 22.2 saem prontas, sem configurar nada |
| Banco | **PostgreSQL** | Escolha do autor; permite usar recursos relacionais reais (CHECK, índices parciais) que rendem conteúdo para 18.1/18.2 |
| ORM | **SQLAlchemy 2.x** + Alembic | Migrations versionadas viram evidência do pipeline de persistência |
| Cálculos | **Escritos do zero** | Não existem no repositório hoje — `app.js` só tem IMC |
| `Macronutrientes` | **Tabela única com discriminador** `tipo ∈ {meta, consumo}` | Permite o gráfico "meta vs. realizado" com uma tabela só |
| Autenticação | **Fora de escopo** | `usuario_id` viaja no corpo da requisição; o login do frontend permanece cosmético |

## 3. Regras de negócio

### 3.1 Idade

Derivada de `Usuario.data_nascimento`, nunca armazenada como número. Idade é um valor
que envelhece; data de nascimento não.

### 3.2 TMB — Harris-Benedict revisada (Roza & Shizgal, 1984)

```
Masculino: 88.362 + (13.397 × peso_kg) + (4.799 × altura_cm) − (5.677 × idade)
Feminino:  447.593 + (9.247 × peso_kg) + (3.098 × altura_cm) − (4.330 × idade)
```

### 3.3 GET — Gasto Energético Total

`GET = TMB × fator_atividade`

| Nível | Fator |
|---|---|
| `sedentario` | 1.2 |
| `leve` | 1.375 |
| `moderado` | 1.55 |
| `intenso` | 1.725 |
| `muito_intenso` | 1.9 |

### 3.4 Meta calórica

`meta_kcal = GET × ajuste_objetivo`

| Objetivo | Ajuste |
|---|---|
| `emagrecer` | 0.80 (déficit de 20%) |
| `manter` | 1.00 |
| `ganhar_massa` | 1.15 (superávit de 15%) |

### 3.5 Macronutrientes

Ordem de cálculo — proteína e gordura são fixadas primeiro, carboidrato absorve o resto:

```
proteina_g    = peso_kg × (2.0 se ganhar_massa senão 1.8)
gordura_g     = (meta_kcal × 0.25) / 9
carboidrato_g = (meta_kcal − proteina_g×4 − meta_kcal×0.25) / 4
```

Densidades energéticas: proteína 4 kcal/g, carboidrato 4 kcal/g, gordura 9 kcal/g.

**Regra de borda:** se o carboidrato resultante for negativo (meta calórica baixa
demais para o peso), o cálculo falha com erro explícito em vez de devolver um valor
sem sentido.

## 4. Modelo relacional

```
Usuario (1) ──< (N) Objetivo (1) ──── (0..1) Macronutrientes [tipo=meta]
   │
   └──< (N) RegistroDiario (1) ──── (0..1) Macronutrientes [tipo=consumo]
```

**Regras de integridade exigidas:**

- `Usuario.email` único.
- No máximo **um** `Objetivo` com `ativo = true` por usuário (índice parcial).
- No máximo **um** `RegistroDiario` por `(usuario_id, data)`.
- `Macronutrientes` obedece ao discriminador: `tipo='meta'` exige `objetivo_id`
  preenchido e `registro_diario_id` nulo; `tipo='consumo'` exige o inverso.
  Garantido por `CHECK` no banco, não só na aplicação.
- Relação 1:1 de `Macronutrientes` com seu dono, por índice único parcial.

## 5. Endpoints

| Método | Rota | Responsabilidade |
|---|---|---|
| `POST` | `/api/usuarios` | Cria usuário (nome, email, sexo, data_nascimento, altura_cm) |
| `GET` | `/api/usuarios/{usuario_id}` | Lê usuário com idade derivada |
| `POST` | `/api/perfil/calcular` | Calcula TMB/GET/meta/macros, grava o `Objetivo` ativo e a meta de macros |
| `POST` | `/api/diario/registro` | Registra o dia (peso, calorias, macros consumidos); upsert por `(usuario_id, data)` |
| `GET` | `/api/diario/{usuario_id}` | Lista registros e compara consumo com a meta vigente |

## 6. Pipeline de validação (base da seção 18.2)

```
JSON → Pydantic (tipos, faixas, enums) → Router → Service (regra de negócio)
     → SQLAlchemy Model → Transação → COMMIT → Schema de resposta
```

Três camadas, cada uma com um papel distinto:

1. **Pydantic** — formato e faixa. `peso_kg > 0`, `altura_cm` entre 50 e 250,
   `objetivo` restrito ao enum. Falha vira HTTP 422 com corpo estruturado.
2. **Service** — regras que exigem contexto. Usuário existe? Já há objetivo ativo?
   O carboidrato ficou negativo? Falha vira 404 ou 422 com mensagem de domínio.
3. **Banco** — `NOT NULL`, `UNIQUE`, `CHECK`, FKs. Rede de segurança que não confia
   na aplicação. Falha vira 409.

Uma transação por requisição: commit no sucesso, rollback em qualquer exceção.

## 7. Contrato com o frontend (mudanças necessárias)

O formulário atual (`index.html` `#infoForm`) coleta **nome, idade, peso, altura,
objetivo**. A API precisa de três informações que o formulário ainda não pede:

| Campo | Por quê |
|---|---|
| `sexo` | Harris-Benedict tem fórmulas distintas por sexo — sem ele não há TMB |
| `nivel_atividade` | É o multiplicador que transforma TMB em GET |
| `data_nascimento` (no lugar de `idade`) | Idade passa a ser derivada |

Isso precisa ser combinado com quem cuida do frontend. Até lá, a API é testável
integralmente pelo Swagger.

## 8. Fora de escopo

Autenticação e sessão; recomendação de alimentos ou cardápio (o `gerarPlano()` do
frontend continua com strings fixas); deploy; frontend consumindo a API.
