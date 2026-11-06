# SDMS System Architecture

**School Periodic Report Card Management System**  
Multi-tenant SaaS for Rwandan secondary schools  
Version: 0.2.0 (Phase 2 — school configuration)

## 1. Goals

- Persistent, multi-tenant academic and behavioral reporting
- Database-enforced tenant isolation and role permissions (RLS)
- Authoritative calculations and PDF generation in FastAPI
- Accessible, mobile-friendly Next.js PWA for day-to-day work
- Auditable workflows for marks, discipline, approvals, and publication

## 2. High-level architecture

```
┌─────────────────────────────────────────────────────────────────┐
│  Clients (Browser / Installable PWA)                            │
│  Next.js App Router · React · Tailwind · shadcn/ui              │
└────────────────────────────┬────────────────────────────────────┘
                             │ HTTPS (session cookies / JWT)
         ┌───────────────────┼───────────────────┐
         ▼                   ▼                   ▼
┌─────────────────┐ ┌─────────────────┐ ┌─────────────────────────┐
│ Next.js Server  │ │ FastAPI API     │ │ Supabase                │
│ Actions / BFF   │ │ Calculations    │ │ Auth · Postgres · RLS   │
│ Auth helpers    │ │ Ranking         │ │ Storage · Realtime      │
│ UI data fetch   │ │ Snapshots       │ │ (private buckets)       │
│                 │ │ PDF orchestration│ │                         │
│                 │ │ AI (optional)   │ │                         │
└────────┬────────┘ └────────┬────────┘ └────────────┬────────────┘
         │                   │                       │
         └───────────────────┴───────────────────────┘
                             │
                    PostgreSQL (single source of truth)
                             │
                    background_jobs table (outbox)
                             │
                    Worker (PDF / batch) → Storage
```

### Responsibility boundaries

| Concern | Owner |
|---|---|
| Persistence, FKs, constraints, RLS, audit rows, OCC versions | PostgreSQL / Supabase |
| Weighted marks, ranking, behavior aggregation, snapshot assembly, PDF jobs, OpenAPI | FastAPI |
| Forms, grids, dashboards, optimistic UX, permission-aware UI | Next.js |
| Secrets / privileged DB ops | Server only (never browser) |

Frontend **displays** calculation results returned by FastAPI. It must not maintain a competing grading formula.

## 3. Repository layout

```
/
├── apps/
│   ├── web/                 # Next.js (App Router, PWA)
│   └── api/                 # FastAPI + calculation engine + PDF worker hooks
├── supabase/
│   ├── migrations/          # Versioned SQL
│   └── seed/                # Fictional demo data
├── docs/                    # Architecture, ERD, permissions, ops guides
├── scripts/                 # Dev helpers
├── .github/workflows/       # CI
├── .env.example
└── README.md
```

Monorepo without microservices. Redis is **not** introduced until a queue workload requires it; Phase 1–6 use the durable `background_jobs` table as the transactional outbox.

## 4. Multi-tenancy model

- Every tenant-owned row carries `school_id` (UUID).
- Users authenticate via Supabase Auth (`auth.users` → `profiles`).
- Access to a school is via `school_memberships` (role + status).
- RLS policies deny by default and require an active membership for the row’s `school_id`.
- Teaching / class-teacher access further restricts mark and report reads via assignment tables.
- Platform admins use a separate `platform_roles` flag; they do **not** automatically read student academics. Exceptional support access is time-boxed and audited (Phase 8).

## 5. AuthN / AuthZ flow

1. User signs in (Supabase Auth).
2. Next.js middleware refreshes session; server components read memberships.
3. UI routes by primary active membership role(s).
4. Mutations go through Next.js server actions or FastAPI with the user’s JWT.
5. FastAPI validates JWT with Supabase JWKS, resolves memberships, then executes authorized domain logic (often via service role **after** explicit authz checks).
6. Direct table access from the browser uses the anon key + RLS only for permitted reads/writes; privileged multi-step workflows use FastAPI + transactions.

## 6. Domain modules

| Module | Description |
|---|---|
| Tenancy & onboarding | Schools, invitations, wizard, CSV import |
| Academic structure | Years, terms, periods, curricula, grades, combinations, classes, subjects |
| People | Profiles, memberships, students, enrollments, guardians |
| Assignments | Teaching assignments, class teachers |
| Assessment | Categories, assessments, scores, autosave + OCC |
| Behavior | Incident types, incidents, reviews, score = 40 − approved deductions (default) |
| Attendance | Daily records, summaries |
| Reporting | Comments, calculation, ranking, snapshots, approvals, templates, PDF jobs |
| Ops | Deadlines, notifications, audit_logs, background_jobs |

## 7. Calculation engine (FastAPI)

Package: `apps/api/app/calculations/`

- Decimal arithmetic with explicit rounding mode/precision (documented defaults).
- Category % = valid scores / applicable maxima × 100
- Overall % = Σ (category % × weight)
- Incomplete sets → provisional unless school policy allows otherwise; provisional cannot publish as final
- Behavior score = max(0, base − Σ approved deductions); excess deductions flagged
- Ranking: shared positions for ties by default; no name/code/DB-order tie-breakers

Policy version IDs are stored on every finalized `report_instances` row.

## 8. Report publication pipeline

1. Teachers submit → class teacher / moderator review → principal approve (school-configurable).
2. Approval transaction: status transition + audit + snapshot JSON + hash + outbox job row.
3. Worker renders HTML→PDF (Playwright/Chromium), stores in private bucket, updates job.
4. Released reports use short-lived signed URLs; re-download returns the same snapshot unless a new versioned correction is authorized.

## 9. Autosave & concurrency

- Debounced client writes with Saving / Saved / Failed / Conflict states
- Server confirms before “Saved”
- `version` integer on scores, comments, incidents, attendance
- Stale version → 409 Conflict with server value + client proposal preserved in UI

## 10. Deployment (target)

| Component | Target |
|---|---|
| `apps/web` | Vercel |
| Supabase | Hosted Postgres + Auth + Storage |
| `apps/api` | Render (or equivalent) web service |
| PDF worker | Same service or Render worker process consuming `background_jobs` |

## 11. Defaults (school-configurable; not national law)

Documented in `docs/grading-assumptions.md`. Examples:

- 3 terms × 3 periodic reports / year
- Behavior base mark: 40
- Default incident deduction table (shouting 2, lateness 2, …)
- Ranking: dense/shared rank on equal overall %
- Missing ≠ 0; absent/exempt/pending are distinct score statuses

## 12. Phase status

- Phase 1 (foundation): monorepo, migration 00001 + RLS, dual-school seed, auth shell, calculation engine.
- Phase 2 (school configuration): migrations 00002–00004, FastAPI configuration/membership API with JWT + membership authorization, admin Settings UI, onboarding wizard with save-and-resume, invitations with single-use hashed tokens, CSV import with preview/commit, seed extended with grading categories/bands and onboarding state.

Remaining phases add onboarding history, mark grids, discipline, reports, PDFs, dashboards.
