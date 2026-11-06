# Database Migration Plan

Migrations live in `supabase/migrations/` and are applied in lexical order.

## Principles

- Additive, versioned SQL only—no ad-hoc production edits
- Enable RLS on every tenant-owned table in the same migration that creates it
- Prefer `SECURITY DEFINER` helper functions with fixed `search_path` for membership checks
- Seed data is fictional and separate from schema migrations

## Planned migrations

| File | Phase | Contents |
|---|---|---|
| `00001_foundation.sql` | 1 | Extensions, enums, core tables (schools → background_jobs), indexes, RLS helpers, baseline policies, audit immutability |
| `00002_rls_refinement.sql` | 2 | Assignment-scoped visibility helpers, colleague profile reads, audit/config versioning helpers, `school_config_versions` |
| `00003_invitations_guardians.sql` | 2 | `user_invitations` (hashed tokens), `guardian_student_links`, `report_releases`, `accept_invitation` / `revoke_invitation` RPCs |
| `00004_grading_bands.sql` | 2 | `assessment_categories`, `grading_bands`, `report_layouts`, `school_onboarding`, `resolve_grading_band` |
| `00005_students_assessment.sql` | 3 | Student status enum, `marksheets` (submission workflow), score audit + OCC trigger, student-code generator, enrollment year-guard |
| `00006_correction_requests.sql` | 4 | Behavioral/academic correction request tables |
| `00007_storage_buckets.sql` | 6 | Private bucket policies for logos, photos, PDFs |
| `00008_performance_indexes.sql` | 8 | Composite indexes tuned from measured query plans |

## Milestone 1 migration scope (`00001`)

Creates:

- `schools`, `profiles`, `school_memberships`, `platform_admins`
- Academic calendar: `academic_years`, `terms`, `reporting_periods`
- Structure: `curricula`, `grades`, `combinations`, `classes`, `subjects`, `curriculum_subjects`
- People: `students`, `enrollments`
- Assignments: `teaching_assignments`, `class_teacher_assignments`
- Assessment: `assessments`, `assessment_scores`
- Policies: `grading_policies`
- Behavior: `incident_types`, `behavioral_incidents`, `incident_reviews`
- Attendance: `attendance_records`
- Comments / reports: `student_comments`, `report_templates`, `report_instances`, `report_approvals`
- Ops: `notifications`, `audit_logs`, `background_jobs`

Seed (`supabase/seed/demo.sql`): two schools, sample O-Level + MS1/MS2 + legacy S6 structure, fictional staff/students.

## Phase 2 migration scope (`00002`–`00004`)

Creates:

- `00002`: RLS refinement (`can_view_student`, verified-guardian visibility helpers), colleague profile reads, `record_audit`, `school_config_versions`
- `00003`: `user_invitations`, `guardian_student_links`, `report_releases`, invitation RPCs with audit
- `00004`: `assessment_categories`, `grading_bands`, `report_layouts`, `school_onboarding`

## Rollback strategy

Supabase does not auto-rollback. For local/dev, reset with `supabase db reset`. For production, ship forward-fixing migrations; destructive changes require explicit dual-write / backfill plans documented in the PR.
