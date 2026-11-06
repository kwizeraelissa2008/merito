-- SDMS Foundation schema + RLS helpers
-- Product defaults only; schools override via configuration tables.

create extension if not exists "pgcrypto";

-- ---------------------------------------------------------------------------
-- Enums
-- ---------------------------------------------------------------------------
create type public.membership_role as enum (
  'school_admin',
  'principal',
  'dean_of_discipline',
  'discipline_staff',
  'subject_teacher',
  'class_teacher',
  'hod_moderator',
  'student',
  'guardian'
);

create type public.membership_status as enum ('invited', 'active', 'suspended', 'deactivated');
create type public.school_status as enum ('draft', 'active', 'suspended', 'archived');
create type public.academic_status as enum ('draft', 'active', 'closed', 'archived');

create type public.reporting_period_status as enum (
  'draft', 'open', 'in_progress', 'submitted', 'under_review',
  'returned', 'approved', 'locked', 'published', 'archived'
);

create type public.academic_level as enum ('olevel', 'alevel', 'legacy_s6', 'custom');
create type public.subject_category as enum ('core', 'minor', 'optional', 'other');
create type public.enrollment_status as enum ('active', 'transferred', 'withdrawn', 'completed');
create type public.score_status as enum ('scored', 'missing', 'absent', 'exempt', 'pending');
create type public.assessment_lifecycle as enum ('draft', 'open', 'submitted', 'locked');
create type public.incident_status as enum (
  'pending', 'approved', 'rejected', 'returned', 'superseded'
);
create type public.attendance_status as enum ('present', 'absent', 'late', 'excused', 'other');
create type public.comment_type as enum (
  'subject', 'class_teacher', 'discipline', 'principal'
);
create type public.report_status as enum (
  'draft', 'in_review', 'returned', 'approved', 'locked', 'published', 'superseded'
);
create type public.job_status as enum (
  'pending', 'running', 'succeeded', 'failed', 'cancelled'
);
create type public.notification_delivery as enum (
  'pending', 'sent', 'failed', 'read'
);

-- ---------------------------------------------------------------------------
-- Helper: updated_at trigger
-- ---------------------------------------------------------------------------
create or replace function public.set_updated_at()
returns trigger
language plpgsql
as $$
begin
  new.updated_at = timezone('utc', now());
  return new;
end;
$$;

-- ---------------------------------------------------------------------------
-- Core identity
-- ---------------------------------------------------------------------------
create table public.schools (
  id uuid primary key default gen_random_uuid(),
  name text not null,
  slug text not null,
  logo_path text,
  contact_details jsonb not null default '{}'::jsonb,
  timezone text not null default 'Africa/Kigali',
  configuration jsonb not null default '{}'::jsonb,
  status public.school_status not null default 'draft',
  created_at timestamptz not null default timezone('utc', now()),
  updated_at timestamptz not null default timezone('utc', now()),
  constraint schools_slug_format check (slug ~ '^[a-z0-9]+(?:-[a-z0-9]+)*$'),
  constraint schools_slug_unique unique (slug)
);

create trigger schools_set_updated_at
before update on public.schools
for each row execute function public.set_updated_at();

create table public.profiles (
  id uuid primary key references auth.users (id) on delete cascade,
  full_name text not null,
  email text not null,
  account_status text not null default 'active',
  created_at timestamptz not null default timezone('utc', now()),
  updated_at timestamptz not null default timezone('utc', now())
);

create trigger profiles_set_updated_at
before update on public.profiles
for each row execute function public.set_updated_at();

create table public.platform_admins (
  user_id uuid primary key references public.profiles (id) on delete cascade,
  active boolean not null default true,
  created_at timestamptz not null default timezone('utc', now())
);

create table public.school_memberships (
  id uuid primary key default gen_random_uuid(),
  school_id uuid not null references public.schools (id) on delete cascade,
  user_id uuid not null references public.profiles (id) on delete cascade,
  role public.membership_role not null,
  status public.membership_status not null default 'invited',
  created_at timestamptz not null default timezone('utc', now()),
  updated_at timestamptz not null default timezone('utc', now()),
  constraint school_memberships_unique unique (school_id, user_id, role)
);

create index school_memberships_user_idx on public.school_memberships (user_id);
create index school_memberships_school_idx on public.school_memberships (school_id, status);

create trigger school_memberships_set_updated_at
before update on public.school_memberships
for each row execute function public.set_updated_at();

-- ---------------------------------------------------------------------------
-- Academic calendar
-- ---------------------------------------------------------------------------
create table public.academic_years (
  id uuid primary key default gen_random_uuid(),
  school_id uuid not null references public.schools (id) on delete cascade,
  name text not null,
  start_date date not null,
  end_date date not null,
  status public.academic_status not null default 'draft',
  created_at timestamptz not null default timezone('utc', now()),
  updated_at timestamptz not null default timezone('utc', now()),
  constraint academic_years_dates check (end_date > start_date),
  constraint academic_years_name_unique unique (school_id, name)
);

