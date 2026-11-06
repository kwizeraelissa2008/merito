"""Apply SDMS SQL migrations to a Postgres/Supabase database.

Reads the database URL from the ``SDMS_DB_URL`` environment variable so the
password is never written to disk or printed.

Usage:
    python scripts/apply_migrations.py            # apply all pending
    python scripts/apply_migrations.py --dry-run  # list what would run

Records applied versions in ``supabase_migrations.schema_migrations`` so re-runs
are idempotent and match what the Supabase CLI expects.
"""

from __future__ import annotations

import argparse
import hashlib
import os
import sys
from pathlib import Path

try:
    import psycopg
except ImportError:  # pragma: no cover
    print("psycopg is required: pip install 'psycopg[binary]'", file=sys.stderr)
    raise SystemExit(1)

ROOT = Path(__file__).resolve().parent.parent
MIGRATIONS_DIR = ROOT / "supabase" / "migrations"

BOOTSTRAP = """
create schema if not exists supabase_migrations;
create table if not exists supabase_migrations.schema_migrations (
  version text primary key,
  name text,
  hash text,
  executed_at timestamptz not null default now()
);
"""


def discover() -> list[Path]:
    files = sorted(MIGRATIONS_DIR.glob("*.sql"))
    if not files:
        print(f"No migrations found in {MIGRATIONS_DIR}", file=sys.stderr)
        raise SystemExit(1)
    return files


def split_version_name(path: Path) -> tuple[str, str]:
    stem = path.stem  # e.g. 00001_foundation
    version, _, name = stem.partition("_")
    return version, name or stem


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()

    db_url = os.environ.get("SDMS_DB_URL")
    if not db_url:
        print("Set SDMS_DB_URL to the database connection string", file=sys.stderr)
        return 1

    with psycopg.connect(db_url, autocommit=False) as conn:
        with conn.cursor() as cur:
            cur.execute(BOOTSTRAP)
            conn.commit()
            cur.execute("select version from supabase_migrations.schema_migrations")
            applied = {row[0] for row in cur.fetchall()}

        for path in discover():
            version, name = split_version_name(path)
            if version in applied:
                print(f"skip   {version}_{name}")
                continue
            sql = path.read_text(encoding="utf-8")
            digest = hashlib.sha256(sql.encode("utf-8")).hexdigest()
            if args.dry_run:
                print(f"plan   {version}_{name}")
                continue
            print(f"apply  {version}_{name} ...", flush=True)
            try:
                with conn.cursor() as cur:
                    cur.execute(sql)
                    cur.execute(
                        "insert into supabase_migrations.schema_migrations "
                        "(version, name, hash) values (%s, %s, %s)",
                        (version, name, digest),
                    )
                conn.commit()
                print(f"ok     {version}_{name}")
            except Exception as exc:  # noqa: BLE001 - report and stop
                conn.rollback()
                print(f"FAILED {version}_{name}: {exc}", file=sys.stderr)
                return 1

    print("Migrations complete.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
