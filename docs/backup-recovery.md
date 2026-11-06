# Database backup and recovery (draft)

Phase 8 expands operational runbooks. Baseline expectations:

## Hosted Supabase

- Enable daily backups in the Supabase project (Pro+) or export via `pg_dump` on a schedule.
- Store dumps encrypted, offline from the application runtime.
- Test restore into a staging project at least quarterly.

## Local / self-hosted

```bash
pg_dump "$DATABASE_URL" -Fc -f sdms-$(date +%Y%m%d).dump
pg_restore -d "$DATABASE_URL" --clean --if-exists sdms-YYYYMMDD.dump
```

## Application considerations

- Published `report_instances.snapshot_json` and Storage PDF objects are part of the recovery set.
- After restore, verify RLS still enabled and platform admin list is correct.
- Do not restore production student data into public demo environments.
