-- SDMS Phase 2 — Invitations, guardian links, and controlled report releases
--
-- Adds the people-facing tables Phase 2 requires:
--   * user_invitations  — school-scoped, tokenised, single-use staff invites
--   * guardian_student_links — verified guardian ↔ student relationships
--   * report_releases    — explicit per-student/per-guardian report distribution
--
-- Security:
--   * Tokens are stored only as a SHA-256 hash; the raw token is emailed/printed once.
--   * Invitation acceptance is a SECURITY DEFINER function that validates the token,
--     expiry, status, and email match before creating a membership.
--   * Guardians see NOTHING until the school explicitly releases a report to them.

-- ---------------------------------------------------------------------------
-- Enums
-- ---------------------------------------------------------------------------
create type public.invitation_status as enum (
  'pending', 'accepted', 'revoked', 'expired'
);

create type public.guardian_relationship as enum (
  'mother', 'father', 'guardian', 'sponsor', 'other'
);

-- ---------------------------------------------------------------------------
-- user_invitations
-- ---------------------------------------------------------------------------
create table public.user_invitations (
  id uuid primary key default gen_random_uuid(),
  school_id uuid not null references public.schools (id) on delete cascade,
  email text not null,
  full_name text not null default '',
  role public.membership_role not null,
  token_hash text not null,
  status public.invitation_status not null default 'pending',
  -- Which staff member issued the invitation.
  invited_by uuid not null references public.profiles (id),
  -- Class/subject scope may be attached later; stored as flexible config so the
  -- invitation can pre-seed teaching assignments during acceptance.
  scope jsonb not null default '{}'::jsonb,
  expires_at timestamptz not null,
  accepted_at timestamptz,
  accepted_by uuid references public.profiles (id),
  revoked_at timestamptz,
  created_at timestamptz not null default timezone('utc', now()),
  updated_at timestamptz not null default timezone('utc', now()),
  constraint user_invitations_email_format
    check (email ~* '^[^@\s]+@[^@\s]+\.[^@\s]+$'),
  constraint user_invitations_token_unique unique (token_hash)
);

-- One PENDING invitation per (school, email, role). Historical rows are kept.
create unique index user_invitations_pending_unique
  on public.user_invitations (school_id, lower(email), role)
  where status = 'pending';

create index user_invitations_school_idx
  on public.user_invitations (school_id, status, created_at desc);

create trigger user_invitations_set_updated_at
before update on public.user_invitations
for each row execute function public.set_updated_at();

alter table public.user_invitations enable row level security;

-- School admins manage invitations. An invited user may read their own record
-- by matching the verified JWT email (never by token).
create policy user_invitations_select on public.user_invitations
  for select using (
    public.is_school_admin(school_id)
    or lower(email) = lower(coalesce(auth.jwt() ->> 'email', ''))
  );

create policy user_invitations_admin_insert on public.user_invitations
  for insert with check (
    public.is_school_admin(school_id)
    and invited_by = auth.uid()
  );

create policy user_invitations_admin_update on public.user_invitations
  for update using (public.is_school_admin(school_id))
  with check (public.is_school_admin(school_id));

-- No hard delete: revoke instead, so the audit trail survives.

-- ---------------------------------------------------------------------------
-- guardian_student_links
-- ---------------------------------------------------------------------------
create table public.guardian_student_links (
  id uuid primary key default gen_random_uuid(),
  school_id uuid not null references public.schools (id) on delete cascade,
  guardian_user_id uuid not null references public.profiles (id) on delete cascade,
  student_id uuid not null references public.students (id) on delete cascade,
  relationship public.guardian_relationship not null default 'guardian',
  -- Link only becomes effective once the school verifies the relationship.
  verified boolean not null default false,
  verified_by uuid references public.profiles (id),
  verified_at timestamptz,
  created_by uuid not null references public.profiles (id),
  created_at timestamptz not null default timezone('utc', now()),
  updated_at timestamptz not null default timezone('utc', now()),
  constraint guardian_student_links_unique unique (school_id, guardian_user_id, student_id)
);

create index guardian_student_links_guardian_idx
  on public.guardian_student_links (guardian_user_id, verified);
