-- SDMS Phase 2 — Grading bands, assessment categories, configuration versions
--
-- Adds school-configurable grading primitives that Phase 3+ relies on:
--   * assessment_categories     — named categories with default max/weight
--   * grading_bands             — percentage → letter grade / descriptor ranges
--   * report_layouts            — draft school report-card layouts (Phase 6 renders)
--
-- All ranges are SCHOOL DEFAULTS, not national rules. A grading policy (00001)
-- references the active band set and category set by version, so a published
-- report can always be traced back to the exact configuration used.

-- ---------------------------------------------------------------------------
-- assessment_categories
-- ---------------------------------------------------------------------------
create table public.assessment_categories (
  id uuid primary key default gen_random_uuid(),
  school_id uuid not null references public.schools (id) on delete cascade,
  name text not null,
  code text not null,
  default_maximum_marks numeric(8, 2) not null default 20 check (default_maximum_marks > 0),
  -- Weight as a fraction of 1 (e.g. 0.30). The calculation engine validates the
  -- category set sums to 1.0 when the school requires it.
  default_weight numeric(8, 4) not null default 0 check (default_weight >= 0 and default_weight <= 1),
  -- How an absence/exemption affects the denominator for this category.
  exclude_absent_from_denominator boolean not null default true,
  exclude_exempt_from_denominator boolean not null default true,
  is_optional boolean not null default false,
  ordering int not null default 0,
  active boolean not null default true,
  created_at timestamptz not null default timezone('utc', now()),
  updated_at timestamptz not null default timezone('utc', now()),
  constraint assessment_categories_code_unique unique (school_id, code)
);

create index assessment_categories_school_idx
  on public.assessment_categories (school_id, active, ordering);

create trigger assessment_categories_set_updated_at
before update on public.assessment_categories
for each row execute function public.set_updated_at();

alter table public.assessment_categories enable row level security;

create policy assessment_categories_select on public.assessment_categories
  for select using (public.is_school_member(school_id));
create policy assessment_categories_admin_write on public.assessment_categories
  for all using (public.is_school_admin(school_id))
  with check (public.is_school_admin(school_id));

-- ---------------------------------------------------------------------------
-- grading_bands
-- ---------------------------------------------------------------------------
create table public.grading_bands (
  id uuid primary key default gen_random_uuid(),
  school_id uuid not null references public.schools (id) on delete cascade,
  grading_policy_id uuid not null references public.grading_policies (id) on delete cascade,
  letter text not null,
  descriptor text not null default '',
  -- Inclusive lower bound; upper bound is the next band's min − epsilon, so the
  -- top band uses min_percentage only. Bounds are validated 0..100.
  min_percentage numeric(5, 2) not null check (min_percentage >= 0 and min_percentage <= 100),
  -- When true the band is the school's official "pass" mark (policy-configurable).
  is_pass boolean not null default true,
  comment_hint text not null default '',
  ordering int not null default 0,
  created_at timestamptz not null default timezone('utc', now()),
  constraint grading_bands_letter_unique unique (grading_policy_id, letter),
  constraint grading_bands_min_unique unique (grading_policy_id, min_percentage)
);

create index grading_bands_policy_idx
  on public.grading_bands (grading_policy_id, min_percentage desc);

alter table public.grading_bands enable row level security;

create policy grading_bands_select on public.grading_bands
  for select using (public.is_school_member(school_id));
create policy grading_bands_admin_write on public.grading_bands
  for all using (public.is_school_admin(school_id))
  with check (public.is_school_admin(school_id));

-- Resolve a percentage to a band. Returns null when no band matches (the caller
-- must render "unclassified" rather than guess a grade).
create or replace function public.resolve_grading_band(
  p_grading_policy_id uuid,
  p_percentage numeric
)
returns public.grading_bands
language sql
stable
security definer
set search_path = public
as $$
  select *
  from public.grading_bands b
  where b.grading_policy_id = p_grading_policy_id
    and b.min_percentage <= p_percentage
  order by b.min_percentage desc
  limit 1;
$$;

-- ---------------------------------------------------------------------------
-- report_layouts — draft configuration surface for the Phase 6 designer.
-- The rendered/published output still lives in report_templates (00001) and is
-- versioned; this table is the editable working copy with save-and-resume.
-- ---------------------------------------------------------------------------
create table public.report_layouts (
  id uuid primary key default gen_random_uuid(),
  school_id uuid not null references public.schools (id) on delete cascade,
  name text not null,
  -- Layout for which curriculum level / combination (null = all).
  level public.academic_level,
  combination_id uuid references public.combinations (id) on delete set null,
  configuration_json jsonb not null default '{}'::jsonb,
  is_default boolean not null default false,
  created_at timestamptz not null default timezone('utc', now()),
  updated_at timestamptz not null default timezone('utc', now()),
  constraint report_layouts_name_unique unique (school_id, name)
);

create trigger report_layouts_set_updated_at
before update on public.report_layouts
for each row execute function public.set_updated_at();

alter table public.report_layouts enable row level security;

create policy report_layouts_select on public.report_layouts
  for select using (public.is_school_member(school_id));
create policy report_layouts_admin_write on public.report_layouts
  for all using (public.is_school_admin(school_id))
  with check (public.is_school_admin(school_id));

-- ---------------------------------------------------------------------------
-- Onboarding state — makes the wizard resumable and auditable.
-- ---------------------------------------------------------------------------
create type public.onboarding_step_status as enum ('pending', 'complete', 'skipped');

create table public.school_onboarding (
  school_id uuid primary key references public.schools (id) on delete cascade,
  current_step text not null default 'identity',
  steps jsonb not null default '{}'::jsonb,
  completed_at timestamptz,
  last_saved_by uuid references public.profiles (id),
  created_at timestamptz not null default timezone('utc', now()),
  updated_at timestamptz not null default timezone('utc', now())
);

create trigger school_onboarding_set_updated_at
before update on public.school_onboarding
for each row execute function public.set_updated_at();

alter table public.school_onboarding enable row level security;

create policy school_onboarding_select on public.school_onboarding
  for select using (public.is_school_member(school_id));
create policy school_onboarding_admin_write on public.school_onboarding
  for all using (public.is_school_admin(school_id))
  with check (public.is_school_admin(school_id));

-- ---------------------------------------------------------------------------
-- Grants for new tables
-- ---------------------------------------------------------------------------
grant select, insert, update, delete on public.assessment_categories to authenticated;
grant select, insert, update, delete on public.grading_bands to authenticated;
grant select, insert, update, delete on public.report_layouts to authenticated;
grant select, insert, update, delete on public.school_onboarding to authenticated;
grant select, insert, update on public.user_invitations to authenticated;
grant select, insert, update, delete on public.guardian_student_links to authenticated;
grant select, insert, update on public.report_releases to authenticated;
grant select, insert on public.school_config_versions to authenticated;
