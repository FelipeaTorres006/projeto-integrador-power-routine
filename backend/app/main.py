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

# O frontend estatico e servido de outra origem (file:// ou http.server). Escopo
# academico sem autenticacao nem cookie, entao nao ha credencial a proteger.
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