create table public.terms (
  id uuid primary key default gen_random_uuid(),
  school_id uuid not null references public.schools (id) on delete cascade,
  academic_year_id uuid not null references public.academic_years (id) on delete cascade,
  term_number int not null check (term_number between 1 and 6),
  name text not null,
  start_date date not null,
  end_date date not null,
  status public.academic_status not null default 'draft',
  created_at timestamptz not null default timezone('utc', now()),
  updated_at timestamptz not null default timezone('utc', now()),
  constraint terms_dates check (end_date > start_date),
  constraint terms_unique unique (academic_year_id, term_number)
);

create table public.reporting_periods (
  id uuid primary key default gen_random_uuid(),
  school_id uuid not null references public.schools (id) on delete cascade,
  term_id uuid not null references public.terms (id) on delete cascade,
  period_number int not null check (period_number between 1 and 12),
  name text not null,
  start_date date not null,
  end_date date not null,
  deadlines jsonb not null default '{}'::jsonb,
  status public.reporting_period_status not null default 'draft',
  configuration_version int not null default 1,
  created_at timestamptz not null default timezone('utc', now()),
  updated_at timestamptz not null default timezone('utc', now()),
  constraint reporting_periods_dates check (end_date >= start_date),
  constraint reporting_periods_unique unique (term_id, period_number)
);

create index reporting_periods_school_status_idx
  on public.reporting_periods (school_id, status);

-- ---------------------------------------------------------------------------
-- Curriculum structure
-- ---------------------------------------------------------------------------
create table public.curricula (
  id uuid primary key default gen_random_uuid(),
  school_id uuid not null references public.schools (id) on delete cascade,
  academic_year_id uuid references public.academic_years (id) on delete set null,
  name text not null,
  level public.academic_level not null,
  effective_from date,
  effective_to date,
  configuration jsonb not null default '{}'::jsonb,
  created_at timestamptz not null default timezone('utc', now()),
  updated_at timestamptz not null default timezone('utc', now())
);

create table public.grades (
  id uuid primary key default gen_random_uuid(),
  school_id uuid not null references public.schools (id) on delete cascade,
  curriculum_id uuid not null references public.curricula (id) on delete cascade,
  name text not null,
  level public.academic_level not null,
  ordering int not null default 0,
  created_at timestamptz not null default timezone('utc', now()),
  constraint grades_unique unique (curriculum_id, name)
);

create table public.combinations (
  id uuid primary key default gen_random_uuid(),
  school_id uuid not null references public.schools (id) on delete cascade,
  curriculum_id uuid not null references public.curricula (id) on delete cascade,
  code text not null,
  name text not null,
  description text,
  created_at timestamptz not null default timezone('utc', now()),
  constraint combinations_unique unique (curriculum_id, code)
);

create table public.subjects (
  id uuid primary key default gen_random_uuid(),
  school_id uuid not null references public.schools (id) on delete cascade,
  name text not null,
  code text not null,
  category public.subject_category not null default 'core',
  active boolean not null default true,
  created_at timestamptz not null default timezone('utc', now()),
  updated_at timestamptz not null default timezone('utc', now()),
  constraint subjects_code_unique unique (school_id, code)
);

create table public.curriculum_subjects (
  id uuid primary key default gen_random_uuid(),
  school_id uuid not null references public.schools (id) on delete cascade,
  curriculum_id uuid not null references public.curricula (id) on delete cascade,
  grade_id uuid references public.grades (id) on delete cascade,
  combination_id uuid references public.combinations (id) on delete cascade,
  subject_id uuid not null references public.subjects (id) on delete cascade,
  maximum_marks numeric(8, 2),
  ordering int not null default 0,
  configuration jsonb not null default '{}'::jsonb,
  created_at timestamptz not null default timezone('utc', now())
);

create table public.classes (
  id uuid primary key default gen_random_uuid(),
  school_id uuid not null references public.schools (id) on delete cascade,
  academic_year_id uuid not null references public.academic_years (id) on delete cascade,
  grade_id uuid not null references public.grades (id) on delete restrict,
  combination_id uuid references public.combinations (id) on delete set null,
  name text not null,
  status public.academic_status not null default 'active',
  created_at timestamptz not null default timezone('utc', now()),
  updated_at timestamptz not null default timezone('utc', now()),
  constraint classes_name_unique unique (school_id, academic_year_id, name)
);

create index classes_school_year_idx on public.classes (school_id, academic_year_id);

-- ---------------------------------------------------------------------------
-- Students & enrollments
-- ---------------------------------------------------------------------------
create table public.students (
  id uuid primary key default gen_random_uuid(),
  school_id uuid not null references public.schools (id) on delete cascade,
  student_code text not null,
  full_name text not null,
  photo_path text,
  date_of_birth date,
  gender text,
  status text not null default 'active',
  profile_fields jsonb not null default '{}'::jsonb,
  created_at timestamptz not null default timezone('utc', now()),
  updated_at timestamptz not null default timezone('utc', now()),
  constraint students_code_unique unique (school_id, student_code)
);

