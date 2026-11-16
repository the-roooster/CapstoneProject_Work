"""Import synthetic CSV directories or CERT files."""
import argparse
import sys
from dataclasses import asdict
import json
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from app.db import SessionLocal
from app.ingest.ingest import load_cert, load_events_csv, load_users_csv


def main():
    parser = argparse.ArgumentParser(description="Ingest activity CSVs")
    group = parser.add_mutually_exclusive_group(required=True)
    group.add_argument("path", nargs="?", help="directory containing users.csv and events.csv")
    group.add_argument("--cert", metavar="DIR", help="CERT CSV directory")
    parser.add_argument("--limit", type=int, default=None, help="maximum CERT rows across all files")
    args = parser.parse_args()
    with SessionLocal() as session:
        if args.cert:
            result = {"events": asdict(load_cert(session, args.cert, limit=args.limit))}
        else:
            directory = Path(args.path)
            result = {"users": asdict(load_users_csv(session, directory / "users.csv")),
                      "events": asdict(load_events_csv(session, directory / "events.csv"))}
    print(json.dumps(result, sort_keys=True))


if __name__ == "__main__":
    main()
