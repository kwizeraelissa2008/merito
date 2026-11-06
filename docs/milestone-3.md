# Milestone 3 — Students & Mark Entry (Phase 3)

## Implemented

**Database (migration `00005_students_assessment.sql`)**

- `student_status` + `marksheet_status` enums.
- `students.status` migrated from free text to the enum (with a guarded cast).
- `marksheets` — submission workflow state per (class, subject, reporting period)
  with RLS (teachers see their own; leadership sees all).
- `audit_assessment_score` trigger — monotonic `version` (optimistic concurrency
  support) plus an audit row whenever score/status changes.
- `generate_student_code()` — sequential per-school codes (`STU-000123`).
- `enforce_enrollment_year()` — blocks enrolling a student in a class from a
  different academic year.
- Unique partial index: one **active** enrollment per student per academic year.
- Performance indexes for roster and score lookups.
- Applied to the hosted database (all migrations `00001`–`00005` present).

**API (`apps/api`)** — new endpoints under `/v1/schools/{id}`:

- Students: list (filter by class/search, paginated), get (with enrollment
  history), create (auto student code), update, bulk create + enroll, transfer
  (closes old enrollment, opens new — history preserved), withdraw.
- Assessments: list, create, update (blocks lowering a maximum below an existing
  score).
- Mark entry: `GET .../mark-grid` (roster + assessments + scores + marksheet),
  `PUT .../scores` (autosave one cell with OCC → 409 on stale version),
  `POST .../scores/bulk` (atomic; any stale version rejects the whole batch and
  writes nothing), mark-sheet submit (teacher) and review (HoD/principal).
- Authorisation: `_ensure_teaches` verifies the caller teaches the class+subject
  (admins exempt); RLS enforces the same at the database layer.
- Validation: score must be numeric, ≥ 0 and ≤ the assessment maximum, at both
  the API and database level.
- Unit tests: 39 passing (added score/assessment/student schema tests); `ruff`
  clean.

**Web (`apps/web`)**

- `/app/students` — roster with search + class filter, links to detail.
- `/app/students/new` — create + enroll (auto code, optional fields).
- `/app/students/[id]` — profile and full enrollment history, plus transfer and
  withdraw actions for admins (history never overwritten).
- `/app/marks` — role-aware list of mark grids (teachers see their assignments,
  leadership sees school-wide).
- `/app/marks/grid` — spreadsheet-style grid: keyboard navigation (arrows,
  Enter, Tab), paste-from-spreadsheet, per-cell save states
  (idle/dirty/saving/saved/error/conflict), debounced autosave, truthful save
  status, conflict resolution preserving the user's input, missing ≠ zero, and
  mark-sheet submission. Warns before leaving with unsaved changes.
- `lint` clean; `build` succeeds with all routes.

## Verified

- [x] Migrations `00001`–`00005` applied to the hosted Supabase project
- [x] `marksheets` table exists with RLS enabled + 3 policies
- [x] Phase 3 functions present: `generate_student_code`, `enforce_enrollment_year`,
      `audit_assessment_score`
- [x] `pytest` (39 passed), `ruff` clean
- [x] `npm run lint` clean, `npm run build` succeeds
- [x] Hosted probe: JWKS, invalid-token rejection, anon RLS read/write denial

## Explicitly not in Phase 3

- Attendance and discipline UIs (Phase 4).
- Report calculation UI, snapshots, approvals (Phase 5); PDF pipeline and
  deadline centre (Phase 6); full dashboards/PWA/analytics (Phase 7).
- Offline editing is NOT offered: there is a debounced autosave queue with
  retry-on-focus, but no durable offline queue or background sync. The UI does
  not claim offline support.
- Bulk roster import is available through Phase 2's `/app/settings/imports`
  (students entity); a dedicated roster-with-class import UI lands with
  enrollment import in a later pass.