create index students_school_name_idx on public.students (school_id, full_name);

create table public.enrollments (
  id uuid primary key default gen_random_uuid(),
  school_id uuid not null references public.schools (id) on delete cascade,
  student_id uuid not null references public.students (id) on delete cascade,
  academic_year_id uuid not null references public.academic_years (id) on delete cascade,
  class_id uuid not null references public.classes (id) on delete restrict,
  start_date date not null,
  end_date date,
  status public.enrollment_status not null default 'active',
  created_at timestamptz not null default timezone('utc', now()),
  constraint enrollments_dates check (end_date is null or end_date >= start_date)
);

create index enrollments_student_idx on public.enrollments (student_id, status);
create index enrollments_class_idx on public.enrollments (class_id, status);

-- ---------------------------------------------------------------------------
-- Assignments
-- ---------------------------------------------------------------------------
create table public.teaching_assignments (
  id uuid primary key default gen_random_uuid(),
  school_id uuid not null references public.schools (id) on delete cascade,
  teacher_user_id uuid not null references public.profiles (id) on delete cascade,
  class_id uuid not null references public.classes (id) on delete cascade,
  subject_id uuid not null references public.subjects (id) on delete cascade,
  academic_year_id uuid not null references public.academic_years (id) on delete cascade,
  active boolean not null default true,
  starts_on date,
  ends_on date,
  created_at timestamptz not null default timezone('utc', now()),
  constraint teaching_assignments_unique
    unique (school_id, teacher_user_id, class_id, subject_id, academic_year_id)
);

create index teaching_assignments_teacher_idx
  on public.teaching_assignments (teacher_user_id, active);

create table public.class_teacher_assignments (
  id uuid primary key default gen_random_uuid(),
  school_id uuid not null references public.schools (id) on delete cascade,
  teacher_user_id uuid not null references public.profiles (id) on delete cascade,
  class_id uuid not null references public.classes (id) on delete cascade,
  academic_year_id uuid not null references public.academic_years (id) on delete cascade,
  active boolean not null default true,
  starts_on date,
  ends_on date,
  created_at timestamptz not null default timezone('utc', now()),
  constraint class_teacher_assignments_unique
    unique (school_id, class_id, academic_year_id, teacher_user_id)
);

-- ---------------------------------------------------------------------------
-- Assessment
-- ---------------------------------------------------------------------------
create table public.grading_policies (
  id uuid primary key default gen_random_uuid(),
  school_id uuid not null references public.schools (id) on delete cascade,
  name text not null,
  version int not null,
  effective_from date,
  effective_to date,
  policy_configuration jsonb not null default '{}'::jsonb,
  created_at timestamptz not null default timezone('utc', now()),
  constraint grading_policies_version_unique unique (school_id, name, version)
);

create table public.assessments (
  id uuid primary key default gen_random_uuid(),
  school_id uuid not null references public.schools (id) on delete cascade,
  reporting_period_id uuid not null references public.reporting_periods (id) on delete cascade,
  class_id uuid not null references public.classes (id) on delete cascade,
  subject_id uuid not null references public.subjects (id) on delete cascade,
  category text not null,
  title text not null,
  maximum_marks numeric(8, 2) not null check (maximum_marks > 0),
  weight numeric(8, 4) not null default 0 check (weight >= 0),
  due_date date,
  created_by uuid references public.profiles (id),
  status public.assessment_lifecycle not null default 'draft',
  version int not null default 1,
  created_at timestamptz not null default timezone('utc', now()),
  updated_at timestamptz not null default timezone('utc', now())
);

create index assessments_scope_idx
  on public.assessments (school_id, reporting_period_id, class_id, subject_id);

create table public.assessment_scores (
  id uuid primary key default gen_random_uuid(),
  school_id uuid not null references public.schools (id) on delete cascade,
  assessment_id uuid not null references public.assessments (id) on delete cascade,
  student_id uuid not null references public.students (id) on delete cascade,
  score numeric(8, 2),
  status public.score_status not null default 'missing',
  version int not null default 1,
  updated_by uuid references public.profiles (id),
  updated_at timestamptz not null default timezone('utc', now()),
  created_at timestamptz not null default timezone('utc', now()),
  constraint assessment_scores_unique unique (assessment_id, student_id),
  constraint assessment_scores_value_check check (
    (status = 'scored' and score is not null and score >= 0)
    or (status <> 'scored' and (score is null or score >= 0))
  )
);

create index assessment_scores_student_idx on public.assessment_scores (student_id);

-- Enforce score <= assessment maximum via trigger
create or replace function public.enforce_score_maximum()
returns trigger
language plpgsql
as $$
declare
  vmax numeric(8, 2);
