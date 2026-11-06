# Permission Matrix

Deny-by-default. Frontend hides unauthorized actions; **database RLS and FastAPI authorization are the security boundary**.

Legend: **F** = full · **R** = read · **W** = write/create · **S** = submit · **A** = approve · **—** = none · **\*** = only assigned scope

| Resource / Action | Platform Admin | School Admin | Principal | DoD | Discipline Staff | Subject Teacher | Class Teacher | HoD/Moderator | Student | Guardian |
|---|---|---|---|---|---|---|---|---|---|---|
| Platform tenants / health | F | — | — | — | — | — | — | — | — | — |
| School configuration | —† | F | R | R | — | — | — | — | — | — |
| Invite/manage staff | —† | F | R | R (discipline staff) | — | — | — | — | — | — |
| Academic calendar / periods | — | F | R | R | — | R | R | R | — | — |
| Curriculum / subjects / classes | — | F | R | R | — | R\* | R\* | R\* | — | — |
| Students / enrollments | — | F | R | R | R (limited) | R\* | R\* | R\* | self | linked |
| Teaching assignments | — | F | R | R | — | R (own) | R (own) | R | — | — |
| Create assessments | — | F | — | — | — | W\* | — | W\* | — | — |
| Enter/edit scores (open period) | — | —‡ | — | — | — | W\* | —§ | —§ | — | — |
| Submit mark sheets | — | — | — | R | — | S\* | R | A (if enabled) | — | — |
| Attendance | — | F | R | R | W (if authorized) | W\* (if authorized) | W\* | — | R (own released) | R (linked released) |
| Record behavior incidents | — | — | — | W/A | W | — | — | — | — | — |
| Approve behavior deductions | — | — | — | A | — | — | — | — | — | — |
| Erase approved incidents | — | — | — | —‖ | — | — | — | — | — | — |
| Class report review / comments | — | — | R | R | — | W subject comments\* | W\* | A (if enabled) | — | — |
| Principal approve / publish | — | — | A | R | — | — | — | — | — | — |
| Report PDF download | — | R | R | R | — | R\* | R\* | R\* | released | released |
| Analytics dashboards | — | school ops | school-wide | discipline + progress | limited | own | class\* | dept\* | — | — |
| Deadline center | — | F | R | F | R own | R own | R own | R own | — | — |
| Audit logs | —† | R school | R school | R discipline-related | — | — | — | — | — | — |
| AI comment assist | — | enable flag | — | — | — | use if enabled\* | use if enabled\* | — | — | — |
| School configuration (identity, calendar, curriculum, grading) | —† | F | R | R | — | — | — | — | — | — |
| Invitations (create / revoke) | —† | F | — | — | — | — | — | — | — | — |
| Accept invitation (own) | — | self-accept only | self-accept only | self-accept only | self-accept only | self-accept only | self-accept only | self-accept only | — | — |
| Member status change (suspend/deactivate) | — | F | — | — | — | — | — | — | — | — |
| Assignment changes (teaching / class teacher) | — | F | — | — | — | — | — | — | — | — |
| Report releases (student/guardian distribution) | — | F | F | — | — | — | R own class | — | released only | released only |
| Students (create/edit/transfer/withdraw) | — | F | R | R (limited) | R (limited) | R\* | R\* | R\* | — | — |
| Create/edit assessments | — | F | — | — | — | W\* | — | W\* | — | — |
| Enter/edit scores (open period) | — | —‡ | — | — | — | W\* | —§ | —§ | — | — |
| Submit mark sheet | — | — | — | — | — | S\* | — | S\* | — | — |
| Review/approve mark sheet | — | F | A | — | — | — | — | A | — | — |

† Time-limited, explicitly authorized, audited support access only—not automatic.  
‡ School admin may reopen periods with reason + audit; not routine mark entry.  
§ Class teacher / HoD cannot change other teachers’ marks unless also assigned or granted correction permission.  
‖ Approved incidents are never physically erased; corrections use audited workflows.

## Enforcement layers

1. **RLS** – membership + assignment predicates on every tenant table  
2. **FastAPI** – JWT membership checks before privileged service-role operations  
3. **Next.js** – route guards and UI affordances (non-authoritative)  
4. **Audit** – sensitive mutations write `audit_logs`; clients cannot UPDATE/DELETE audit rows

## Role multiplicity

One `profiles` account may hold multiple `school_memberships` roles in the same school (e.g. subject teacher + class teacher). Authorization is the union of granted scopes.
