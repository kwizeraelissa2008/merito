# SDMS — School Periodic Report Card Management System

Production-oriented multi-tenant SaaS for Rwandan secondary schools: marks, attendance, behavioral deductions, approvals, immutable report snapshots, and PDF generation.

> **Status:** Phase 3 (student management + autosaving mark entry) is implemented. Hosted on Supabase (eu-west-1). Later phases (discipline, reports, PDFs, dashboards) build on this base. See `docs/milestone-1.md` … `docs/milestone-3.md`.

## Architecture at a glance

| Layer | Stack |
|---|---|
| Web | Next.js App Router, TypeScript, Tailwind |
| API | FastAPI (authoritative calculations, future PDF jobs) |
| Data | Supabase Postgres + Auth + RLS + Storage |

Docs:

- [Architecture](docs/architecture.md)
- [ERD](docs/erd.md)
- [Permission matrix](docs/permission-matrix.md)
- [Migration plan](docs/migration-plan.md)
- [Grading assumptions (defaults)](docs/grading-assumptions.md)
- [Hosted Supabase setup](docs/hosted-supabase.md)
- [Phase 2 milestone](docs/milestone-2.md)
- [Phase 3 milestone](docs/milestone-3.md)

## Repository layout

```
apps/web     Next.js PWA shell + auth
apps/api     FastAPI + calculation engine
supabase/    Migrations, seed, config
docs/        Architecture & ops docs
```

## Prerequisites

- Node.js 20+
- Python 3.11+
- [Supabase CLI](https://supabase.com/docs/guides/cli) (for local DB)
- Docker (required by local Supabase)

## Quick start

### 1. Environment

```bash
cp .env.example apps/web/.env.local
cp .env.example apps/api/.env
```

After `supabase start`, paste the printed URL and anon/service keys into those files.

### 2. Database

**Hosted Supabase (recommended — see [docs/hosted-supabase.md](docs/hosted-supabase.md))**

```bash
set SDMS_DB_URL=postgresql://postgres.<ref>:<PASSWORD>@aws-0-eu-west-1.pooler.supabase.com:5432/postgres
python scripts/apply_migrations.py
python scripts/verify_phase2.py
```

**Local Supabase (requires Docker + the Supabase CLI)**

```bash
supabase start
supabase db reset
```

Local applies `00001_foundation.sql` – `00004_grading_bands.sql` and loads the
fictional dual-school seed from `supabase/seed/demo.sql`.

### 3. Web

```bash
cd apps/web
npm install
npm run dev
```

Open [http://localhost:3000](http://localhost:3000).

### 4. API

```bash
cd apps/api
python -m venv .venv
# Windows: .venv\Scripts\activate
# Unix: source .venv/bin/activate
pip install -r requirements.txt
uvicorn app.main:app --reload --port 8000
```

- Health: `GET http://localhost:8000/health`
- OpenAPI: [http://localhost:8000/docs](http://localhost:8000/docs)

### 5. Tests

```bash
cd apps/api
pytest
```

```bash
cd apps/web
npm run lint
npm run build
```

## Security notes

- Tenant isolation is enforced with Postgres RLS; UI hiding is not the security boundary.
- Never expose `SUPABASE_SERVICE_ROLE_KEY` to the browser.
- Demo seed data is fictional. Do not load real student PII into public demos.
- Platform admins do not automatically receive student academic access.

## Deployment (target)

- `apps/web` → Vercel
- Supabase → hosted project (run migrations)
- `apps/api` → Render (or equivalent)

See `.env.example` for required variables. Detailed runbooks (backup/recovery, smoke tests) expand in Phase 8.

## What is / isn’t done

**Done (through Phase 3):** monorepo; schema + RLS (migrations `00001`–`00005`) applied to hosted Supabase; school configuration (onboarding wizard, curriculum/classes/subjects/grading, invitations with hashed single-use tokens, audited RPCs, CSV import with preview); student management with preserved enrollment history (create/transfer/withdraw, auto codes); autosaving mark-entry grid with keyboard nav, paste, optimistic concurrency and conflict resolution; mark-sheet submit/review; calculation engine with unit tests.

**Next:** Phase 4 — attendance entry and discipline (incident recording, DoD approval queue, behavioral scoring).
