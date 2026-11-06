# Grading & Ranking Assumptions (Defaults)

**These are product defaults, not official Rwandan education regulations.**  
Schools override via `grading_policies` and related configuration. Never invent national rules.

## Academic calendar

| Setting | Default |
|---|---|
| Terms per year | 3 |
| Periodic reports per term | 3 |
| Periodic reports per year | 9 (+ optional end-of-term / final if configured) |

## Weighted marks

```
category_percentage = sum(valid scores) / sum(applicable maxima) × 100
overall_percentage  = Σ (category_percentage × category_weight)
```

- If weights are percentages, they must sum to 100% unless `normalize_weights = true`.
- Score statuses: `scored`, `missing`, `absent`, `exempt`, `pending`.
- Missing is never auto-converted to zero.
- Which statuses contribute to “valid/applicable” is policy-configurable; default: only `scored` contributes; `absent`/`exempt` exclude both score and maximum from the denominator when `exclude_non_scored_from_denominator = true` (default true for exempt; absent follows school flag, default exclude).
- Incomplete assessment sets → **provisional** results; cannot publish as final unless `allow_provisional_publication = false` (default).

## Rounding

| Setting | Default |
|---|---|
| Intermediate precision | Decimal, 6 places |
| Display / stored report % | 2 decimal places |
| Rounding mode | `ROUND_HALF_UP` |

## Behavioral marks

| Setting | Default |
|---|---|
| Base mark per reporting period | 40 |
| Formula | `max(0, 40 − Σ approved deductions)` |
| Excess deductions | Score displays 0; flag `deductions_exceed_base = true`; history retained |
| Unapproved incidents | Excluded from official scores and published reports |

Default incident types (configurable):

| Incident | Default deduction |
|---|---:|
| Shouting | 2 |
| Lateness | 2 |
| Changing place in class | 3 |
| Unsuitable shoes | 2 |
| Communication language violation | 2 |
| Other violation | school-defined |

Lateness as attendance does **not** auto-create a behavioral deduction unless an explicit school rule is enabled.

## Ranking

| Setting | Default |
|---|---|
| Tie policy | Shared / dense rank (equal % → same position; next rank skips) |
| Tie-breakers | None by name, code, or DB order |
| Incomplete records | Excluded from ranking unless `rank_provisional = true` (default false) |
| Populations | Class / combination / cohort as configured per template |

## Curriculum notes

- O-Level subject list and MS1/MS2 combinations are **seed defaults**.
- Legacy S6 combinations (MPC, MCB, PCB, PCM, etc.) are year/cohort-scoped.
- MPC involving Mathematics/Physics/Chemistry vs Computer Science must be confirmed by the school—do not silently merge with PCM.
- Computer Science ≠ ICT unless the school configures equivalence.