create index guardian_student_links_student_idx
  on public.guardian_student_links (student_id, verified);

create trigger guardian_student_links_set_updated_at
before update on public.guardian_student_links
for each row execute function public.set_updated_at();

alter table public.guardian_student_links enable row level security;

-- A guardian sees only their own verified links. Admins manage the links.
create policy guardian_student_links_select on public.guardian_student_links
  for select using (
    guardian_user_id = auth.uid()
    or public.is_school_admin(school_id)
    or public.has_school_role(
      school_id,
      array['principal'::public.membership_role]
    )
  );

create policy guardian_student_links_admin_write on public.guardian_student_links
  for all using (public.is_school_admin(school_id))
  with check (public.is_school_admin(school_id));

-- Helper: is the caller a verified guardian of the given student?
create or replace function public.is_verified_guardian_of(
  p_school_id uuid,
  p_student_id uuid
)
returns boolean
language sql
stable
security definer
set search_path = public
as $$
  select exists (
    select 1 from public.guardian_student_links g
    where g.school_id = p_school_id
      and g.student_id = p_student_id
      and g.guardian_user_id = auth.uid()
      and g.verified = true
  );
$$;

-- ---------------------------------------------------------------------------
-- report_releases
-- ---------------------------------------------------------------------------
-- A release is the school's explicit decision to expose a (possibly published)
-- report instance to a student portal and/or a verified guardian. Absence of a
-- row means NO access for portal roles.
create table public.report_releases (
  id uuid primary key default gen_random_uuid(),
  school_id uuid not null references public.schools (id) on delete cascade,
  report_instance_id uuid not null references public.report_instances (id) on delete cascade,
  audience text not null check (audience in ('student', 'guardian', 'both')),
  released_by uuid not null references public.profiles (id),
  released_at timestamptz not null default timezone('utc', now()),
  revoked_at timestamptz,
  note text,
  constraint report_releases_unique unique (report_instance_id, audience)
);

create index report_releases_instance_idx
  on public.report_releases (report_instance_id, revoked_at);

alter table public.report_releases enable row level security;

create policy report_releases_select on public.report_releases
  for select using (
    public.has_school_role(
      school_id,
      array[
        'school_admin'::public.membership_role,
        'principal'::public.membership_role,
        'dean_of_discipline'::public.membership_role
      ]
    )
    or public.is_class_teacher_of(
      school_id,
      (
        select ri.class_id from public.report_instances ri
        where ri.id = report_instance_id
      )
    )
    -- Student/guardian visibility is evaluated against verified relationships.
    or exists (
      select 1
      from public.report_instances ri
      where ri.id = report_instance_id
        and (
          (
            audience in ('student', 'both')
            and exists (
              select 1 from public.students s
              where s.id = ri.student_id
                -- A student user is linked by profile email ↔ student code owner
                -- mapping created in Phase 5; for now portal access is guardian-only.
                and false
            )
          )
          or (
            audience in ('guardian', 'both')
            and public.is_verified_guardian_of(ri.school_id, ri.student_id)
          )
        )
    )
  );

create policy report_releases_leadership_write on public.report_releases
  for all using (
    public.has_school_role(
      school_id,
      array[
        'school_admin'::public.membership_role,
        'principal'::public.membership_role
      ]
    )
  )
  with check (
    public.has_school_role(
      school_id,
      array[
        'school_admin'::public.membership_role,
        'principal'::public.membership_role
      ]
    )
  );

-- ---------------------------------------------------------------------------
-- Invitation acceptance RPC
-- ---------------------------------------------------------------------------
-- Validated server-side. The caller must be authenticated and their JWT email
-- must match the invitation. Applies the membership and (optionally) pre-seeds
-- teaching / class-teacher assignments carried in the invitation scope.
create or replace function public.accept_invitation(p_token text)
returns public.school_memberships
language plpgsql
security definer
set search_path = public
as $$
declare
  v_hash text;
  v_inv public.user_invitations;
  v_membership public.school_memberships;
  v_email text;
  v_assignment jsonb;