begin
  if new.status = 'scored' then
    select a.maximum_marks into vmax from public.assessments a where a.id = new.assessment_id;
    if new.score is null or new.score > vmax then
      raise exception 'Score % exceeds maximum % for assessment %', new.score, vmax, new.assessment_id;
    end if;
  end if;
  return new;
end;
$$;

create trigger assessment_scores_max_check
before insert or update on public.assessment_scores
for each row execute function public.enforce_score_maximum();

-- ---------------------------------------------------------------------------
-- Behavior
-- ---------------------------------------------------------------------------
create table public.incident_types (
  id uuid primary key default gen_random_uuid(),
  school_id uuid not null references public.schools (id) on delete cascade,
  name text not null,
  default_deduction numeric(8, 2) not null check (default_deduction > 0),
  active boolean not null default true,
  created_at timestamptz not null default timezone('utc', now()),
  constraint incident_types_unique unique (school_id, name)
);

create table public.behavioral_incidents (
  id uuid primary key default gen_random_uuid(),
  school_id uuid not null references public.schools (id) on delete cascade,
  student_id uuid not null references public.students (id) on delete cascade,
  reporting_period_id uuid not null references public.reporting_periods (id) on delete cascade,
  incident_type_id uuid not null references public.incident_types (id) on delete restrict,
  incident_date date not null,
  description text not null default '',
  proposed_deduction numeric(8, 2) not null check (proposed_deduction > 0),
  status public.incident_status not null default 'pending',
  created_by uuid not null references public.profiles (id),
  version int not null default 1,
  idempotency_key text,
  created_at timestamptz not null default timezone('utc', now()),
  updated_at timestamptz not null default timezone('utc', now()),
  constraint behavioral_incidents_idempotent
    unique (school_id, idempotency_key)
);

create index behavioral_incidents_queue_idx
  on public.behavioral_incidents (school_id, status, reporting_period_id);

create table public.incident_reviews (
  id uuid primary key default gen_random_uuid(),
  school_id uuid not null references public.schools (id) on delete cascade,
  incident_id uuid not null references public.behavioral_incidents (id) on delete cascade,
  reviewer_id uuid not null references public.profiles (id),
  decision public.incident_status not null,
  reason text,
  created_at timestamptz not null default timezone('utc', now())
);

-- ---------------------------------------------------------------------------
-- Attendance
-- ---------------------------------------------------------------------------
create table public.attendance_records (
  id uuid primary key default gen_random_uuid(),
  school_id uuid not null references public.schools (id) on delete cascade,
  student_id uuid not null references public.students (id) on delete cascade,
  class_id uuid not null references public.classes (id) on delete cascade,
  attendance_date date not null,
  status public.attendance_status not null,
  recorded_by uuid references public.profiles (id),
  version int not null default 1,
  notes text,
  created_at timestamptz not null default timezone('utc', now()),
  updated_at timestamptz not null default timezone('utc', now()),
  constraint attendance_records_unique unique (school_id, student_id, attendance_date)
);

create index attendance_records_class_date_idx
  on public.attendance_records (class_id, attendance_date);

-- ---------------------------------------------------------------------------
-- Comments & reports
-- ---------------------------------------------------------------------------
create table public.student_comments (
  id uuid primary key default gen_random_uuid(),
  school_id uuid not null references public.schools (id) on delete cascade,
  student_id uuid not null references public.students (id) on delete cascade,
  reporting_period_id uuid not null references public.reporting_periods (id) on delete cascade,
  subject_id uuid references public.subjects (id) on delete set null,
  author_id uuid not null references public.profiles (id),
  comment_type public.comment_type not null,
  content text not null default '',
  status text not null default 'draft',
  version int not null default 1,
  created_at timestamptz not null default timezone('utc', now()),
  updated_at timestamptz not null default timezone('utc', now())
);

create table public.report_templates (
  id uuid primary key default gen_random_uuid(),
  school_id uuid not null references public.schools (id) on delete cascade,
  name text not null,
  version int not null,
  configuration_json jsonb not null default '{}'::jsonb,
  active boolean not null default true,
  created_at timestamptz not null default timezone('utc', now()),
  constraint report_templates_version_unique unique (school_id, name, version)
);

create table public.report_instances (
  id uuid primary key default gen_random_uuid(),
  school_id uuid not null references public.schools (id) on delete cascade,
  student_id uuid not null references public.students (id) on delete cascade,
  reporting_period_id uuid not null references public.reporting_periods (id) on delete cascade,
  class_id uuid not null references public.classes (id) on delete restrict,
  template_id uuid references public.report_templates (id),
  template_version int,
  grading_policy_id uuid references public.grading_policies (id),
  grading_policy_version int,
  status public.report_status not null default 'draft',
  snapshot_json jsonb,
  snapshot_hash text,
  approved_by uuid references public.profiles (id),
  approved_at timestamptz,
  published_at timestamptz,
  version int not null default 1,
  created_at timestamptz not null default timezone('utc', now()),
  updated_at timestamptz not null default timezone('utc', now()),
  constraint report_instances_unique unique (school_id, student_id, reporting_period_id, version)
);

