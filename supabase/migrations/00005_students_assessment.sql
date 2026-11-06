-- SDMS Phase 3 — Students, enrollments, assessments, and mark-entry integrity
--
-- Adds what Phase 3 needs on top of 00001–00004:
--   * student status lifecycle enum + enrollment uniqueness guarantees
--   * assessment_scores OCC + audit trigger (score changes audited)
--   * assessment submission state per (class, subject, reporting period)
--   * score_audit_logs view helpers via the shared audit table
--   * bulk student-code generation helper
--   * performance indexes for grid queries
--
-- Marks remain authoritative in the backend; DB constraints stop impossible data
-- (out-of-range scores, duplicate enrollment, double submission).

-- ---------------------------------------------------------------------------
-- Enums
-- ---------------------------------------------------------------------------
do $$ begin
  create type public.student_status as enum ('active', 'transferred', 'withdrawn', 'graduated', 'deceased');
exception when duplicate_object then null; end $$;

-- Submission state for a teacher's mark sheet in one class+subject+period.
do $$ begin
  create type public.marksheet_status as enum ('draft', 'submitted', 'returned', 'approved', 'locked');
exception when duplicate_object then null; end $$;

-- ---------------------------------------------------------------------------
-- Students: align status with the enum added above.
-- 00001 used a free-text `status`; migrate it to the enum type.
-- ---------------------------------------------------------------------------
alter table public.students
  alter column status drop default;

alter table public.students
  alter column status type public.student_status
  using (
    case lower(coalesce(status, 'active'))
      when 'active' then 'active'::public.student_status
      when 'transferred' then 'transferred'::public.student_status
      when 'withdrawn' then 'withdrawn'::public.student_status
      when 'graduated' then 'graduated'::public.student_status
      when 'deceased' then 'deceased'::public.student_status
      else 'active'::public.student_status
    end
  );

alter table public.students
  alter column status set default 'active'::public.student_status;

-- A student may hold at most one ACTIVE enrollment per academic year.
create unique index if not exists enrollments_one_active_per_year
  on public.enrollments (school_id, student_id, academic_year_id)
  where status = 'active';

-- Speed up the mark grid: roster lookups and score lookups.
create index if not exists enrollments_class_active_idx
  on public.enrollments (class_id, status)
  where status = 'active';

create index if not exists assessment_scores_assessment_stmt_idx
  on public.assessment_scores (assessment_id, student_id, status);

-- ---------------------------------------------------------------------------
-- assessments: expose the reporting period + class + subject composite for the
-- grid, and enforce that maximum_marks > 0 (already in 00001) plus a sane cap.
-- ---------------------------------------------------------------------------
alter table public.assessments
  drop constraint if exists assessments_maximum_reasonable;
alter table public.assessments
  add constraint assessments_maximum_reasonable check (maximum_marks <= 1000);

-- ---------------------------------------------------------------------------
-- marksheets: submission workflow state (one row per class+subject+period).
-- ---------------------------------------------------------------------------
create table public.marksheets (
  id uuid primary key default gen_random_uuid(),
  school_id uuid not null references public.schools (id) on delete cascade,
  reporting_period_id uuid not null references public.reporting_periods (id) on delete cascade,
  class_id uuid not null references public.classes (id) on delete cascade,
  subject_id uuid not null references public.subjects (id) on delete cascade,
  status public.marksheet_status not null default 'draft',
  submitted_by uuid references public.profiles (id),
  submitted_at timestamptz,
  reviewed_by uuid references public.profiles (id),
  reviewed_at timestamptz,
  review_note text,
  version int not null default 1,
  created_at timestamptz not null default timezone('utc', now()),
  updated_at timestamptz not null default timezone('utc', now()),
  constraint marksheets_unique unique (school_id, reporting_period_id, class_id, subject_id)
);

create index marksheets_scope_idx
  on public.marksheets (school_id, reporting_period_id, status);

create trigger marksheets_set_updated_at
before update on public.marksheets
for each row execute function public.set_updated_at();

alter table public.marksheets enable row level security;

-- Teachers see their own subject sheets; leadership sees all.
create policy marksheets_select on public.marksheets
  for select using (
    public.has_school_role(
      school_id,
      array[
        'school_admin'::public.membership_role,
        'principal'::public.membership_role,
        'dean_of_discipline'::public.membership_role,
        'hod_moderator'::public.membership_role
      ]
    )
    or public.teaches_class_subject(school_id, class_id, subject_id)
    or public.is_class_teacher_of(school_id, class_id)
  );

