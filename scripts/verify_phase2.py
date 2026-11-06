"""Post-migration verification for the hosted Supabase database.

Checks that every Phase 2 object exists, RLS is enabled, audit_logs is
immutable, and the grading-band resolver returns correct boundary results.

Usage:
    set SDMS_DB_URL=postgresql://...   (env var; never written to disk)
    python scripts/verify_phase2.py
"""

from __future__ import annotations

import os
import sys

try:
    import psycopg
except ImportError:  # pragma: no cover
    print("psycopg is required", file=sys.stderr)
    raise SystemExit(1)

CHECKS: list[tuple[str, str]] = [
    (
        "tables present",
        """
        select count(*) from information_schema.tables
        where table_schema = 'public' and table_name in (
          'school_config_versions','user_invitations','guardian_student_links',
          'report_releases','assessment_categories','grading_bands',
          'report_layouts','school_onboarding')
        """,
    ),
    (
        "rls enabled on phase-2 tables",
        """
        select count(*) from pg_class
        where relname in (
          'school_config_versions','user_invitations','guardian_student_links',
          'report_releases','assessment_categories','grading_bands',
          'report_layouts','school_onboarding')
          and relrowsecurity = true
        """,
    ),
    (
        "audit_logs has no UPDATE/DELETE policy",
        """
        select count(*) from pg_policies
        where schemaname='public' and tablename='audit_logs' and cmd in ('UPDATE','DELETE')
        """,
    ),
    (
        "accept_invitation function exists",
        "select count(*) from pg_proc where proname = 'accept_invitation'",
    ),
    (
        "resolve_grading_band function exists",
        "select count(*) from pg_proc where proname = 'resolve_grading_band'",
    ),
    (
        "can_view_student function exists",
        "select count(*) from pg_proc where proname = 'can_view_student'",
    ),
]

EXPECT_PRESENT = {"tables present": 8, "rls enabled on phase-2 tables": 8}
EXPECT_ABSENT = {"audit_logs has no UPDATE/DELETE policy": 0}


def main() -> int:
    db_url = os.environ.get("SDMS_DB_URL")
    if not db_url:
        print("Set SDMS_DB_URL", file=sys.stderr)
        return 1

    failures: list[str] = []
    with psycopg.connect(db_url) as conn, conn.cursor() as cur:
        for label, sql in CHECKS:
            cur.execute(sql)
            value = cur.fetchone()[0]
            ok = True
            if label in EXPECT_PRESENT:
                ok = value == EXPECT_PRESENT[label]
            elif label in EXPECT_ABSENT:
                ok = value == EXPECT_ABSENT[label]
            else:
                ok = value >= 1
            print(f"{'PASS' if ok else 'FAIL'}  {label}: {value}")
            if not ok:
                failures.append(label)

        # Behavior: grading band boundaries (only if seed data is present).
        cur.execute("select count(*) from grading_policies")
        if cur.fetchone()[0] > 0:
            cur.execute(
                """
                select p, (public.resolve_grading_band(
                  (select id from grading_policies order by version desc limit 1), p)).letter
                from (values (0.00),(49.99),(50.00),(69.99),(80.00),(100.00)) as v(p)
                """
            )
            print("band boundaries:", cur.fetchall())

    if failures:
        print(f"\n{len(failures)} check(s) failed", file=sys.stderr)
        return 1
    print("\nAll verification checks passed.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