create index report_instances_period_status_idx
  on public.report_instances (school_id, reporting_period_id, status);

create table public.report_approvals (
  id uuid primary key default gen_random_uuid(),
  school_id uuid not null references public.schools (id) on delete cascade,
  report_instance_id uuid not null references public.report_instances (id) on delete cascade,
  reviewer_id uuid not null references public.profiles (id),
  action text not null,
  comment text,
  created_at timestamptz not null default timezone('utc', now())
);

-- ---------------------------------------------------------------------------
-- Ops
-- ---------------------------------------------------------------------------
create table public.notifications (
  id uuid primary key default gen_random_uuid(),
  school_id uuid not null references public.schools (id) on delete cascade,
  recipient_id uuid not null references public.profiles (id) on delete cascade,
  notification_type text not null,
  payload jsonb not null default '{}'::jsonb,
  read_at timestamptz,
  delivery_status public.notification_delivery not null default 'pending',
  created_at timestamptz not null default timezone('utc', now())
);

create index notifications_recipient_idx
  on public.notifications (recipient_id, delivery_status, created_at desc);

create table public.audit_logs (
  id uuid primary key default gen_random_uuid(),
  school_id uuid references public.schools (id) on delete set null,
  actor_id uuid references public.profiles (id) on delete set null,
  action text not null,
  entity_type text not null,
  entity_id uuid,
  old_value jsonb,
  new_value jsonb,
  reason text,
  request_id text,
  created_at timestamptz not null default timezone('utc', now())
);

create index audit_logs_school_created_idx
  on public.audit_logs (school_id, created_at desc);

create table public.background_jobs (
  id uuid primary key default gen_random_uuid(),
  school_id uuid not null references public.schools (id) on delete cascade,
  job_type text not null,
  payload jsonb not null default '{}'::jsonb,
  idempotency_key text,
  status public.job_status not null default 'pending',
  attempts int not null default 0,
  last_error text,
  created_at timestamptz not null default timezone('utc', now()),
  started_at timestamptz,
  completed_at timestamptz,
  constraint background_jobs_idempotent unique (school_id, job_type, idempotency_key)
);

-- ---------------------------------------------------------------------------
-- Auth helpers (SECURITY DEFINER, fixed search_path) — after tables exist
-- ---------------------------------------------------------------------------
create or replace function public.is_platform_admin()
returns boolean
language sql
stable
security definer
set search_path = public
as $$
  select exists (
    select 1 from public.platform_admins pa
    where pa.user_id = auth.uid() and pa.active = true
  );
$$;

create or replace function public.has_school_membership(p_school_id uuid)
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

create or replace function public.has_school_role(p_school_id uuid, p_roles public.membership_role[])
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
      and sm.role = any (p_roles)
  );
$$;

create or replace function public.teaches_class_subject(
  p_school_id uuid,
  p_class_id uuid,
  p_subject_id uuid
)
returns boolean
language sql
stable
security definer
set search_path = public
as $$
  select exists (
    select 1 from public.teaching_assignments ta
    where ta.school_id = p_school_id
      and ta.class_id = p_class_id
      and ta.subject_id = p_subject_id
      and ta.teacher_user_id = auth.uid()
      and ta.active = true
  );
$$;

create or replace function public.is_class_teacher_of(p_school_id uuid, p_class_id uuid)
returns boolean
language sql
stable
security definer
set search_path = public
as $$
  select exists (
    select 1 from public.class_teacher_assignments cta
    where cta.school_id = p_school_id
      and cta.class_id = p_class_id
      and cta.teacher_user_id = auth.uid()
      and cta.active = true
  );
$$;

-- ---------------------------------------------------------------------------
-- Profile bootstrap from auth.users
-- ---------------------------------------------------------------------------
create or replace function public.handle_new_user()
returns trigger
language plpgsql
security definer
set search_path = public
as $$
begin
  insert into public.profiles (id, full_name, email)
  values (
    new.id,
    coalesce(new.raw_user_meta_data->>'full_name', split_part(new.email, '@', 1)),
    new.email
  )
  on conflict (id) do nothing;
  return new;
end;
$$;

create trigger on_auth_user_created
after insert on auth.users
for each row execute function public.handle_new_user();

