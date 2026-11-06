# Milestone 1 — Foundation (Acceptance)

## Implemented in this milestone

1. System architecture, ERD, permission matrix, migration plan, grading defaults
2. Monorepo: `apps/web` (Next.js) + `apps/api` (FastAPI)
3. Supabase migration `00001_foundation.sql` with core schema + RLS helpers
4. Fictional dual-school seed data
5. Auth-ready UI shell, design tokens, public landing + login routes
6. FastAPI health + OpenAPI + calculation module stubs with unit tests
7. `.env.example`, README, CI workflow

## Verified locally

- [x] `npm run lint` / `npm run build` in `apps/web`
- [x] `pytest` in `apps/api` (8 passed) + `ruff check`
- [ ] `supabase db reset` applies migrations + seed (requires Docker + Supabase CLI on the machine)

## Explicitly not in Milestone 1

Onboarding wizard, mark grid, PDF pipeline, full dashboards, Realtime, AI comments—these land in Phases 2–7.
