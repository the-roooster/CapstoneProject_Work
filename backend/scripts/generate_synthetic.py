"""Generate synthetic CSVs: python backend/scripts/generate_synthetic.py."""
import argparse
import sys
from datetime import date
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from app.ingest.synthetic import generate_synthetic


def main():
    parser = argparse.ArgumentParser(description="Generate deterministic synthetic activity CSVs")
    parser.add_argument("--out", default="data/synthetic")
    parser.add_argument("--seed", type=int, default=42)
    parser.add_argument("--anchor-date", type=date.fromisoformat, default=date(2026, 11, 2))
    parser.add_argument("--days", type=int, default=45)
    args = parser.parse_args()
    generate_synthetic(**vars(args))


if __name__ == "__main__":
    main()
