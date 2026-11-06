# Entity-Relationship Overview

Logical model for SDMS. All tenant-owned entities include `school_id` unless noted.

## Mermaid ERD (core)

```mermaid
erDiagram
  schools ||--o{ school_memberships : has
  profiles ||--o{ school_memberships : joins
  schools ||--o{ academic_years : owns
  academic_years ||--o{ terms : contains
  terms ||--o{ reporting_periods : contains
  schools ||--o{ curricula : owns
  curricula ||--o{ grades : defines
  curricula ||--o{ combinations : defines
  schools ||--o{ subjects : owns
  curricula ||--o{ curriculum_subjects : maps
  subjects ||--o{ curriculum_subjects : mapped
  grades ||--o{ curriculum_subjects : scoped
  combinations ||--o{ curriculum_subjects : scoped
  academic_years ||--o{ classes : has
  grades ||--o{ classes : level
  combinations ||--o{ classes : stream
  schools ||--o{ students : enrolls
  students ||--o{ enrollments : history
  classes ||--o{ enrollments : roster
  profiles ||--o{ teaching_assignments : teaches
  classes ||--o{ teaching_assignments : class
  subjects ||--o{ teaching_assignments : subject
  profiles ||--o{ class_teacher_assignments : leads
  classes ||--o{ class_teacher_assignments : class
  reporting_periods ||--o{ assessments : period
  classes ||--o{ assessments : class
  subjects ||--o{ assessments : subject
  assessments ||--o{ assessment_scores : scores
  students ||--o{ assessment_scores : student
  schools ||--o{ grading_policies : versions
  schools ||--o{ incident_types : defines
  students ||--o{ behavioral_incidents : incidents
  reporting_periods ||--o{ behavioral_incidents : period
  behavioral_incidents ||--o{ incident_reviews : reviews
  students ||--o{ attendance_records : attendance
  students ||--o{ student_comments : comments
  schools ||--o{ report_templates : templates
  students ||--o{ report_instances : reports
  reporting_periods ||--o{ report_instances : period
  report_instances ||--o{ report_approvals : approvals
  schools ||--o{ audit_logs : audits
  schools ||--o{ background_jobs : jobs
  schools ||--o{ notifications : notifies
  schools ||--o{ school_onboarding : tracks
  schools ||--o{ user_invitations : issues
  profiles ||--o{ user_invitations : accepts
  schools ||--o{ guardian_student_links : verifies
  profiles ||--o{ guardian_student_links : guardians
  students ||--o{ guardian_student_links : linked_to
  report_instances ||--o| report_releases : released_via
  grading_policies ||--o{ grading_bands : defines
  schools ||--o{ assessment_categories : configures
  schools ||--o{ report_layouts : drafts
```

## Hierarchy

```
School
 └── Academic Year
      ├── Terms → Reporting Periods
      ├── Curricula (O-Level / A-Level / Legacy S6) → Grades → Combinations
      ├── Classes (grade + optional combination + stream name)
      ├── Enrollments (student ↔ class, dated, never overwrite history)
      └── Assignments (teaching / class teacher)
```

## JSONB usage

| Table | JSONB purpose |
|---|---|
| `schools.configuration` | Feature flags, portal settings, timezone prefs |
| `reporting_periods.deadlines` | Named deadline timestamps |
| `curricula.configuration` | Level-specific options |
| `grading_policies.policy_configuration` | Weights, bands, rounding, eligibility |
| `report_templates.configuration_json` | Layout, columns, signatures |
| `report_instances.snapshot_json` | Immutable published payload |
| `notifications.payload` | Typed notification data |
| `background_jobs.payload` | Job inputs |
| `audit_logs.old_value` / `new_value` | Change diffs |

Relational FKs are used for students, classes, scores, incidents, and approvals—not buried in JSONB.

## Key uniqueness / checks (summary)

- `(school_id, slug)` unique on schools; `(school_id, student_code)` unique on students
- One score per `(assessment_id, student_id)`
- Score status ∈ {scored, missing, absent, exempt, pending}; scored requires numeric in [0, maximum]
- Behavior deduction > 0; score display capped at 0 when deductions exceed base
- Report status transitions enforced in application transactions (+ DB check on allowed statuses)
- Idempotency: unique `(school_id, job_type, idempotency_key)` where key present

See migration `00001_foundation.sql` for full DDL.
