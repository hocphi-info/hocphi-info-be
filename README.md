# hocphi-info-be

Backend cho **hocphi.info** — tra cứu & so sánh học phí đại học Việt Nam
(MVP pilot 50 trường TP.HCM & Hà Nội).

- Ngữ cảnh sản phẩm & UI: repo [`hocphi-info`](../hocphi-info) (`yeu-cau-san-pham.md`, mockup `*.dc.html`).
- Tech stack: **Go + PostgreSQL**, REST API.

## Trạng thái

| Bước | Nội dung | Trạng thái |
|---|---|---|
| 1 | Chốt phạm vi MVP | ✅ |
| 2 | Mockup UI | ✅ |
| 3 | **Thiết kế schema dữ liệu** | 🚧 repo này — [`docs/schema.md`](docs/schema.md) |
| 4 | API backend (Go) | ⏳ |

## Cấu trúc

```
migrations/   # golang-migrate, SQL thuần (.up.sql / .down.sql)
  000001_init.*             schema + view school_track_stats
  000002_seed_reference.*   cities, major_groups, app_settings
seeds/
  001_schools.sql           50 trường pilot (category/short_name còn phỏng đoán)
docs/
  schema.md                 thuyết minh thiết kế + ERD
```

## Chạy migration

```bash
brew install golang-migrate
export DATABASE_URL="postgres://user:pass@localhost:5432/hocphi?sslmode=disable"

migrate -path migrations -database "$DATABASE_URL" up
psql "$DATABASE_URL" -f seeds/001_schools.sql   # tuỳ chọn
```

Yêu cầu PostgreSQL >= 14.