-- ---------------------------------------------------------------------------
-- RLS
-- ---------------------------------------------------------------------------
alter table public.schools enable row level security;
alter table public.profiles enable row level security;
alter table public.platform_admins enable row level security;
alter table public.school_memberships enable row level security;
alter table public.academic_years enable row level security;
alter table public.terms enable row level security;
alter table public.reporting_periods enable row level security;
alter table public.curricula enable row level security;
alter table public.grades enable row level security;
alter table public.combinations enable row level security;
alter table public.subjects enable row level security;
alter table public.curriculum_subjects enable row level security;
alter table public.classes enable row level security;
alter table public.students enable row level security;
alter table public.enrollments enable row level security;
alter table public.teaching_assignments enable row level security;
alter table public.class_teacher_assignments enable row level security;
alter table public.grading_policies enable row level security;
alter table public.assessments enable row level security;
alter table public.assessment_scores enable row level security;
alter table public.incident_types enable row level security;
alter table public.behavioral_incidents enable row level security;
alter table public.incident_reviews enable row level security;
alter table public.attendance_records enable row level security;
alter table public.student_comments enable row level security;
alter table public.report_templates enable row level security;
alter table public.report_instances enable row level security;
alter table public.report_approvals enable row level security;
alter table public.notifications enable row level security;
alter table public.audit_logs enable row level security;
alter table public.background_jobs enable row level security;

-- Profiles: users see self; members of same school can see colleague names (Phase 2 may tighten)
create policy profiles_select_self on public.profiles
  for select using (id = auth.uid() or public.is_platform_admin());

create policy profiles_update_self on public.profiles
  for update using (id = auth.uid());

create policy platform_admins_self_read on public.platform_admins
  for select using (user_id = auth.uid() or public.is_platform_admin());

-- Schools: members can read their school
create policy schools_select_member on public.schools
  for select using (public.has_school_membership(id) or public.is_platform_admin());

create policy schools_update_admin on public.schools
  for update using (
    public.has_school_role(id, array['school_admin'::public.membership_role])
    or public.is_platform_admin()
  );

create policy schools_insert_platform on public.schools
  for insert with check (public.is_platform_admin());

-- Memberships
create policy memberships_select on public.school_memberships
  for select using (
    user_id = auth.uid()
    or public.has_school_role(school_id, array['school_admin'::public.membership_role, 'principal'::public.membership_role, 'dean_of_discipline'::public.membership_role])
    or public.is_platform_admin()
  );

create policy memberships_admin_write on public.school_memberships
  for all using (
    public.has_school_role(school_id, array['school_admin'::public.membership_role])
    or public.is_platform_admin()
  )
  with check (
    public.has_school_role(school_id, array['school_admin'::public.membership_role])
    or public.is_platform_admin()
  );

-- Generic school-scoped read for members
create policy academic_years_member_select on public.academic_years
  for select using (public.has_school_membership(school_id));
create policy academic_years_admin_write on public.academic_years
  for all using (public.has_school_role(school_id, array['school_admin'::public.membership_role]))
  with check (public.has_school_role(school_id, array['school_admin'::public.membership_role]));

create policy terms_member_select on public.terms
  for select using (public.has_school_membership(school_id));
create policy terms_admin_write on public.terms
  for all using (public.has_school_role(school_id, array['school_admin'::public.membership_role]))
  with check (public.has_school_role(school_id, array['school_admin'::public.membership_role]));

create policy reporting_periods_member_select on public.reporting_periods
  for select using (public.has_school_membership(school_id));
create policy reporting_periods_admin_write on public.reporting_periods
  for all using (public.has_school_role(school_id, array['school_admin'::public.membership_role]))
  with check (public.has_school_role(school_id, array['school_admin'::public.membership_role]));

create policy curricula_member_select on public.curricula
  for select using (public.has_school_membership(school_id));
create policy curricula_admin_write on public.curricula
  for all using (public.has_school_role(school_id, array['school_admin'::public.membership_role]))
  with check (public.has_school_role(school_id, array['school_admin'::public.membership_role]));

create policy grades_member_select on public.grades
  for select using (public.has_school_membership(school_id));
create policy grades_admin_write on public.grades
  for all using (public.has_school_role(school_id, array['school_admin'::public.membership_role]))
  with check (public.has_school_role(school_id, array['school_admin'::public.membership_role]));

create policy combinations_member_select on public.combinations
  for select using (public.has_school_membership(school_id));
create policy combinations_admin_write on public.combinations
  for all using (public.has_school_role(school_id, array['school_admin'::public.membership_role]))
  with check (public.has_school_role(school_id, array['school_admin'::public.membership_role]));

create policy subjects_member_select on public.subjects
  for select using (public.has_school_membership(school_id));
create policy subjects_admin_write on public.subjects
  for all using (public.has_school_role(school_id, array['school_admin'::public.membership_role]))
  with check (public.has_school_role(school_id, array['school_admin'::public.membership_role]));

create policy curriculum_subjects_member_select on public.curriculum_subjects
  for select using (public.has_school_membership(school_id));
create policy curriculum_subjects_admin_write on public.curriculum_subjects
  for all using (public.has_school_role(school_id, array['school_admin'::public.membership_role]))
  with check (public.has_school_role(school_id, array['school_admin'::public.membership_role]));

create policy classes_member_select on public.classes
  for select using (public.has_school_membership(school_id));
create policy classes_admin_write on public.classes
  for all using (public.has_school_role(school_id, array['school_admin'::public.membership_role]))
  with check (public.has_school_role(school_id, array['school_admin'::public.membership_role]));

