<p align="right">
  <a href="README-en.md"><img src="https://flagcdn.com/20x15/gb.png" width="20" height="15" alt="Cờ Anh"> English</a>
  &nbsp;|&nbsp;
  <a href="README.md"><img src="https://flagcdn.com/20x15/vn.png" width="20" height="15" alt="Cờ Việt Nam"> Tiếng Việt</a>
</p>

# hocphi-info-be

**Backend cho [hocphi.info](../hocphi-info) — thống kê học phí của 100+ trường Đại Học/Cao Đẳng tại Việt Nam.**

Thống kê học phí từng ngành–trường về `đồng/năm`, tách theo hệ đào tạo, và ước lượng
tổng chi phí cả khoá (4–6 năm) dựa trên % tăng học phí hàng năm.

- [hocphi-info-be](#hocphi-info-be)
  - [I. Cách hoạt động](#i-cách-hoạt-động)
  - [II. Vì sao thiết kế thế này](#ii-vì-sao-thiết-kế-thế-này)
  - [III. Công nghệ](#iii-công-nghệ)
  - [IV. Cấu trúc dự án](#iv-cấu-trúc-dự-án)
  - [V. Mô hình dữ liệu](#v-mô-hình-dữ-liệu)
  - [VI. Chạy thử](#vi-chạy-thử)
  - [VII. Lộ trình](#vii-lộ-trình)

## I. Cách hoạt động

Backend này **chỉ đọc**. Dữ liệu vào bằng một đường duy nhất: **AI-crawler** (repo
riêng) sinh ra file seed, người vận hành duyệt, rồi `scripts/seed.py` nạp vào DB.

```mermaid
flowchart TD
    subgraph CRAWL["AI-crawler — repo riêng, chạy theo đợt (không phải service)"]
        LIST["50 trường pilot<br/>+ domain chính thức"] --> DISC["1 · Tìm nguồn<br/>sitemap + site-search + heuristic URL<br/>→ ứng viên 'đề án tuyển sinh' / 'học phí'"]
        DISC --> FETCH["2 · Tải & chuẩn hoá về text<br/>HTML → trafilatura · PDF text → pypdf<br/>PDF scan → OCR/VLM"]
        FETCH --> SLICE["3 · Cắt lát KHÔNG dùng LLM<br/>regex + BM25 giữ lại đoạn có học phí<br/>~40k token → ~3k token/tài liệu"]
        SLICE --> LLM["4 · LLM trích xuất<br/>structured output theo schema Pydantic<br/>mỗi mức phí = 1 record + câu trích gốc + số trang"]
        LLM --> CHECK["5 · Kiểm tự động (code, không LLM)<br/>đơn vị · biên độ hợp lý · ngành có trong danh mục<br/>· chạy 2 lượt phải khớp"]
        CHECK --> REVIEW["6 · Người duyệt<br/>chỉ xem phần máy tự đánh dấu 'chưa chắc'"]
        REVIEW --> OUT["seeds/*.jsonl<br/>programs · tuition_records · sources"]
    end

    OUT -->|"pull request sang repo này"| SEED["scripts/seed.py<br/>(idempotent, chạy tay sau migrate)"]
    SEED --> DB[("PostgreSQL<br/>schools · majors · programs ·<br/>tuition_records · program_increase ·<br/>post_grad_requirements · sources")]

    subgraph API["FastAPI (chỉ đọc — không endpoint ghi)"]
        DB --> Q["query lọc / sắp xếp / tìm không dấu"]
        DB --> VIEW[("VIEW school_track_stats<br/>Min–Max / trung vị / số ngành<br/>theo (trường, hệ)")]
        Q --> DERIVE["Giá trị dẫn xuất tính lúc query<br/>(schema.md §5): amount_year_i =<br/>year_1 × (1+r)^(i-1), total_course,<br/>median_per_year, total_with_license"]
        VIEW --> DERIVE
        DERIVE --> RESP["Pydantic response models<br/>camelCase, enum = string —<br/>khớp hocphi-info-fe/src/types/domain.ts"]
    end

    RESP --> FE["hocphi-info-fe<br/>S1 theo ngành · S2 theo trường ·<br/>S3 chi tiết ngành–trường · F13 tìm nhanh"]

    subgraph FB["Phản hồi số liệu sai — không có API, chỉ là link"]
        USER["Người dùng cuối"] --> CH["mailto:example@mail.com<br/>· GitHub issue · Facebook"]
        CH --> OWNER["Người vận hành sửa seeds<br/>→ chạy lại scripts/seed.py"]
    end
```

Số gốc lưu trong DB (một mức học phí / chương trình / năm học); **mọi con số dẫn xuất**
— tổng cả khoá, trung vị/năm, khoảng Min–Max — tính lúc query, không lưu, để tránh dữ
liệu lệch nhau. Mọi con số truy được về một `sources` có ngày, kèm câu trích nguyên văn
và số trang trong tài liệu gốc.

## II. Vì sao thiết kế thế này

**1. Chuẩn hoá đơn vị ngay lúc nhập.** Mỗi trường công bố học phí một kiểu (đồng/tháng,
đồng/tín chỉ, đồng/năm) trong PDF đề án tuyển sinh — Việt Nam không có nguồn chuẩn hoá
bắt buộc kiểu [IPEDS](https://nces.ed.gov/ipeds/) (Mỹ) hay
[Discover Uni](https://discoveruni.gov.uk/) (Anh). Đây chính là lý do dự án phải tự
crawl: không có API nào để gọi. Backend quy tất cả về `amount_per_year`, giữ
`amount_original` + `unit_original` để đối chiếu khi tranh chấp số liệu.

**2. "Hệ đào tạo" là một thực thể riêng (`programs`), không phải cột.** Học phí hệ chất
lượng cao / tiên tiến / quốc tế gấp 3–5 lần hệ đại trà. Trộn chung khi tính trung vị sẽ
làm lệch số. `programs` = tổ hợp `trường × ngành × hệ × ngôn ngữ × cơ sở` — đơn vị nhỏ
nhất có đúng một mức học phí.

**3. Chỉ lưu số gốc, tính số dẫn xuất ở tầng API.** Tổng khoá, trung vị/năm, khoảng
Min–Max… đều là hàm của số gốc + % tăng. Lưu chúng = tự tạo ra cơ hội cho dữ liệu lệch
nhau. VIEW `school_track_stats` và công thức `schema.md` §5 làm việc này lúc query.

**4. Số công bố vs dự phóng phân biệt ở tầng dữ liệu.** Cột `is_projected` trên từng
`tuition_records` — "Năm 1" là số trường công bố, "Năm 2..N" là dự phóng theo % tăng.
UI luôn gắn nhãn, không suy đoán.

**5. Nhập liệu bằng AI-crawler + người duyệt, không admin CRUD / auth.** Phần khó nhất
của dự án là thu thập dữ liệu, không phải viết code — nên chỗ đó được tự động hoá, còn
API thì giữ nguyên hình dạng đơn giản nhất: **không có endpoint ghi nào cả**. Crawler
nằm ở repo riêng (deps nặng: trình duyệt headless, OCR, model), chạy theo đợt, và giao
tiếp với repo này bằng **file** (`seeds/*.jsonl`) qua pull request — không phải bằng
kết nối DB chung. Người vận hành là cổng cuối: máy đề xuất, người duyệt, `seed.py` nạp.

**6. Không nhận báo lỗi qua API.** Bảng `data_issue_reports` (F17) đã bị gỡ (2026-09-04).
Một endpoint công khai nhận ghi = phải lo spam, rate-limit, kiểm duyệt, quyền riêng tư —
đổi lại vài chục report mỗi năm. Ở quy mô MVP, `mailto:` + GitHub issue + comment
Facebook làm đúng việc đó với chi phí bằng 0, và người vận hành vẫn phải sửa `seeds/`
bằng tay trong cả hai trường hợp.

**7. ULID `text` làm khoá chính, sinh ở DB.** Sắp xếp được theo thời gian tạo, không lộ
số lượng bản ghi như serial, không cần round-trip lấy id trước khi tạo bản ghi liên quan.
`slug` vẫn là khoá công khai/URL cho `schools` và `majors`.

## III. Công nghệ

FastAPI · PostgreSQL 16 · SQLAlchemy 2.x (async, asyncpg) · Alembic · Pydantic v2 ·
structlog (structured logging — Tuần 5) · pytest · GitHub Actions CI · `uv` · Docker Compose

> **Caching:** roadmap gốc có Redis từ Tuần 5. Hoãn tới khi đo được một hot path thật
> sự cần — thêm một service + biến môi trường + dependency cho một API read-only chưa có
> traffic là chi phí không đổi lại gì. Xem `docs/brainstorms/2026-09-06-week5-observability-drop-redis-requirements.md`.

> **Lịch sử:** roadmap gốc (B4) định viết backend bằng **Go**. Đổi sang **Python/FastAPI**
> (2026-09-04) — đây là dự án học FastAPI, giống `hocphi-info-fe` là dự án học React.
> `docs/schema.md` v0.2 độc lập ngôn ngữ nên chuyển stack không mất thiết kế. Migration
> chuyển từ `golang-migrate` (SQL thuần) sang **Alembic** (`alembic/versions/`).

## IV. Cấu trúc dự án

Cấu trúc **phẳng, colocated** — không tầng repository/service/entity. API là đọc / lọc /
hiển thị, không phải business logic phức tạp; query nằm thẳng trong module feature.

```
app/
  main.py            # FastAPI(), CORS, exception handler, include routers
  config.py          # pydantic-settings BaseSettings (DATABASE_URL, CORS_ORIGINS, LOG_FORMAT)
  observability.py   # contextvar request_id + configure_logging() + RequestContextMiddleware
  db.py              # Base, async engine, async_sessionmaker, get_session() dependency
  enums.py           # Python StrEnum ↔ ENUM Postgres (school_category, program_track, …)
  models.py          # TẤT CẢ model SQLAlchemy trong 1 file (MVP 11 bảng)
  health.py          # GET /health (+ /docs Swagger tự sinh)
  majors.py          # GET /api/majors (S1) — join programs+schools+majors+tuition+increase
  schools.py         # GET /api/schools (S2) — đọc VIEW school_track_stats + increaseSummary
  search.py          # GET /api/search (F13) — không dấu, min 2 ký tự, max 8 kết quả
  schemas/common.py  # Pydantic response model dùng chung (CamelModel, khớp FE domain.ts)
alembic/
  env.py             # template async — trỏ app.db:Base.metadata
  versions/
    0001_initial_schema.py   # viết tay: gen_ulid(), ENUM, bảng, VIEW, seed bảng tra cứu
    0002_tuition_review_columns.py  # tuition_records +needs_review/+review_reason
scripts/
  seed.py                   # nạp seeds/*.sql + *.jsonl (đã duyệt) qua AsyncSession (idempotent)
  seed_majors_mapping.py    # quyết định tay: dòng nào trong *.jsonl được nạp, vào ngành nào
seeds/
  001_schools.sql    # 50 trường pilot (category/short_name còn phỏng đoán)
  002_majors.sql     # 16 ngành tối thiểu cho 25 dòng học phí thật đã duyệt (Tuần 2)
  # (Tuần 4+) *.jsonl — output đã duyệt của repo AI-crawler
tests/
  conftest.py        # fixture _schema (alembic upgrade), engine, db (SAVEPOINT rollback)
  test_migrations.py # upgrade head → downgrade base → upgrade head
  test_seed.py       # bảng tra cứu đủ dòng; seed nạp 50 trường; id = ULID 26 ký tự
  test_models.py     # selectinload chạy; vi phạm CHECK → IntegrityError
docs/
  schema.md          # thuyết minh thiết kế + ERD (v0.2) — nguồn cho app/models.py
  brainstorms/       # (git-ignore) requirements docs
  plans/             # (git-ignore) plan từng "tuần"
compose.yaml         # postgres + migrate (one-shot) + api
Dockerfile           # multi-stage uv, non-root
.github/workflows/ci.yml
```

Dự án chia thành các **"tuần"** có phần "Tuần N học được gì" + diagram đọc code, giống
`hocphi-info-fe` (nền Flutter/Go, học FastAPI vừa làm vừa học — xem `docs/plans/`).

## V. Mô hình dữ liệu

Chi tiết + thuyết minh: [`docs/schema.md`](docs/schema.md). Sơ đồ rút gọn:

```mermaid
erDiagram
    cities ||--o{ schools : "city_code"
    major_groups ||--o{ majors : "group_code"
    schools ||--o{ programs : "school_id"
    majors ||--o{ programs : "major_id"
    programs ||--o{ tuition_records : "program_id"
    programs ||--|| program_increase : "program_id 1-1"
    majors ||--o{ post_grad_requirements : "major_id"
    sources ||--o{ tuition_records : "source_id nullable"
    sources ||--o{ program_increase : "source_id"
    sources ||--o{ post_grad_requirements : "source_id"

    schools {
        text id PK "gen_ulid()"
        text slug UK "URL key"
        text name
        text city_code FK
        enum category "cong_lap | cong_lap_tu_chu | tu_thuc | tu_thuc_von_nuoc_ngoai"
    }
    majors {
        text id PK
        text slug UK
        text code "ma nganh cap IV, khong unique"
        text group_code FK
        smallint standard_years "3..7, mac dinh 4"
        boolean requires_practice_license
    }
    programs {
        text id PK
        text school_id FK
        text major_id FK
        enum track "dai_tra | chat_luong_cao | tien_tien | quoc_te"
        text language "vi | en | vi_en"
        text campus "NULL = co so chinh"
    }
    tuition_records {
        text id PK
        text program_id FK
        text academic_year "YYYY-YYYY"
        bigint amount_per_year "dong/nam, chuan hoa"
        enum unit_original "dong_nam | dong_thang | dong_tin_chi"
        boolean is_projected "false = cong bo, true = du phong"
        enum confidence "verified | published_unverified | estimated"
    }
    program_increase {
        text program_id PK "FK, 1-1"
        numeric annual_increase_pct
        enum increase_source "published_roadmap | default_estimate"
    }
    post_grad_requirements {
        text id PK
        text major_id FK
        text step_name "dao tao nghe, tap su, thi, phi hoi..."
        bigint cost_min
        bigint cost_max
    }
    sources {
        text id PK
        text url
        enum doc_type "de_an_tuyen_sinh | thong_bao_hoc_phi | quy_dinh_nghe | khac"
        date published_date
    }
```

Bảng phụ: `app_settings` (key/value — `current_intake_year`, `default_increase_pct`…).
VIEW `school_track_stats` (Min–Max / trung vị / số ngành theo
`(trường, hệ)`) phục vụ màn hình S2. `cities` / `major_groups` / `app_settings` là bảng
tra cứu tĩnh khoá bằng `code` / `key` — không ULID, không soft-delete. Các bảng nghiệp vụ
đều có `created_at` / `updated_at` / `deleted_at` (soft delete: query mặc định lọc
`WHERE deleted_at IS NULL`).

## VI. Chạy thử

```bash
cp .env.example .env               # điền DATABASE_URL nếu khác mặc định
uv sync                            # cài deps (uv tự tải Python 3.12)

docker compose up -d postgres      # Postgres 16 qua Docker (:5432)
uv run alembic upgrade head        # dựng schema + seed bảng tra cứu
uv run python -m scripts.seed      # nạp 50 trường pilot (idempotent)

uv run uvicorn app.main:app --reload   # API tại :8000
curl localhost:8000/health
# Swagger UI: http://localhost:8000/docs
```

Hoặc chạy tất cả qua Docker Compose (Postgres + migrate + API):

```bash
docker compose up        # migrate chạy xong mới tới api; API tại :8000
```

Kiểm thử:

```bash
uv run ruff check . && uv run mypy .
uv run pytest -q
```

Yêu cầu: PostgreSQL ≥ 14 (dùng `gen_random_bytes` của `pgcrypto` cho `gen_ulid()` +
generated columns). `pgcrypto` có sẵn trong image `postgres:16-alpine`.

## VII. Lộ trình

Roadmap sản phẩm 7 bước (xem [`../hocphi-info/y-tuong-hoc-phi-dai-hoc.md`](../hocphi-info/y-tuong-hoc-phi-dai-hoc.md) §8):

- [x] **B1** Chốt phạm vi MVP
- [x] **B2** Mockup UI (`*.dc.html`)
- [x] **B3** Thiết kế schema dữ liệu — [`docs/schema.md`](docs/schema.md) v0.3
- [ ] **B4** API backend (**FastAPI** — đang làm)
  - [x] **Tuần 1** — nền tảng: schema + Alembic + seed + Docker Compose + `GET /health` + `/docs`
  - [x] **Tuần 2** — nạp học phí thật (JSONL, 25/43 dòng đã duyệt) + endpoint đọc
        `GET /api/majors` (S1) / `GET /api/schools` (S2) / `GET /api/search` (F13) +
        Pydantic response models. Đảo thứ tự với Tuần 4 gốc — xem
        `docs/plans/2026-09-05-001-...-plan.md`. Path endpoint **tiếng Anh** (đã chốt,
        khác draft để ngỏ ban đầu); `tuition_records` +`needs_review`/`review_reason`
        (migration `0002`).
  - [x] **Tuần 3** — endpoint chi tiết ngành–trường `GET /api/schools/{school}/majors/{major}`
        (S3, gom mọi hệ đào tạo) + giá trị dẫn xuất `schema.md` §5: `total_course`,
        `total_with_license` (tính lũy tiến theo `app_settings.default_increase_pct`,
        chưa có `program_increase` thật). Không cần migration mới. Bỏ `total_course_range`
        khỏi tuần này (chưa có dữ liệu lộ trình tăng thật để khoảng có ý nghĩa) — xem
        `docs/brainstorms/2026-09-05-week3-program-detail-endpoint-requirements.md`.
  - [x] **Phụ** — `GET /api/coverage` (độ phủ dữ liệu cho trang `/du-lieu` của FE):
        tổng hợp + theo thành phố / loại trường / nhóm ngành + bảng từng trường, một
        CTE `pub` cho mọi phép đếm (các số cộng khớp nhau). Không cần migration mới —
        xem `../hocphi-info/docs/plans/2026-09-06-001-feat-coverage-endpoint-du-lieu-page-plan.md`.
  - [ ] **Tuần 4** — mở rộng hợp đồng dữ liệu AI-crawler cho các trường/dòng còn lại
        (17 dòng bẩn đã bỏ qua ở Tuần 2 — bundle nhiều ngành, chương trình liên kết
        quốc tế, tên hệ đào tạo giả làm ngành)
  - [x] **Tuần 5** — middleware request-id (`X-Request-ID` nhận lại / tự sinh, echo header,
        vào body lỗi 500) + structured logging (structlog, JSON ra stdout, mỗi request một
        `request_id`). Caching (Redis) và rate-limit **hoãn tới khi cần** — chưa có traffic;
        1 instance thì rate-limit in-process là đủ khi làm. Xem
        `docs/plans/2026-09-06-002-feat-week5-observability-drop-redis-plan.md` (kèm phần
        "Tuần 5 học được gì": ASGI middleware, `contextvars`, structlog).
- [ ] **B4b** **AI-crawler** — chạy bằng chính Claude Code (ngân sách API = 0), song song
      với B4. Skill `/crawl-truong` → `seeds/*.jsonl` cho 50 trường pilot;
      xem [`docs/ai-crawler.md`](docs/ai-crawler.md)
- [ ] **B5** Frontend React — [`hocphi-info-fe`](../hocphi-info-fe) (Tuần 1–3 xong, chạy mock, chờ API này)
- [ ] **B6** Deploy
- [ ] **B7** Người dùng thử
