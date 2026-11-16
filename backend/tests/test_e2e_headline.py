from sqlalchemy import create_engine

from app.config import settings
from app import db as database
from app.ml import registry
from scripts.seed_demo import run_demo


def test_demo_refuses_without_confirmation():
    import pytest
    with pytest.raises(ValueError, match="without --yes"):
        run_demo()


def test_e2e_headline_sqlite(tmp_path, monkeypatch, capsys):
    url = f"sqlite:///{(tmp_path / 'demo.sqlite').as_posix()}"
    engine = create_engine(url, execution_options={"schema_translate_map": {"sentinel": None}})
    from sqlalchemy.orm import sessionmaker
    monkeypatch.setattr(settings, "DATABASE_URL", url)
    monkeypatch.setattr(settings, "DEMO_EMAIL", "demo@example.com")
    monkeypatch.setattr(settings, "DEMO_PASSWORD", "demo-password")
    monkeypatch.setattr(database, "SessionLocal", sessionmaker(bind=engine))
    monkeypatch.setattr(registry, "MODEL_DIR", tmp_path / "models")
    try:
        assert run_demo(confirmed=True, output_dir=tmp_path / "synthetic")
        output = capsys.readouterr()
        for user_id in ("EMP004", "EMP007", "EMP013", "EMP018"):
            assert user_id in output.out
    finally:
        engine.dispose()
