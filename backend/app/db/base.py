"""SQLAlchemy 2.x declarative base.

All ORM models inherit from `Base`. Importing `app.db.models` populates
`Base.metadata` with every table — useful for tests that build/drop a schema
without going through Alembic.
"""

from sqlalchemy.orm import DeclarativeBase


class Base(DeclarativeBase):
    pass
