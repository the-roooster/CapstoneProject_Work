"""Create the configured demo analyst once."""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from sqlalchemy import select

from app.auth import hash_password
from app.config import settings
from app.db import SessionLocal
from app.models import Analyst


def seed_analyst(db, email: str, password: str) -> bool:
    email = email.strip()
    if not email or not password:
        raise ValueError("DEMO_EMAIL and DEMO_PASSWORD must both be set")
    if db.scalar(select(Analyst.id).where(Analyst.email == email)) is not None:
        return False
    db.add(Analyst(email=email, password_hash=hash_password(password)))
    db.commit()
    return True


def main():
    with SessionLocal() as db:
        created = seed_analyst(db, settings.DEMO_EMAIL, settings.DEMO_PASSWORD)
    print("Analyst created." if created else "Analyst already exists.")


if __name__ == "__main__":
    main()
