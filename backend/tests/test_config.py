import pytest

from app.core.config import Settings, settings



def test_settings_carrega_database_url():
    assert settings.database_url.startswith("postgresql+psycopg://")


def test_settings_carrega_test_database_url():
    assert settings.test_database_url.endswith("_test")


@pytest.mark.parametrize(
    "url",
    [
        "postgresql://u:s@ep-exemplo.sa-east-1.aws.neon.tech/power_routine?sslmode=require",
        "postgres://u:s@ep-exemplo.sa-east-1.aws.neon.tech/power_routine?sslmode=require",
    ],
)
def test_database_url_do_neon_e_normalizada_para_psycopg(url):
    """O Neon e o Render entregam `postgresql://` ou `postgres://`; sem o
    `+psycopg`, o SQLAlchemy procuraria o driver psycopg2, que nao esta instalado."""
    s = Settings(database_url=url, _env_file=None)
    assert s.database_url == (
        "postgresql+psycopg://u:s@ep-exemplo.sa-east-1.aws.neon.tech/power_routine?sslmode=require"
    )


def test_database_url_ja_com_psycopg_fica_intacta():
    url = "postgresql+psycopg://power:power@localhost:5432/power_routine"
    assert Settings(database_url=url, _env_file=None).database_url == url


def test_test_database_url_e_opcional_em_producao():
    """O Render nao tem banco de teste; a API precisa subir so com DATABASE_URL."""
    s = Settings(database_url="postgresql://u:s@h/db", _env_file=None)
    assert s.test_database_url is None
