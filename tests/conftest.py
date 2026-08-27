"""Shared test fixtures.

Integration tests run against a throwaway Postgres started by testcontainers,
migrated with Alembic and seeded with the few rows they depend on. The database
is not the developer's own: the tests must pass on a machine that has never
loaded the Olist data, and in CI, where the source files do not exist.
"""

import os
from collections.abc import Generator

import pytest
from alembic import command
from alembic.config import Config
from sqlalchemy import Engine, create_engine, text
from testcontainers.community.postgres import PostgresContainer

from delivery_risk.database import get_engine

SEED = """
INSERT INTO curated.zip_code_locations (zip_code_prefix, latitude, longitude)
VALUES ('01001', -23.550381, -46.634027),
       ('13010', -22.894561, -47.062380);

INSERT INTO curated.sellers (seller_id, zip_code_prefix, city, state)
VALUES ('seller-with-location', '13010', 'campinas', 'SP');
"""


@pytest.fixture(scope="session")
def postgres_url() -> Generator[str, None, None]:
    """Start a Postgres container, migrate it, seed it, and hand back its URL.

    Session-scoped: starting a container and running migrations takes a few
    seconds, and repeating that per test would make the suite too slow to run
    often.
    """
    with PostgresContainer("postgres:17", driver="psycopg") as container:
        url = container.get_connection_url()

        config = Config("alembic.ini")
        config.set_main_option("sqlalchemy.url", url)
        os.environ["DATABASE_URL"] = url
        get_engine.cache_clear()
        command.upgrade(config, "head")

        engine: Engine = create_engine(url)
        with engine.begin() as connection:
            connection.execute(text(SEED))

        yield url
