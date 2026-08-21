"""Declarative base shared by every model in the project."""

from sqlalchemy.orm import DeclarativeBase


class Base(DeclarativeBase):
    """Base class for all ORM models.

    Every table in the project inherits from this class, which means its
    metadata is registered here. Alembic reads that metadata to work out what
    the schema should look like, so a model class that is never imported is a
    table Alembic does not know about.
    """

    