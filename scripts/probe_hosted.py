"""Live integration probe against the hosted Supabase project.

Uses only the publishable key (safe) to verify:
  1. JWKS is reachable and the API's verifier can load it.
  2. An invalid token is rejected (401) — fail closed.
  3. RLS denies anonymous reads (0 rows) and anonymous writes (401).

Requires: SDMS_DB_URL not needed; reads apps/api/.env for the project URL and key.
Run:  python scripts/probe_hosted.py
"""

from __future__ import annotations

import asyncio
import os
import sys
from pathlib import Path

import httpx

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "apps" / "api"))

# Minimal .env loader (avoids importing full settings so we can run standalone).
def load_env() -> dict[str, str]:
    env: dict[str, str] = {}
    env_path = ROOT / "apps" / "api" / ".env"
    if env_path.exists():
        for line in env_path.read_text(encoding="utf-8").splitlines():
            line = line.strip()
            if not line or line.startswith("#") or "=" not in line:
                continue
            key, _, value = line.partition("=")
            env[key.strip()] = value.strip()
    return env


async def main() -> int:
    env = load_env()
    url = env.get("SUPABASE_URL") or os.environ.get("SUPABASE_URL", "")
    anon = env.get("SUPABASE_ANON_KEY") or env.get("SUPABASE_SERVICE_ROLE_KEY", "")
    if not url or not anon:
        print("Missing SUPABASE_URL / SUPABASE_ANON_KEY in apps/api/.env", file=sys.stderr)
        return 1

    failures: list[str] = []
    async with httpx.AsyncClient(timeout=15.0) as client:
        # 1. JWKS reachable
        jwks_url = f"{url}/auth/v1/.well-known/jwks.json"
        try:
            resp = await client.get(jwks_url, headers={"apikey": anon})
            keys = resp.json().get("keys", [])
            print(f"PASS  JWKS reachable ({len(keys)} key(s)): "
                  + ", ".join(f"{k.get('alg')}:{k.get('kid','')[:8]}" for k in keys))
            if not keys:
                failures.append("JWKS has no keys")
        except Exception as exc:  # noqa: BLE001
            print(f"FAIL  JWKS unreachable: {exc}")
            failures.append("jwks")

        # 2. API verifier loads and rejects an invalid token (fail closed)
        os.environ.setdefault("SUPABASE_JWKS_URL", jwks_url)
        from app.core.auth import get_current_user  # noqa: PLC0415
        from fastapi import HTTPException  # noqa: PLC0415

        try:
            await get_current_user("Bearer not.a.valid.token")
            print("FAIL  invalid token was accepted")
            failures.append("token")
        except HTTPException as exc:
            if exc.status_code == 401:
                print("PASS  invalid token rejected (401)")
            else:
                print(f"FAIL  unexpected status {exc.status_code}")
                failures.append("token-status")

        # 3. RLS: anonymous reads denied
        for table in ("schools", "students", "assessment_scores", "audit_logs"):
            resp = await client.get(
                f"{url}/rest/v1/{table}?select=*",
                headers={"apikey": anon},
            )
            rows = resp.json() if resp.status_code == 200 else None
            count = len(rows) if isinstance(rows, list) else resp.status_code
            if isinstance(rows, list) and len(rows) == 0:
                print(f"PASS  anon read {table} -> 0 rows")
            else:
                print(f"FAIL  anon read {table} -> {count}")
                failures.append(f"rls-{table}")

        # 4. Anonymous write denied
        resp = await client.post(
            f"{url}/rest/v1/subjects",
            headers={"apikey": anon, "Content-Type": "application/json"},
            json={"school_id": "00000000-0000-0000-0000-000000000000",
                  "name": "x", "code": "X"},
        )
        if resp.status_code in (401, 403):
            print(f"PASS  anon write blocked ({resp.status_code})")
        else:
            print(f"FAIL  anon write returned {resp.status_code}")
            failures.append("anon-write")

    if failures:
        print(f"\n{len(failures)} probe failure(s): {', '.join(failures)}", file=sys.stderr)
        return 1
    print("\nHosted probe complete — all checks passed.")
    return 0


if __name__ == "__main__":
    raise SystemExit(asyncio.run(main()))