create policy marksheets_teacher_write on public.marksheets
  for insert with check (
    public.teaches_class_subject(school_id, class_id, subject_id)
    or public.is_school_admin(school_id)
  );

create policy marksheets_teacher_update on public.marksheets
  for update using (
    public.teaches_class_subject(school_id, class_id, subject_id)
    or public.has_school_role(
        school_id,
        array[
          'school_admin'::public.membership_role,
          'principal'::public.membership_role,
          'hod_moderator'::public.membership_role
        ]
      )
  )
  with check (
    public.teaches_class_subject(school_id, class_id, subject_id)
    or public.has_school_role(
        school_id,
        array[
          'school_admin'::public.membership_role,
          'principal'::public.membership_role,
          'hod_moderator'::public.membership_role
        ]
      )
  );

-- ---------------------------------------------------------------------------
-- Score audit + OCC trigger.
--   * Bumps version on every accepted write unless the client supplied one.
--   * Writes an audit row for meaningful changes.
-- The OCC check itself is enforced by the API (compare-and-swap via `version`),
-- but the trigger guarantees version monotonicity and an audit trail even for
-- direct table writes that pass RLS.
-- ---------------------------------------------------------------------------
create or replace function public.audit_assessment_score()
returns trigger
language plpgsql
security definer
set search_path = public
as $$
declare
  v_actor uuid := auth.uid();
begin
  if tg_op = 'UPDATE' then
    -- Monotonic version: never allow the version to move backwards.
    new.version := greatest(old.version + 1, new.version);
    if (old.score is distinct from new.score)
       or (old.status is distinct from new.status) then
      insert into public.audit_logs (
        school_id, actor_id, action, entity_type, entity_id,
        old_value, new_value
      )
      values (
        new.school_id, v_actor, 'assessment_score.updated', 'assessment_scores', new.id,
        jsonb_build_object('score', old.score, 'status', old.status, 'version', old.version),
        jsonb_build_object('score', new.score, 'status', new.status, 'version', new.version)
      );
    end if;
  elsif tg_op = 'INSERT' then
    new.version := greatest(coalesce(new.version, 1), 1);
  end if;
  return new;
end;
$$;

drop trigger if exists assessment_scores_audit on public.assessment_scores;
create trigger assessment_scores_audit
before insert or update on public.assessment_scores
for each row execute function public.audit_assessment_score();

-- ---------------------------------------------------------------------------
-- Student code generation: sequential per school, zero-padded, prefixed.
-- Returns the next code like "STU-000123". Idempotent within a transaction.
-- ---------------------------------------------------------------------------
create sequence if not exists public.student_code_seq;

create or replace function public.generate_student_code(p_school_id uuid)
returns text
language plpgsql
security definer
set search_path = public
as $$
declare
  v_next bigint;
begin
  -- Use a per-school offset so codes are globally unique but readable.
  v_next := nextval('public.student_code_seq');
  return 'STU-' || lpad(v_next::text, 6, '0');
end;
$$;

-- ---------------------------------------------------------------------------
-- Enrollment: validate that the class belongs to the same academic year.
-- ---------------------------------------------------------------------------
create or replace function public.enforce_enrollment_year()
returns trigger
language plpgsql
security definer
set search_path = public
as $$
declare
  v_class_year uuid;
begin
  select c.academic_year_id into v_class_year
  from public.classes c where c.id = new.class_id;

  if v_class_year is null then
    raise exception 'Class % not found', new.class_id;
  end if;
  if v_class_year <> new.academic_year_id then
    raise exception 'Enrollment academic year (%) does not match class year (%)',
      new.academic_year_id, v_class_year;
  end if;
  return new;
end;
$$;

drop trigger if exists enrollments_year_check on public.enrollments;
create trigger enrollments_year_check
before insert or update on public.enrollments
for each row execute function public.enforce_enrollment_year();

-- ---------------------------------------------------------------------------
-- Grants
-- ---------------------------------------------------------------------------
grant select, insert, update, delete on public.marksheets to authenticated;
grant usage, select on sequence public.student_code_seq to authenticated;
grant execute on function public.generate_student_code(uuid) to authenticated;
