# Cac lenh hay dung khi phat trien hocphi-info-be.
#
# Hai che do chay:
#   1. Lai (dev)   : Postgres qua Compose, API + migrate + seed chay tr. host bang `uv run`
#                    -> `make bootstrap` mot lan, sau do `make dev`.
#   2. Full Compose: tat ca trong container (postgres + migrate one-shot + api)
#                    -> `make up`.
#
# `make` hoac `make help` liet ke moi target.

# ── Bien co the ghi de: `make dev UV="uv run" COMPOSE="docker compose"` ──────────
UV            ?= uv run
COMPOSE       ?= docker compose
POSTGRES_USER ?= hocphi
POSTGRES_DB   ?= hocphi

.DEFAULT_GOAL := help

# ── Tro giup ───────────────────────────────────────────────────────────────────
.PHONY: help
help: ## Hien thi danh sach target
	@grep -E '^[a-zA-Z_-]+:.*?## .*$$' $(MAKEFILE_LIST) \
		| awk 'BEGIN {FS = ":.*?## "}; {printf "  \033[36m%-14s\033[0m %s\n", $$1, $$2}'

# ── Setup ──────────────────────────────────────────────────────────────────────
.PHONY: install bootstrap
install: ## Cai/cap nhat dependencies (uv sync, gom nhom dev)
	uv sync

bootstrap: install db-up db-wait migrate seed ## Lan dau sau khi clone: deps + Postgres + schema + seed

# ── Chay API (che do dev, tren host) ──────────────────────────────────────────
.PHONY: dev serve
dev: ## API co hot-reload tai :8000 (Postgres phai dang chay)
	$(UV) uvicorn app.main:app --reload

serve: ## API khong reload, lang nghe 0.0.0.0:8000 (giong container)
	$(UV) uvicorn app.main:app --host 0.0.0.0 --port 8000

# ── Migration (Alembic) ──────────────────────────────────────────────────────
.PHONY: migrate downgrade revision history
migrate: ## Nang schema len ban moi nhat (alembic upgrade head)
	$(UV) alembic upgrade head

downgrade: ## Ha 1 buoc migration (alembic downgrade -1)
	$(UV) alembic downgrade -1

revision: ## Sinh migration tu thay doi model: make revision m="them cot X"
	@test -n "$(m)" || { echo "Thieu tham so m=... (mo ta migration)"; exit 1; }
	$(UV) alembic revision --autogenerate -m "$(m)"

history: ## Xem lich su migration
	$(UV) alembic history --verbose

# ── Seed du lieu ─────────────────────────────────────────────────────────────
.PHONY: seed
seed: ## Nap seeds/*.sql|jsonl vao DB (idempotent, chay lai duoc)
	$(UV) python -m scripts.seed

# ── Postgres qua Compose (chi rieng service postgres) ─────────────────────────
.PHONY: db-up db-stop db-wait db-shell db-reset
db-up: ## Bat container Postgres (:5432, chay nen)
	$(COMPOSE) up -d postgres

db-stop: ## Dung container Postgres (giu nguyen du lieu)
	$(COMPOSE) stop postgres

db-wait: ## Cho Postgres san sang nhan ket noi
	@echo "Doi Postgres..."
	@until $(COMPOSE) exec -T postgres pg_isready -U $(POSTGRES_USER) -d $(POSTGRES_DB) >/dev/null 2>&1; do sleep 1; done
	@echo "Postgres san sang."

db-shell: ## Mo psql trong container Postgres
	$(COMPOSE) exec postgres psql -U $(POSTGRES_USER) -d $(POSTGRES_DB)

db-reset: ## Xoa SACH DB (drop volume) roi dung lai + migrate + seed
	$(COMPOSE) down -v
	$(MAKE) db-up db-wait migrate seed

# ── Full stack qua Compose (postgres + migrate + api) ────────────────────────
.PHONY: up up-d down build logs ps
up: ## Dung toan bo stack, bam log (migrate xong moi toi api; API :8000)
	$(COMPOSE) up --build

up-d: ## Nhu `up` nhung chay nen
	$(COMPOSE) up --build -d

down: ## Tat stack Compose (giu volume du lieu)
	$(COMPOSE) down

build: ## Build lai image API
	$(COMPOSE) build

logs: ## Theo doi log moi service
	$(COMPOSE) logs -f

ps: ## Trang thai cac container
	$(COMPOSE) ps

# ── Kiem tra chat luong (chay truoc khi commit — xem AGENTS.md) ───────────────
.PHONY: lint fmt typecheck test check
lint: ## ruff check
	$(UV) ruff check .

fmt: ## ruff format (sua tai cho)
	$(UV) ruff format .

typecheck: ## mypy
	$(UV) mypy .

test: ## pytest
	$(UV) pytest -q

check: lint typecheck test ## Chay ca lint + mypy + pytest

# ── Don dep ──────────────────────────────────────────────────────────────────
.PHONY: clean
clean: ## Xoa cache cong cu (.pytest_cache, .mypy_cache, .ruff_cache, __pycache__)
	rm -rf .pytest_cache .mypy_cache .ruff_cache
	find . -type d -name __pycache__ -prune -exec rm -rf {} +
