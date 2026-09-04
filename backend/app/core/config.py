from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Configuracao da aplicacao, lida de variaveis de ambiente ou do arquivo .env."""

    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    database_url: str
    test_database_url: str


settings = Settings()
