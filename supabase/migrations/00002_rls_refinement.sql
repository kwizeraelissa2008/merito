-- SDMS Phase 2 — RLS refinement
-- Tightens assignment-scoped visibility for students, assessments, reports, and
-- adds helper predicates + audit triggers used by the configuration surface.
--
-- Principles (unchanged from 00001):
--   * Every tenant-owned row carries school_id; access requires an ACTIVE membership.
--   * Assignment tables (teaching_assignments / class_teacher_assignments) further
--     restrict who may read/alter academic records.
--   * Deny by default. UI hiding is never the security boundary.

-- ---------------------------------------------------------------------------
-- Additional helper predicates
-- ---------------------------------------------------------------------------

-- True when the caller has an active membership of any of the given roles in ANY
-- school. Used to gate platform-adjacent reads without leaking a specific tenant.
create or replace function public.has_any_school_role(p_roles public.membership_role[])
returns boolean
language sql
stable
security definer
set search_path = public
as $$
  select exists (
    select 1 from public.school_memberships sm
    where sm.user_id = auth.uid()
      and sm.status = 'active'
      and sm.role = any (p_roles)
  );
$$;

-- True when the caller is an active member of the school (any role).
create or replace function public.is_school_member(p_school_id uuid)
returns boolean
language sql
stable
security definer
set search_path = public
as $$
  select exists (
    select 1 from public.school_memberships sm
    where sm.school_id = p_school_id
      and sm.user_id = auth.uid()
      and sm.status = 'active'
  );
$$;

-- School admins of a school are the only role allowed to mutate configuration.
create or replace function public.is_school_admin(p_school_id uuid)
returns boolean
language sql
stable
security definer
set search_path = public
as $$
  select exists (
    select 1 from public.school_memberships sm
    where sm.school_id = p_school_id
      and sm.user_id = auth.uid()
      and sm.status = 'active'
      and sm.role = 'school_admin'
  );
$$;

-- True when the student is actively enrolled in the class the caller teaches or leads.
create or replace function public.can_view_student(p_school_id uuid, p_student_id uuid)
returns boolean
language sql
stable
security definer
set search_path = public
as $$
  select
    public.has_school_role(
      p_school_id,
      array[
        'school_admin'::public.membership_role,
        'principal'::public.membership_role,
        'dean_of_discipline'::public.membership_role,
        'discipline_staff'::public.membership_role,
        'hod_moderator'::public.membership_role
      ]
    )
    or exists (
      select 1
      from public.enrollments e
      where e.school_id = p_school_id
        and e.student_id = p_student_id
        and e.status = 'active'
        and (
          public.is_class_teacher_of(p_school_id, e.class_id)
          or exists (
            select 1 from public.teaching_assignments ta
            where ta.school_id = p_school_id
              and ta.class_id = e.class_id
              and ta.teacher_user_id = auth.uid()
              and ta.active = true
          )
        )
    );
$$;

-- ---------------------------------------------------------------------------
-- Profiles: a member may read the profile of colleagues in a shared school.
-- (Needed to display teacher names in assignment pickers and audit views.)
-- ---------------------------------------------------------------------------
drop policy if exists profiles_select_self on public.profiles;

create policy profiles_select_self_or_colleague on public.profiles
  for select using (
    id = auth.uid()
    or public.is_platform_admin()
    or exists (
      select 1
      from public.school_memberships mine
      join public.school_memberships theirs on theirs.school_id = mine.school_id
      where mine.user_id = auth.uid()
        and mine.status = 'active'
        and theirs.user_id = profiles.id
        and theirs.status = 'active'
    )
  );

-- ---------------------------------------------------------------------------
-- Students: assignment-scoped read instead of "any member with a staff role".
-- ---------------------------------------------------------------------------
drop policy if exists students_member_select on public.students;

create policy students_scoped_select on public.students
  for select using (public.can_view_student(school_id, id));

-- ---------------------------------------------------------------------------
-- Enrollments: members of a class (teacher or class teacher) plus leadership.
-- ---------------------------------------------------------------------------
drop policy if exists enrollments_member_select on public.enrollments;

