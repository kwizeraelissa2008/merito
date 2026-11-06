# Known limitations (Phase 3)

- Hosted Supabase (eu-west-1) has migrations `00001`–`00005` applied. No demo seed on the hosted project — create the first school via the onboarding wizard.
- Auth users are NOT seeded; create them via Supabase Auth (email confirmation is ON, so sign-ups need a confirmed email) and invite from `/app/settings/members`.
- The secret API key must be a full `sb_secret_…` value; a truncated key returns 401. Verify with `python scripts/probe_hosted.py`.
- Attendance and discipline UIs, report calculation/approval UI, PDF pipeline, deadline centre, PWA offline, and dashboards are Phases 4–7.
- **Offline editing is not supported**: autosave is debounced with retry, but there is no durable offline queue or background sync. The UI does not claim otherwise.
- Mark-sheet review is available to HoD/principal/admin; class-teacher moderation and report-level moderation land in Phase 5.
- Guardian portal surface is not built; `report_releases` gates only verified-guardian visibility. Student-user linking is Phase 5/6.
- No rate limiting on API mutations yet (planned Phase 8).
- Legal privacy/terms pages are placeholders pending counsel review.
- Audit rows are append-only to clients (no UPDATE/DELETE policy). Score changes are auto-audited by a database trigger.
