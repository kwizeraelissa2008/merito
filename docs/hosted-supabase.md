# Hosted Deployment — Supabase (eu-west-1)

This document records how SDMS is wired to a **hosted** Supabase project
(no local Docker), and how to re-apply migrations.

## 1. Create / choose a project

1. Create a project at [supabase.com](https://supabase.com) — region **eu-west-1**
   (Ireland) is a good latency choice for Rwanda.
2. Set a strong **database password** and keep it safe.
3. From **Project Settings → API**, note:
   - Project URL, e.g. `https://<ref>.supabase.co`
   - **Publishable** key (`sb_publishable_…`) — safe for the browser
   - **Secret** key (`sb_secret_…`) — server-only, never shipped to the client

> New projects use asymmetric auth signing (ES256) and publish a JWKS document
> at `https://<ref>.supabase.co/auth/v1/.well-known/jwks.json`. Older projects
> use HS256 with a shared JWT secret. The API supports both (see below).

## 2. Environment

Copy `.env.example` into the two gitignored files and fill them in:

| File | Purpose |
|---|---|
| `apps/web/.env.local` | Browser + Next.js server: URL, publishable key, API URL |
| `apps/api/.env` | FastAPI: URL, publishable key, secret key, JWKS URL |

Never commit these files. The service/secret key must only ever be present on
the server.

## 3. Apply migrations

Migrations are plain SQL in `supabase/migrations/` and are applied in order.
Two supported paths:

### Option A — `psycopg` runner (no CLI login required)

```bash
# Session pooler connection string from Settings → Database → Connection string
set SDMS_DB_URL=postgresql://postgres.<ref>:<PASSWORD>@aws-0-eu-west-1.pooler.supabase.com:5432/postgres
python scripts/apply_migrations.py            # applies pending
python scripts/apply_migrations.py --dry-run  # list only
```

The runner records applied versions in
`supabase_migrations.schema_migrations`, so it matches what the Supabase CLI
expects and re-runs are idempotent.

### Option B — Supabase CLI

```bash
supabase login                      # paste a personal access token (sbp_…)
supabase link --project-ref <ref>
supabase db push                    # applies pending migrations
```

`supabase link`/`db push` require a personal access token, **not** the database
password.

## 4. Verify

```bash
set SDMS_DB_URL=postgresql://...
python scripts/verify_phase2.py
```

Expected: all checks `PASS` (8 Phase-2 tables, RLS enabled, `audit_logs`
immutable, RPCs present), plus band-boundary output when seed data exists.

## 5. Auth token verification

The hosted project signs tokens with **ES256** and exposes JWKS. Configure the
API with:

```
SUPABASE_JWKS_URL=https://<ref>.supabase.co/auth/v1/.well-known/jwks.json
# SUPABASE_JWT_SECRET only for legacy HS256 projects / local dev
```

`app/core/auth.py` tries JWKS first, then falls back to the HS256 secret when
one is configured. It never accepts unverified tokens.

## 6. Seed data

The hosted database is intentionally **clean** (no fictional demo seed). Create
the first school through the in-app onboarding wizard. To load the demo seed on
a throwaway project only:

```bash
psql "$SDMS_DB_URL" -f supabase/seed/demo.sql
```

Do not load demo data into a production project.

## 7. Related scripts

- `scripts/apply_migrations.py` — idempotent migration runner
- `scripts/verify_phase2.py` — post-migration structural/RLS verification
- `scripts/verify-phase2.sql` — psql-friendly verification (manual RLS notes)
