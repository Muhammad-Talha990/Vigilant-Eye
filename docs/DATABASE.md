# Database reliability (Phase 22)

## Principle

Schema changes use **Alembic**. Production must **not** rely on `create_all()` at API startup.

Google authentication, administrator UX, and UFM business rules are unchanged by this phase.

## Architecture

| Concern | Mechanism |
|---------|-----------|
| Fresh schema | `alembic upgrade head` (baseline creates tables) |
| Existing DB adoption | `alembic upgrade head` (baseline `create_all` is additive; integrity migration adds FK/indexes) |
| Production startup | No `create_all` (`IS_PRODUCTION`) |
| Development bare uvicorn | Optional `ALLOW_CREATE_ALL_ON_STARTUP=1` (default in non-prod) |
| Demo seed | Only when `demo_seed_enabled()`; blocked in production |

## Production migration procedure

1. Take a backup (`scripts/backup_postgres.ps1` / `.sh`).
2. Deploy application code including `backend/alembic/`.
3. Run bootstrap / entrypoint (calls `alembic upgrade head`) **or** manually:

```bash
cd backend
alembic upgrade head
```

4. Confirm `/ready` shows `migrations_pending: false`.
5. Confirm Administrator → System shows current = head revision.

Never run `alembic downgrade` against institutional data casually. Baseline downgrade is a no-op by design.

## Legacy scripts

| Script | Classification |
|--------|----------------|
| `migrate_student_user_link.py` | **A — obsolete after Alembic** (columns already in models/baseline). Kept for reference; only runs if `LEGACY_ADDITIVE_MIGRATIONS=1` in non-prod. |
| `migrate_submission_features.py` | **A — obsolete after Alembic** (same). |

## Integrity hardening (revision `20260928_0002_integrity`)

| Change | Why | Delete strategy |
|--------|-----|-----------------|
| `evidence.detection_id` → `detections.id` FK | Close missing relationship | `ON DELETE SET NULL` (preserve evidence) |
| `uq_result_controls_case_id` | App already assumes one control per case | N/A |
| Indexes on notifications / audit / users / cases | List/filter/pagination queries | N/A |

Applied only after live integrity audit found **zero** conflicting rows.

## Foreign-key delete policy (existing)

Most FKs use PostgreSQL default **NO ACTION / RESTRICT** — institutional history (cases, evidence, reviews, audit) is preserved; parent rows cannot be deleted while children exist. Prefer account **deactivation** over user deletion.

## Transaction / notification / concurrency

- Request sessions rollback on exception (`get_db`).
- Case reviews + notifications + audit + optional result hold commit in **one** transaction.
- Email send never raises; email failure does **not** roll back DB actions.
- Case review loads the case with `SELECT … FOR UPDATE` to block concurrent invalid state transitions.

## Health

| Endpoint | Meaning |
|----------|---------|
| `GET /health` | Process up (no DB) |
| `GET /ready` | DB reachable + Alembic revision fields |
| `GET /admin/system-info` | Admin-only migration visibility |

## Backup & restore

- Method: `pg_dump -Fc` (custom format)
- Scripts: `scripts/backup_postgres.ps1`, `scripts/backup_postgres.sh`
- Retention suggestion: daily × 14, weekly × 8, encrypted off-host
- **Never** restore over the live volume without an explicit disaster plan
- Verify with a **separate** temporary database (see Phase 22 restore test)

## Connection pool (env)

| Variable | Default |
|----------|---------|
| `DB_POOL_SIZE` | 5 |
| `DB_MAX_OVERFLOW` | 10 |
| `DB_POOL_TIMEOUT` | 30 |
| `DB_POOL_RECYCLE` | 1800 |
