from app.core.config import settings


def test_settings_carrega_database_url():
    assert settings.database_url.startswith("postgresql+psycopg://")


def test_settings_carrega_test_database_url():
    assert settings.test_database_url.endswith("_test")
