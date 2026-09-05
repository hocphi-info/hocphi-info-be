# Seeds — batch dữ liệu

## `001_schools.sql`

50 trường pilot, nhập tay (xem header trong file). `category`/`short_name` là phỏng đoán.

## `003_school_logos.csv` — logo trường (nhập tay)

4 cột `slug,name,short_name,logo_url` (đúng thứ tự cột như bảng `schools`). Khoá
join là **`slug`**; `name`/`short_name` chỉ để người điền nhìn biết dòng nào,
script không đọc. `logo_url` để trống = bỏ qua dòng đó. Hợp lệ khi bắt đầu bằng
`http://`, `https://`, hoặc `/` (đường dẫn trong `hocphi-info-fe/public/`).

```
uv run python -m scripts.import_school_logos --dry-run   # xem tóm tắt
uv run python -m scripts.import_school_logos             # UPDATE schools.logo_url
```

Idempotent (UPDATE theo slug, chạy lại cho cùng kết quả). Slug lạ chỉ cảnh báo,
không làm script dừng. Cột `schools.logo_url` đã có sẵn từ migration `0001` —
**không** cần migration mới.

## `*.jsonl` — output AI-crawler, batch **2026-09**

Học phí thu thập bằng skill `.claude/skills/crawl-truong/` (Claude Code tự
WebSearch/curl/đọc PDF, không gọi LLM API trả tiền — xem `docs/ai-crawler.md`).

| File | Trường | Số dòng |
|---|---|---|
| `uit.jsonl` | ĐH Công nghệ Thông tin (ĐHQG-HCM) | 4 |
| `tdtu.jsonl` | ĐH Tôn Đức Thắng | 27 |
| `dh-van-lang.jsonl` | ĐH Văn Lang | 1 |
| `neu.jsonl` | ĐH Kinh tế Quốc dân | 7 |
| `ussh-tphcm.jsonl` | ĐH KHXH&NV TP.HCM (ĐHQG-HCM) | 4 |

**Mọi dòng đều `needs_review: true`** — `major_slug` chưa map vào danh mục
`majors`, và nhiều dòng có `review_reason` nêu bất định cần người xác nhận trước
khi đưa vào `scripts/seed.py` (xem `.claude/skills/crawl-truong/SKILL.md` mục
"Bẫy đã gặp thật" / "Bẫy mới phát hiện" để hiểu từng loại cờ).

**Hạn dùng: ~1 năm.** Học phí đổi theo năm học và theo khoá tuyển sinh (xem SKILL.md
mục 12). Batch này lấy vào **tháng 9/2026** — nếu dự án còn duy trì, chạy lại skill
cho từng trường (`school_slug`) vào khoảng tháng 8-9/2027 trước khi tuyển sinh
đợt mới, đừng dùng lại số cũ.
