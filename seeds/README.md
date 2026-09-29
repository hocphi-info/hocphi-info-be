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

Đợt 2 (2026-09-06) — ưu tiên nguồn `*.edu.vn` chính thức:

| File | Trường | Số dòng |
|---|---|---|
| `ump.jsonl` | ĐH Y Dược TP.HCM | 18 |
| `tmu.jsonl` | ĐH Thương mại | 4 |
| `ou-tphcm.jsonl` | ĐH Mở TP.HCM | 7 |

**Đã crawl nhưng 0 dòng** (chỉ còn `crawler/work/<slug>/`, không có seed): `dh-luat-tphcm`,
`ptit` — quyết định học phí chính thức của cả hai trường chỉ công bố **đồng/tín chỉ**,
không kèm tổng số tín chỉ/năm; không có bảng đồng/năm chính thức nào ⇒ không quy đổi
được mà không bịa số (xem SKILL.md mục 2 & 7). Đơn giá tín chỉ gốc đã ghi trong
`review_reason`/báo cáo phiên để người duyệt hoàn tất nếu lấy được số tín chỉ/năm.

**Mọi dòng đều `needs_review: true`** — `major_slug` chưa map vào danh mục
`majors`, và nhiều dòng có `review_reason` nêu bất định cần người xác nhận trước
khi đưa vào `scripts/seed.py` (xem `.claude/skills/crawl-truong/SKILL.md` mục
"Bẫy đã gặp thật" / "Bẫy mới phát hiện" để hiểu từng loại cờ).

**Hạn dùng: ~1 năm.** Học phí đổi theo năm học và theo khoá tuyển sinh (xem SKILL.md
mục 12). Batch này lấy vào **tháng 9/2026** — nếu dự án còn duy trì, chạy lại skill
cho từng trường (`school_slug`) vào khoảng tháng 8-9/2027 trước khi tuyển sinh
đợt mới, đừng dùng lại số cũ.

## Phân loại ngành (taxonomy) — `004`, `005`, `006`

> ⚠️ **Dữ liệu này chưa đầy đủ và sẽ phải cập nhật.** Hiện hocphi.info mới có học phí của một
> phần nhỏ trong 50 trường pilot; mỗi lần crawl thêm trường sẽ xuất hiện thêm ngành, tên ngành
> lạ và cách gọi khác. Sau **mỗi đợt crawl**, rà lại `005` (ngành mới chưa có dòng nào?) và `006`
> (bộ alias mới chỉ phủ các ngành hiện có). Ngành mới trong `002_majors.sql` mà thiếu dòng ở `005`
> sẽ hiện là "Chưa phân loại" (không lỗi) — nhưng nên gán mã khi đã xác nhận được.

| File | Vai trò | Nguồn / cách cập nhật |
|---|---|---|
| `004_taxonomy.csv` | Danh mục thống kê ngành đào tạo **trình độ đại học** của Bộ GD&ĐT: `code,level,parent_code,name` (level 1 = lĩnh vực 3 số, 2 = nhóm ngành 5 số, 3 = ngành 7 số). 475 nút (23/75/377). | Thông tư 09/2022/TT-BGDĐT (Công báo 485+486), lấy ngày 2026-09-29 từ `congbao.chinhphu.vn`. Bỏ các nhóm "Khác" rỗng. **Bộ còn cập nhật danh mục ngoài Thông tư gốc** (ngành mới/thí điểm, đăng trên cổng thông tin của Bộ) — khi có, thêm dòng vào file này, không cần migration. |
| `005_major_taxonomy.csv` | Ánh xạ mỗi ngành (`major_slug` của `002_majors.sql`) → mã ngành 7 số (`taxonomy_code`). **Để trống = "Chưa phân loại"** và bắt buộc có `note` ghi lý do. | Người duyệt. 118 dòng khớp đúng tên danh mục, 2 dòng khác chính tả, **23 dòng chưa phân loại** (tên riêng của trường / ngành thí điểm / tên nhóm). Không đoán mã: chỉ điền khi xác nhận cùng ngành. Đây là *nguồn sự thật*: seed lại sẽ **ghi đè** `majors.code` theo file này. |
| `006_major_aliases.csv` | Tên gọi khác để tìm kiếm (`cntt`, `it`, `khmt`, `computer science`…): `major_slug,alias`. | Người curate. Khớp bằng nhau hoặc tiền tố ≥ 3 ký tự (không khớp chuỗi con). Cố ý **không** thêm alias nhập nhằng (vd `kt`, `httt` — "Hệ thống thông tin" của danh mục khác với "Hệ thống thông tin quản lý" đang có). Seed chỉ *thêm*; muốn xoá alias phải xoá tay trong DB. |

Nạp bằng `uv run python -m scripts.seed` (idempotent; thứ tự 001 → 002 → 004 → 005 → 006).