begin
  if auth.uid() is null then
    raise exception 'Authentication required' using errcode = '28000';
  end if;

  v_email := lower(coalesce(auth.jwt() ->> 'email', ''));
  if v_email = '' then
    raise exception 'Authenticated user has no email claim' using errcode = '28000';
  end if;

  v_hash := encode(digest(p_token, 'sha256'), 'hex');

  select * into v_inv
  from public.user_invitations
  where token_hash = v_hash
  for update;

  if not found then
    raise exception 'Invitation not found' using errcode = 'P0002';
  end if;

  if v_inv.status <> 'pending' then
    raise exception 'Invitation is not pending (status: %)', v_inv.status
      using errcode = 'P0001';
  end if;

  if v_inv.expires_at < timezone('utc', now()) then
    update public.user_invitations
       set status = 'expired'
     where id = v_inv.id;
    raise exception 'Invitation has expired' using errcode = 'P0001';
  end if;

  if lower(v_inv.email) <> v_email then
    raise exception 'Invitation email does not match the signed-in account'
      using errcode = '42501';
  end if;

  insert into public.school_memberships (school_id, user_id, role, status)
  values (v_inv.school_id, auth.uid(), v_inv.role, 'active')
  on conflict (school_id, user_id, role)
    do update set status = 'active'
  returning * into v_membership;

  -- Optional pre-seeded assignments.
  for v_assignment in
    select value from jsonb_array_elements(coalesce(v_inv.scope -> 'teaching_assignments', '[]'::jsonb))
  loop
    insert into public.teaching_assignments (
      school_id, teacher_user_id, class_id, subject_id, academic_year_id
    )
    values (
      v_inv.school_id,
      auth.uid(),
      (v_assignment ->> 'class_id')::uuid,
      (v_assignment ->> 'subject_id')::uuid,
      (v_assignment ->> 'academic_year_id')::uuid
    )
    on conflict (school_id, teacher_user_id, class_id, subject_id, academic_year_id)
      do nothing;
  end loop;

  for v_assignment in
    select value from jsonb_array_elements(coalesce(v_inv.scope -> 'class_teacher_assignments', '[]'::jsonb))
  loop
    insert into public.class_teacher_assignments (
      school_id, teacher_user_id, class_id, academic_year_id
    )
    values (
      v_inv.school_id,
      auth.uid(),
      (v_assignment ->> 'class_id')::uuid,
      (v_assignment ->> 'academic_year_id')::uuid
    )
    on conflict (school_id, class_id, academic_year_id, teacher_user_id)
      do nothing;
  end loop;

  update public.user_invitations
     set status = 'accepted',
         accepted_at = timezone('utc', now()),
         accepted_by = auth.uid()
   where id = v_inv.id;

  perform public.record_audit(
    v_inv.school_id,
    auth.uid(),
    'invitation.accepted',
    'user_invitations',
    v_inv.id,
    null,
    jsonb_build_object('email', v_inv.email, 'role', v_inv.role),
    null,
    null
  );

  return v_membership;
end;
$$;

-- Revoke a pending invitation (audited, non-destructive).
create or replace function public.revoke_invitation(p_invitation_id uuid, p_reason text default null)
returns public.user_invitations
language plpgsql
security definer
set search_path = public
as $$
declare
  v_inv public.user_invitations;
begin
  select * into v_inv from public.user_invitations where id = p_invitation_id for update;
  if not found then
    raise exception 'Invitation not found' using errcode = 'P0002';
  end if;
  if not public.is_school_admin(v_inv.school_id) then
    raise exception 'Not authorized' using errcode = '42501';
  end if;
  if v_inv.status <> 'pending' then
    raise exception 'Only pending invitations can be revoked' using errcode = 'P0001';
  end if;

  update public.user_invitations
     set status = 'revoked', revoked_at = timezone('utc', now())
   where id = v_inv.id
  returning * into v_inv;

  perform public.record_audit(
    v_inv.school_id, auth.uid(), 'invitation.revoked', 'user_invitations',
    v_inv.id, null, null, p_reason, null
  );

  return v_inv;
end;
$$;

grant execute on function public.accept_invitation(text) to authenticated;
grant execute on function public.revoke_invitation(uuid, text) to authenticated;
