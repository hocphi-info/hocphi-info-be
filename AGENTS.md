# Project: hocphi-info-be

Backend API for [hocphi.info](../hocphi-info) — tuition lookup/comparison for Vietnamese
universities. Sibling repo `hocphi-info-fe` (Next.js) is the only consumer; product spec
lives at `../hocphi-info/y-tuong-hoc-phi-dai-hoc.md` (repo root, one level up).

Owner is learning FastAPI while building this (same setup as `hocphi-info-fe`, which is a
React-learning project). Prefer plain, idiomatic FastAPI/SQLAlchemy over clever abstractions.

> **History:** the original roadmap (B4) planned Go. Switched to **Python/FastAPI**
> (2026-09-04) — `docs/schema.md` is language-independent so the switch cost no design work.
> Don't be surprised by Go references in old commit messages/docs.

## Architecture

No named architecture (no repository/service/entity layers). The API is read / filter /
display, not complex business logic — query code lives directly in each feature's router
module. Two design decisions that shape everything else:

- **Store only source numbers, derive everything else at query time.** Total course cost,
  median/year, Min–Max range are all functions of the stored per-year amount + the annual
  increase %. Don't add columns or cache tables for these — compute them in the response
  layer (see `docs/schema.md` §5) so there's never a second copy that can drift.
- **"Track" (hệ đào tạo) is its own entity (`programs`), not a column.** Mixing
  chất lượng cao / tiên tiến / quốc tế into one average badly skews tuition numbers.
  `programs` = `school × major × track × language × campus`, the smallest unit with exactly
  one tuition figure.

## Folder structure

```
app/
  main.py            # FastAPI(), CORS, exception handlers, include routers
  config.py          # pydantic-settings BaseSettings (DATABASE_URL, REDIS_URL, CORS_ORIGINS)
  db.py              # Base, async engine, async_sessionmaker, get_session() dependency
  enums.py           # Python StrEnum <-> Postgres ENUM (school_category, program_track, …)
  models.py          # every SQLAlchemy model, one file (11 tables at MVP size)
  health.py          # GET /health (+ /docs Swagger, auto-generated)
  # feature routers land here as they're built: schools.py, majors.py, search.py, …
  # each file = router + its Pydantic request/response models, colocated
alembic/versions/     # 0001_initial_schema.py written by hand (gen_ulid(), ENUMs, VIEW, seed)
scripts/seed.py        # manual data load — reads seeds/*.sql via AsyncSession
seeds/                 # hand-curated *.sql (no admin API — see below)
tests/                 # conftest.py: alembic upgrade against an isolated test DB,
                        # SAVEPOINT-wrapped session per test (rolls back, never touches dev data)
docs/schema.md          # schema rationale + ERD — the source of truth `app/models.py` follows
compose.yaml            # postgres + redis + migrate (one-shot) + api
```

Work is split into **"tuần" (week) plans** with a "Tuần N học được gì" (what I learned)
section, matching `hocphi-info-fe`'s learning-log style — see `docs/plans/`.

## Conventions

- **No admin CRUD, no auth.** Data entry is manual: edit `seeds/*.sql`, run
  `uv run python -m scripts.seed` (idempotent). The only public write path is F17
  (report-bad-data) — validated by Pydantic, processed via `BackgroundTasks`, never blocking
  the response. Don't add an admin API or auth middleware without the owner asking first —
  it's a deliberate MVP scope cut, not an oversight.
- **Primary keys are ULIDs (`text`, `gen_ulid()` default in Postgres)**, except the small
  static lookup tables (`cities`, `major_groups`, `app_settings`), which are keyed by a plain
  `code`/`key` string — no ULID, no soft-delete on those.
- **Soft delete on business tables**: `created_at` / `updated_at` / `deleted_at`, default
  queries filter `WHERE deleted_at IS NULL`.
- **Response models are Pydantic, camelCase, enums as strings** — this has to match
  `hocphi-info-fe/src/types/domain.ts` field-for-field; check that file before renaming or
  reshaping a response.
- Tooling: `uv` for deps/venv, `ruff` (lint) + `mypy` (types, `disallow_untyped_defs`) +
  `pytest` (async, `asyncio_mode = "auto"`). Run `uv run ruff check . && uv run mypy . && uv run pytest -q`
  before committing.

## Git commit messages

Always in English, regardless of the conversation language. No AI-attribution lines
(no "Generated with Claude", no Co-Authored-By Claude) in commits or PR descriptions.
