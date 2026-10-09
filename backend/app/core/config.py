from pydantic import field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Configuracao da aplicacao, lida de variaveis de ambiente ou do arquivo .env."""

    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    database_url: str
    # Opcional: so o pytest usa. Em producao (Render) nao existe banco de teste.
    test_database_url: str | None = None

    # Origens que o navegador deixa chamar a API. Uma origem e esquema + host
    # (+ porta): o caminho do GitHub Pages (/projeto-integrador-power-routine/)
    # nao faz parte dela. Em variavel de ambiente, CORS_ORIGINS e uma lista JSON.
    cors_origins: list[str] = ["https://felipeatorres006.github.io"]
    # Desenvolvimento local em qualquer porta (http.server, Live Server...).
    cors_origin_regex: str = r"^http://(localhost|127\.0\.0\.1)(:\d+)?$"

    @field_validator("database_url", "test_database_url")
    @classmethod
    def usar_driver_psycopg(cls, url: str | None) -> str | None:
        """Neon e Render entregam `postgresql://` ou `postgres://`; sem o `+psycopg`
        o SQLAlchemy procuraria o psycopg2, que nao esta instalado."""
        if url is None:
            return None
        for prefixo in ("postgres://", "postgresql://"):
            if url.startswith(prefixo):
                return "postgresql+psycopg://" + url.removeprefix(prefixo)
        return url


settings = Settings()
