"""Database connection and session management.

The engine is created on first use rather than at import, so importing this
module — or anything that depends on it — does not require configuration to be
present. A test that never touches the database should not need a database URL.
"""

import os
from functools import lru_cache

from dotenv import load_dotenv
from sqlalchemy import Engine, create_engine
from sqlalchemy.orm import Session, sessionmaker

load_dotenv()


def get_database_url() -> str:
    """Return the configured database URL, failing loudly if it is absent."""
    url = os.environ.get("DATABASE_URL")
    if not url:
        raise RuntimeError("DATABASE_URL is not set. Copy .env.example to .env.")
    return url


@lru_cache(maxsize=1)
def get_engine() -> Engine:
    """Return the shared engine, creating it on first use."""
    return create_engine(get_database_url())


def get_session() -> Session:
    """Create a new session bound to the shared engine."""
    return sessionmaker(bind=get_engine(), expire_on_commit=False)()
