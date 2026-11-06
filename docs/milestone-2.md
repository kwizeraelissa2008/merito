# Milestone 2 — School Configuration (Phase 2)

## Implemented

**Database (migrations 00002–00004)**

- `00002_rls_refinement.sql` — assignment-scoped visibility helpers
  (`can_view_student`, `is_verified_guardian_of` via 00003), colleague profile
  reads, member-scoped audit/config helpers, and the `school_config_versions`
  versioning table. Tenant isolation remains enforced by RLS.
- `00003_invitations_guardians.sql` — `user_invitations` (hashed single-use
  tokens, pending-uniqueness), `guardian_student_links` (verified relationships),
  `report_releases` (explicit per-audience report distribution), and the
  `accept_invitation` / `revoke_invitation` SECURITY DEFINER RPCs with audited
  outcomes.
- `00004_grading_bands.sql` — `assessment_categories`, `grading_bands`
  (+ `resolve_grading_band` helper), `report_layouts`, and resumable
  `school_onboarding` state.

**API (`apps/api`)**

- JWT authentication dependency (`core/auth.py`) with database-resolved
  membership/role checks on every privileged route — client-supplied roles are
  never trusted.
- `core/supabase.py` — PostgREST client. User-JWT path (RLS applies) by default;
  service-role path only for audited multi-step transactions.
- Phase 2 routers under `/v1`: school identity & overview, academic years /
  terms / reporting periods (+ default 3×3 calendar generator), curricula /
  grades / combinations / curriculum-subjects / classes (incl. bulk streams),
  subjects, grading policies / categories / bands (with weight-sum and
  band-set validation), invitations (create + accept RPC + revoke RPC),
  member status, teaching & class-teacher assignments, onboarding state
  (save-and-resume + completion gate that activates the school), and a
  two-step CSV import (`/preview` → `/commit`) with duplicate detection and
  per-row errors. Nothing is written during preview.
- Unit tests added: import validation, auth boundary (401/500 fail-closed),
  configuration schema validation. **29 tests pass; `ruff` clean.**

**Web (`apps/web`)**

- Role-aware app sidebar + top bar with session/membership badges and sign-out.
- Settings shell (`/app/settings/*`) with tab navigation, guarded to school
  administrators (UI mirror of the DB/API boundary; the DB is the boundary).
  Pages: overview (live counts), school identity, calendar (create year +
  generate default calendar), curriculum (curricula/grades/combinations +
  preview), subjects, classes (single + bulk streams), grading (policy,
  category weights incl. 100% check, bands), members & invitations (create /
  revoke / member status + teaching & class-teacher assignments), and
  configuration import (preview table → commit, errors block commit).
- Onboarding wizard (`/app/onboarding`) with progress bar and save-and-resume:
  identity → calendar → curriculum seed (O-Level, A-Level MS, S6 Legacy) →
  subjects seed → grading policy seed → members → review & activate (blocks
  until year/subjects/classes/policy exist).
- Invitation acceptance page at `/invitations/accept?token=…`.
- `npm run lint` clean; `npm run build` succeeds with all 20 routes.

## Verified

- [x] `pytest` (30 passed) and `ruff check` in `apps/api`
- [x] `npm run lint` and `npm run build` in `apps/web`
- [x] Migrations `00001–00004` applied to the **hosted** Supabase project
      (eu-west-1) via `scripts/apply_migrations.py`
- [x] `scripts/verify_phase2.py` on the hosted DB — all checks PASS
      (8 Phase-2 tables, RLS enabled, audit_logs immutable, RPCs present)
- [x] Deny-by-default confirmed against the live REST API: anonymous reads
      return 0 rows from every tenant table; anonymous writes are rejected (401)
- [x] JWKS auth (ES256) reachable and supported by the upgraded API auth path

## Verification on your machine

1. Confirm env files are filled (`apps/web/.env.local`, `apps/api/.env`) — see
   [hosted-supabase.md](hosted-supabase.md).
2. Re-run structural verification any time:
   `SDMS_DB_URL=… python scripts/verify_phase2.py`
   (or the psql variant `scripts/verify-phase2.sql`).
3. Exercise the RLS matrix with a real signed-in user: a subject teacher must
   not be able to `insert` subjects; a guardian must see nothing in
   `report_instances`.
4. Create a school through the onboarding wizard and confirm the corresponding
   rows in `audit_logs`.

## Explicitly not in Phase 2

- Mark entry grids / autosave (Phase 3), attendance & discipline UIs (Phase 4),
  report calculation UI, snapshots, approvals (Phase 5), PDF pipeline and
  deadline center (Phase 6), full dashboards/PWA/analytics (Phase 7),
  backups/monitoring/hardening runbook (Phase 8).
- Auth users are NOT seeded; create accounts via Supabase Auth and invite them
  from `/app/settings/members`.
- `school_config_versions` is created for future snapshot pinning; bumping it
  automatically on every config write is a Phase 5 integration point.
- Guardian portal access is inactive until `report_releases` rows exist and a
  guardian-grade surface is built (Phase 5/6); students portal linking is not
  built — `report_releases` only ships verified-guardian evaluation for now.
