from collections.abc import Generator

from sqlalchemy import create_engine
from sqlalchemy.engine import make_url
from sqlalchemy.orm import Session, sessionmaker

from app.config import settings
from app.models import SCHEMA

engine_options = {}
if make_url(settings.DATABASE_URL).get_backend_name() == "sqlite":
    engine_options["execution_options"] = {"schema_translate_map": {SCHEMA: None}}

engine = create_engine(settings.DATABASE_URL, **engine_options)
SessionLocal = sessionmaker(bind=engine, autocommit=False, autoflush=False)


def get_db() -> Generator[Session, None, None]:
    with SessionLocal() as session:
        yield session