create policy students_member_select on public.students
  for select using (
    public.has_school_role(
      school_id,
      array[
        'school_admin'::public.membership_role,
        'principal'::public.membership_role,
        'dean_of_discipline'::public.membership_role,
        'discipline_staff'::public.membership_role,
        'subject_teacher'::public.membership_role,
        'class_teacher'::public.membership_role,
        'hod_moderator'::public.membership_role
      ]
    )
  );
create policy students_admin_write on public.students
  for all using (public.has_school_role(school_id, array['school_admin'::public.membership_role]))
  with check (public.has_school_role(school_id, array['school_admin'::public.membership_role]));

create policy enrollments_member_select on public.enrollments
  for select using (public.has_school_membership(school_id));
create policy enrollments_admin_write on public.enrollments
  for all using (public.has_school_role(school_id, array['school_admin'::public.membership_role]))
  with check (public.has_school_role(school_id, array['school_admin'::public.membership_role]));

create policy teaching_assignments_select on public.teaching_assignments
  for select using (
    teacher_user_id = auth.uid()
    or public.has_school_role(school_id, array['school_admin'::public.membership_role, 'principal'::public.membership_role, 'dean_of_discipline'::public.membership_role])
  );
create policy teaching_assignments_admin_write on public.teaching_assignments
  for all using (public.has_school_role(school_id, array['school_admin'::public.membership_role]))
  with check (public.has_school_role(school_id, array['school_admin'::public.membership_role]));

create policy class_teacher_assignments_select on public.class_teacher_assignments
  for select using (
    teacher_user_id = auth.uid()
    or public.has_school_role(school_id, array['school_admin'::public.membership_role, 'principal'::public.membership_role, 'dean_of_discipline'::public.membership_role])
  );
create policy class_teacher_assignments_admin_write on public.class_teacher_assignments
  for all using (public.has_school_role(school_id, array['school_admin'::public.membership_role]))
  with check (public.has_school_role(school_id, array['school_admin'::public.membership_role]));

create policy grading_policies_select on public.grading_policies
  for select using (public.has_school_membership(school_id));
create policy grading_policies_admin_write on public.grading_policies
  for all using (public.has_school_role(school_id, array['school_admin'::public.membership_role]))
  with check (public.has_school_role(school_id, array['school_admin'::public.membership_role]));

-- Assessments: teachers see assigned; leaders see school-wide
create policy assessments_select on public.assessments
  for select using (
    public.has_school_role(school_id, array['school_admin'::public.membership_role, 'principal'::public.membership_role, 'dean_of_discipline'::public.membership_role, 'hod_moderator'::public.membership_role])
    or public.teaches_class_subject(school_id, class_id, subject_id)
    or public.is_class_teacher_of(school_id, class_id)
  );

create policy assessments_teacher_write on public.assessments
  for insert with check (
    public.teaches_class_subject(school_id, class_id, subject_id)
    or public.has_school_role(school_id, array['school_admin'::public.membership_role])
  );

create policy assessments_teacher_update on public.assessments
  for update using (
    public.teaches_class_subject(school_id, class_id, subject_id)
    or public.has_school_role(school_id, array['school_admin'::public.membership_role])
  );

create policy assessment_scores_select on public.assessment_scores
  for select using (
    exists (
      select 1 from public.assessments a
      where a.id = assessment_id
        and (
          public.has_school_role(a.school_id, array['school_admin'::public.membership_role, 'principal'::public.membership_role, 'dean_of_discipline'::public.membership_role, 'hod_moderator'::public.membership_role])
          or public.teaches_class_subject(a.school_id, a.class_id, a.subject_id)
          or public.is_class_teacher_of(a.school_id, a.class_id)
        )
    )
  );

create policy assessment_scores_teacher_write on public.assessment_scores
  for all using (
    exists (
      select 1 from public.assessments a
      where a.id = assessment_id
        and public.teaches_class_subject(a.school_id, a.class_id, a.subject_id)
    )
  )
  with check (
    exists (
      select 1 from public.assessments a
      where a.id = assessment_id
        and public.teaches_class_subject(a.school_id, a.class_id, a.subject_id)
    )
  );

-- Behavior
create policy incident_types_select on public.incident_types
  for select using (public.has_school_membership(school_id));
create policy incident_types_admin_write on public.incident_types
  for all using (
    public.has_school_role(school_id, array['school_admin'::public.membership_role, 'dean_of_discipline'::public.membership_role])
  )
  with check (
    public.has_school_role(school_id, array['school_admin'::public.membership_role, 'dean_of_discipline'::public.membership_role])
  );

create policy behavioral_incidents_select on public.behavioral_incidents
  for select using (
    public.has_school_role(school_id, array['school_admin'::public.membership_role, 'principal'::public.membership_role, 'dean_of_discipline'::public.membership_role, 'discipline_staff'::public.membership_role, 'class_teacher'::public.membership_role])
  );

