# SDMS API

FastAPI service owning authoritative academic calculations, ranking, behavioral aggregation, report snapshot assembly, and school configuration for Phase 2.

## Run

```bash
python -m venv .venv
.venv\Scripts\activate   # Windows
pip install -r requirements.txt
uvicorn app.main:app --reload --port 8000
```

Requires `SUPABASE_URL`, `SUPABASE_ANON_KEY`, `SUPABASE_SERVICE_ROLE_KEY`, and
`SUPABASE_JWT_SECRET` in `.env` (copy from `.env.example`).

## Tests

```bash
pytest
```

## API surface

All routes are under `/v1`. Authenticated routes expect a Supabase access token
as a Bearer credential; membership and role are resolved against the database on
every request — client-supplied role claims are never trusted.

### Calculations (Milestone 1)

- `POST /v1/calculations/marks`
- `POST /v1/calculations/behavior`
- `POST /v1/calculations/attendance`
- `POST /v1/calculations/ranking`

### Configuration & membership (Phase 2)

- School identity & overview: `GET/PATCH /v1/schools/{id}`, `GET /v1/schools/{id}/overview`
- Calendar: `POST /v1/schools/{id}/academic-years`, `/terms`, `/reporting-periods`, `/calendar/default`
- Structure: `POST /v1/schools/{id}/curricula|grades|combinations|curriculum-subjects|classes|classes/streams`, `GET .../curriculum-structure`
- Subjects: `GET|POST /v1/schools/{id}/subjects`
- Grading: `GET|POST /v1/schools/{id}/grading-policies`, `.../assessment-categories`, `.../grading-bands`, `POST .../validate-weights`
- Members & invitations: `GET /v1/schools/{id}/members`, `POST /v1/schools/{id}/members/{id}/status`, `GET|POST /v1/schools/{id}/invitations`, `POST .../invitations/{id}/revoke`, `POST /v1/schools/invitations/accept`
- Assignments: `GET|POST /v1/schools/{id}/teaching-assignments`, `GET|POST /v1/schools/{id}/class-teacher-assignments`
- Imports: `POST /v1/schools/{id}/imports/{entity}/preview|commit` (entity: subjects | classes | students)
- Onboarding: `GET|PUT /v1/schools/{id}/onboarding`, `POST /v1/schools/{id}/onboarding/complete`

See the OpenAPI docs at [`http://localhost:8000/docs`](http://localhost:8000/docs) for exact request/response schemas.
