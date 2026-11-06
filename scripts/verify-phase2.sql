-- Phase 2 verification: schema sanity + RLS spot checks.
-- Run against the local DB AFTER `supabase db reset`, e.g.:
--   psql postgresql://postgres:postgres@127.0.0.1:54322/postgres -v ON_ERROR_STOP=1 -f scripts/verify-phase2.sql
--
-- Every query below must either return rows or pass its DO-block assertion.
-- Failures raise exceptions and abort the script (ON_ERROR_STOP=1).

\echo '=== 1. Tables created by 00002-00004 exist ==='
select table_name from information_schema.tables
where table_schema = 'public'
  and table_name in (
    'school_config_versions', 'user_invitations', 'guardian_student_links',
    'report_releases', 'assessment_categories', 'grading_bands',
    'report_layouts', 'school_onboarding'
  )
order by table_name;

\echo '=== 2. RLS is enabled on every new table ==='
select relname, relrowsecurity
from pg_class
where relname in (
    'school_config_versions', 'user_invitations', 'guardian_student_links',
    'report_releases', 'assessment_categories', 'grading_bands',
    'report_layouts', 'school_onboarding'
  )
order by relname;

\echo '=== 3. Seed data present (both schools) ==='
select s.slug,
       (select count(*) from assessment_categories c where c.school_id = s.id) as categories,
       (select count(*) from grading_bands b where b.school_id = s.id) as bands,
       (select count(*) from school_onboarding o where o.school_id = s.id) as onboarding,
       (select count(*) from report_layouts l where l.school_id = s.id) as layouts
from schools s order by s.slug;

\echo '=== 4. Weights of seeded categories sum to 1.0 ==='
select school_id, sum(default_weight) as total
from assessment_categories
group by school_id;

\echo '=== 5. Grading band resolution works for boundary values ==='
select (b).letter as band, (b).descriptor
from (values (0.00), (49.99), (50.00), (69.99), (80.00), (100.00)) as v(p),
     lateral (select public.resolve_grading_band('14141414-1414-1414-1414-141414141401'::uuid, v.p)) as t(b)
order by 1;

\echo '=== 6. Onboarding state for both schools ==='
select school_id, current_step, completed_at is not null as complete
from school_onboarding order by school_id;

\echo '=== 7. Invitation token hashing: raw token must never be stored ==='
do $$
declare v_count int;
begin
  select count(*) into v_count
  from user_invitations
  where token_hash !~ '^[0-9a-f]{64}$';
  if v_count > 0 then
    raise exception 'Found % invitation row(s) whose token_hash is not a SHA-256 hex string', v_count;
  end if;
end $$;

\echo '=== 8. No-policy tables deny by default (guided assertion) ==='
-- audit_logs must have NO update/delete policies.
do $$
declare v_viol int;
begin
  select count(*) into v_viol
  from pg_policies
  where schemaname = 'public'
    and tablename = 'audit_logs'
    and cmd in ('UPDATE', 'DELETE');
  if v_viol > 0 then
    raise exception 'audit_logs unexpectedly has % mutating policies', v_viol;
  end if;
end $$;

\echo '=== 9. Manual RLS checks to run as a test user (documented) ==='
\echo '-- Create a test user in Supabase Auth, add NO membership, then as that user:'
\echo '--   select * from students;                 -- expects 0 rows'
\echo '--   insert into subjects(...)               -- expects RLS violation'
\echo '--   select * from user_invitations;         -- expects only own-email rows'
\echo '--   select * from report_instances;         -- expects 0 rows'
\echo '-- Then grant subject_teacher membership of SCHOOL 1 and confirm:'
\echo '--   select * from students;                 -- expects only SCHOOL 1 students they can view (assigned class)'
\echo '--   select * from schools;                  -- expects only their school, never school 2'
\echo 'Phase 2 verification script complete.'