create policy behavioral_incidents_staff_insert on public.behavioral_incidents
  for insert with check (
    public.has_school_role(school_id, array['discipline_staff'::public.membership_role, 'dean_of_discipline'::public.membership_role])
    and created_by = auth.uid()
  );

create policy behavioral_incidents_staff_update_pending on public.behavioral_incidents
  for update using (
    (
      public.has_school_role(school_id, array['discipline_staff'::public.membership_role])
      and created_by = auth.uid()
      and status in ('pending', 'returned')
    )
    or public.has_school_role(school_id, array['dean_of_discipline'::public.membership_role])
  );

create policy incident_reviews_select on public.incident_reviews
  for select using (
    public.has_school_role(school_id, array['dean_of_discipline'::public.membership_role, 'principal'::public.membership_role, 'school_admin'::public.membership_role, 'discipline_staff'::public.membership_role])
  );

create policy incident_reviews_dod_insert on public.incident_reviews
  for insert with check (
    public.has_school_role(school_id, array['dean_of_discipline'::public.membership_role])
    and reviewer_id = auth.uid()
  );

-- Attendance
create policy attendance_select on public.attendance_records
  for select using (
    public.has_school_role(school_id, array['school_admin'::public.membership_role, 'principal'::public.membership_role, 'dean_of_discipline'::public.membership_role])
    or public.is_class_teacher_of(school_id, class_id)
    or exists (
      select 1 from public.teaching_assignments ta
      where ta.school_id = attendance_records.school_id
        and ta.class_id = attendance_records.class_id
        and ta.teacher_user_id = auth.uid()
        and ta.active = true
    )
  );

create policy attendance_write on public.attendance_records
  for all using (
    public.is_class_teacher_of(school_id, class_id)
    or public.has_school_role(school_id, array['school_admin'::public.membership_role, 'dean_of_discipline'::public.membership_role])
  )
  with check (
    public.is_class_teacher_of(school_id, class_id)
    or public.has_school_role(school_id, array['school_admin'::public.membership_role, 'dean_of_discipline'::public.membership_role])
  );

-- Comments & reports (baseline; refined in later migrations for guardians)
create policy student_comments_select on public.student_comments
  for select using (
    author_id = auth.uid()
    or public.has_school_role(school_id, array['school_admin'::public.membership_role, 'principal'::public.membership_role, 'dean_of_discipline'::public.membership_role, 'class_teacher'::public.membership_role])
  );

create policy student_comments_author_write on public.student_comments
  for all using (author_id = auth.uid())
  with check (author_id = auth.uid());

create policy report_templates_select on public.report_templates
  for select using (public.has_school_membership(school_id));
create policy report_templates_admin_write on public.report_templates
  for all using (public.has_school_role(school_id, array['school_admin'::public.membership_role]))
  with check (public.has_school_role(school_id, array['school_admin'::public.membership_role]));

create policy report_instances_select on public.report_instances
  for select using (
    public.has_school_role(school_id, array['school_admin'::public.membership_role, 'principal'::public.membership_role, 'dean_of_discipline'::public.membership_role])
    or public.is_class_teacher_of(school_id, class_id)
  );

create policy report_instances_leadership_write on public.report_instances
  for all using (
    public.has_school_role(school_id, array['school_admin'::public.membership_role, 'principal'::public.membership_role, 'class_teacher'::public.membership_role])
  )
  with check (
    public.has_school_role(school_id, array['school_admin'::public.membership_role, 'principal'::public.membership_role, 'class_teacher'::public.membership_role])
  );

create policy report_approvals_select on public.report_approvals
  for select using (
    public.has_school_role(school_id, array['school_admin'::public.membership_role, 'principal'::public.membership_role, 'dean_of_discipline'::public.membership_role, 'class_teacher'::public.membership_role])
  );

create policy report_approvals_insert on public.report_approvals
  for insert with check (
    public.has_school_role(school_id, array['principal'::public.membership_role, 'dean_of_discipline'::public.membership_role, 'hod_moderator'::public.membership_role, 'class_teacher'::public.membership_role])
    and reviewer_id = auth.uid()
  );

create policy notifications_select on public.notifications
  for select using (recipient_id = auth.uid());
create policy notifications_update on public.notifications
  for update using (recipient_id = auth.uid());

create policy audit_logs_select on public.audit_logs
  for select using (
    school_id is not null
    and public.has_school_role(school_id, array['school_admin'::public.membership_role, 'principal'::public.membership_role, 'dean_of_discipline'::public.membership_role])
  );
-- No update/delete policies for audit_logs → immutable for clients

create policy background_jobs_select on public.background_jobs
  for select using (
    public.has_school_role(school_id, array['school_admin'::public.membership_role, 'principal'::public.membership_role, 'dean_of_discipline'::public.membership_role])
  );

-- Grant usage
grant usage on schema public to anon, authenticated;
grant select, insert, update, delete on all tables in schema public to authenticated;
grant select on all tables in schema public to anon;