create policy enrollments_scoped_select on public.enrollments
  for select using (
    public.has_school_role(
      school_id,
      array[
        'school_admin'::public.membership_role,
        'principal'::public.membership_role,
        'dean_of_discipline'::public.membership_role,
        'discipline_staff'::public.membership_role,
        'hod_moderator'::public.membership_role
      ]
    )
    or public.is_class_teacher_of(school_id, class_id)
    or exists (
      select 1 from public.teaching_assignments ta
      where ta.school_id = enrollments.school_id
        and ta.class_id = enrollments.class_id
        and ta.teacher_user_id = auth.uid()
        and ta.active = true
    )
  );

-- ---------------------------------------------------------------------------
-- Assessment scores: leadership reads school-wide; teachers by assignment.
-- (00001 covered this; here we make reads explicit and add class-teacher read of
-- all subjects in their class is INTENTIONALLY excluded — class teachers must not
-- silently acquire the ability to REWRITE others' scores. They may read the
-- subject scores through the report layer, which is snapshot-based.)
-- ---------------------------------------------------------------------------
drop policy if exists assessment_scores_teacher_write on public.assessment_scores;

create policy assessment_scores_teacher_write on public.assessment_scores
  for all using (
    exists (
      select 1 from public.assessments a
      where a.id = assessment_id
        and public.teaches_class_subject(a.school_id, a.class_id, a.subject_id)
    )
    or public.is_school_admin(school_id)
  )
  with check (
    exists (
      select 1 from public.assessments a
      where a.id = assessment_id
        and public.teaches_class_subject(a.school_id, a.class_id, a.subject_id)
    )
    or public.is_school_admin(school_id)
  );

-- ---------------------------------------------------------------------------
-- Report instances: principals/administrators read school-wide; class teachers
-- read their own class; the reporter itself may read only when released.
-- ---------------------------------------------------------------------------
drop policy if exists report_instances_select on public.report_instances;

create policy report_instances_select on public.report_instances
  for select using (
    public.has_school_role(
      school_id,
      array[
        'school_admin'::public.membership_role,
        'principal'::public.membership_role,
        'dean_of_discipline'::public.membership_role
      ]
    )
    or public.is_class_teacher_of(school_id, class_id)
  );

-- ---------------------------------------------------------------------------
-- Audit helper: write a school-scoped audit row from within a transaction.
-- Callers provide the actor explicitly; clients can never mutate audit rows.
-- ---------------------------------------------------------------------------
create or replace function public.record_audit(
  p_school_id uuid,
  p_actor_id uuid,
  p_action text,
  p_entity_type text,
  p_entity_id uuid,
  p_old_value jsonb default null,
  p_new_value jsonb default null,
  p_reason text default null,
  p_request_id text default null
)
returns uuid
language plpgsql
security definer
set search_path = public
as $$
declare
  v_id uuid;
begin
  insert into public.audit_logs (
    school_id, actor_id, action, entity_type, entity_id,
    old_value, new_value, reason, request_id
  )
  values (
    p_school_id, p_actor_id, p_action, p_entity_type, p_entity_id,
    p_old_value, p_new_value, p_reason, p_request_id
  )
  returning id into v_id;
  return v_id;
end;
$$;

-- ---------------------------------------------------------------------------
-- Configuration versioning: bump the school's configuration_version whenever a
-- structural configuration row changes. reporting_periods already carries its
-- own configuration_version column (00001); this centralises the counter used
-- by immutable report snapshots.
-- ---------------------------------------------------------------------------
create table if not exists public.school_config_versions (
  id uuid primary key default gen_random_uuid(),
  school_id uuid not null references public.schools (id) on delete cascade,
  version int not null,
  changed_by uuid references public.profiles (id),
  summary text not null default '',
  created_at timestamptz not null default timezone('utc', now()),
  constraint school_config_versions_unique unique (school_id, version)
);

create index if not exists school_config_versions_school_idx
  on public.school_config_versions (school_id, version desc);

alter table public.school_config_versions enable row level security;

create policy school_config_versions_select on public.school_config_versions
  for select using (public.is_school_member(school_id));

create policy school_config_versions_admin_write on public.school_config_versions
  for insert with check (public.is_school_admin(school_id));

-- Compat: ensure the membership_role enum tolerates the spelling used above.
-- (Kept defensive: 00001 defines 'discipline_staff'; nothing to change here.)
