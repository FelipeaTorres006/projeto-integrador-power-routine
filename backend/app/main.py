from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api.handlers import registrar_handlers
from app.api.routers import diario, perfil, usuarios
from app.core.config import settings

app = FastAPI(
    title="Power Routine API",
    version="1.0.0",
    description=(
        "API do projeto integrador Power Routine. Calcula TMB (Harris-Benedict), "
        "GET, meta calorica e macronutrientes, e registra o acompanhamento diario."
    ),
)

# O frontend (GitHub Pages) e a API (Render) moram em origens diferentes, entao o
# navegador so entrega a resposta ao JavaScript se a API autorizar a origem.
# Lista explicita em vez de "*": so o Pages e o localhost de desenvolvimento.
# Sem allow_credentials: a API nao tem cookie nem autenticacao.
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins,
    allow_origin_regex=settings.cors_origin_regex,
    allow_methods=["GET", "POST"],
    allow_headers=["Content-Type"],
)

registrar_handlers(app)
app.include_router(usuarios.router, prefix="/api")
app.include_router(perfil.router, prefix="/api")
app.include_router(diario.router, prefix="/api")


@app.get("/api/saude", tags=["infra"])
def saude() -> dict[str, str]:
    return {"status": "ok"}
