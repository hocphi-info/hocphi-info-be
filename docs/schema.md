# Thiết kế schema dữ liệu — hocphi.info (Bước 3)

> Phiên bản 0.1 — MVP pilot 50 trường TP.HCM & Hà Nội.
> Nguồn yêu cầu: [`yeu-cau-san-pham.md`](../../hocphi-info/yeu-cau-san-pham.md) §2, §8, §9 và
> [`y-tuong-hoc-phi-dai-hoc.md`](../../hocphi-info/y-tuong-hoc-phi-dai-hoc.md) §6.
> DDL: [`migrations/000001_init.up.sql`](../migrations/000001_init.up.sql).

## 1. Nguyên tắc thiết kế

1. **Chuẩn hoá đơn vị ngay lúc nhập** — mọi học phí quy về `đồng/năm` (`amount_per_year`).
   Giữ `amount_original` + `unit_original` để đối chiếu khi tranh chấp số liệu.
2. **Tách "hệ đào tạo" thành thực thể** (`programs`) — học phí các hệ chênh 3–5 lần,
   không bao giờ trộn hệ khi tính trung vị / Min–Max.
3. **Chỉ lưu số gốc, không lưu số dẫn xuất** — tổng cả khoá, trung vị/năm, khoảng
   min–max… tính lúc query hoặc build (xem §5). Tránh dữ liệu lệch nhau.
4. **Số công bố vs dự phóng phân biệt ở tầng dữ liệu** — cột `is_projected` trên
   từng `tuition_records`, không suy đoán ở UI.
5. **Mọi con số truy được về một nguồn có ngày** — `sources` + `confidence` +
   `verified_by/at` trên bản ghi.
6. **Enum cho bộ giá trị ổn định** (hệ đào tạo, độ tin cậy, loại tài liệu…);
   **bảng tra cứu** cho thứ sẽ mở rộng (thành phố, nhóm ngành).
7. **Khoá công khai là `slug`** (tiếng Việt không dấu, ổn định) cho `schools` và
   `majors` — phục vụ URL SEO ở §11 yêu cầu. `id` bigint chỉ dùng nội bộ / FK.

## 2. Sơ đồ quan hệ

```mermaid
erDiagram
  cities ||--o{ schools : "city_code"
  major_groups ||--o{ majors : "group_code"
  schools ||--o{ programs : "school_id"
  majors ||--o{ programs : "major_id"
  programs ||--o{ tuition_records : "program_id"
  programs ||--|| program_increase : "program_id (1-1)"
  majors ||--o{ post_grad_requirements : "major_id"
  sources ||--o{ tuition_records : "source_id (nullable)"
  sources ||--o{ program_increase : "source_id (nullable)"
  sources ||--o{ post_grad_requirements : "source_id (nullable)"

  schools {
    bigint id PK
    text   slug UK
    text   name
    text   short_name
    text   city_code FK
    enum   category "cong_lap | cong_lap_tu_chu | tu_thuc | tu_thuc_von_nuoc_ngoai"
    text   website
    text   logo_url
    smallint established_year
  }
  majors {
    bigint  id PK
    text    slug UK
    text    name
    text    code "mã ngành cấp IV, không unique"
    text    group_code FK
    boolean requires_practice_license
    text    practice_profession
  }
  programs {
    bigint  id PK
    bigint  school_id FK
    bigint  major_id FK
    enum    track "dai_tra | chat_luong_cao | tien_tien | quoc_te"
    text    language "vi | en | vi_en …"
    text    campus "NULL = cơ sở chính"
    text    display_name
    boolean is_active
  }
  tuition_records {
    bigint   id PK
    bigint   program_id FK
    text     academic_year "YYYY-YYYY"
    smallint academic_year_start "generated"
    bigint   amount_per_year "đồng/năm, chuẩn hoá"
    enum     unit_original "dong_nam | dong_thang | dong_tin_chi"
    bigint   amount_original
    smallint credits_per_year_assumed
    boolean  is_projected
    enum     confidence "verified | published_unverified | estimated"
    bigint   source_id FK
    text     verified_by
    timestamptz verified_at
  }
  program_increase {
    bigint  program_id PK_FK
    numeric annual_increase_pct
    enum    increase_source "published_roadmap | default_estimate"
    smallint roadmap_years_known
    bigint  source_id FK
  }
  post_grad_requirements {
    bigint   id PK
    bigint   major_id FK
    smallint step_order
    text     step_name
    text     provider
    smallint duration_months
    bigint   cost_min
    bigint   cost_max
    enum     confidence
    boolean  verified
    bigint   source_id FK
  }
  sources {
    bigint id PK
    text   url
    enum   doc_type "de_an_tuyen_sinh | thong_bao_hoc_phi | quy_dinh_nghe | khac"
    text   page_ref
    date   published_date
    timestamptz fetched_at
    text   checked_by
    timestamptz checked_at
  }
```

Bảng phụ không vẽ: `app_settings` (key/value), `data_issue_reports` (F17).

## 3. Từ điển bảng

### `cities`, `major_groups` — tra cứu
Seed cố định ở [`000002_seed_reference.up.sql`](../migrations/000002_seed_reference.up.sql):
`HCM`, `HN`; 6 nhóm ngành (`CNTT`, `KY_THUAT`, `KINH_TE`, `Y_DUOC`, `LUAT`, `LOGISTICS`).

### `app_settings` — cấu hình dẫn xuất
| key | mặc định | ý nghĩa |
|---|---|---|
| `current_intake_year` | `2026` | Năm nhập học của "Năm đầu" đang hiển thị |
| `course_years_default` | `4` | Số năm khoá cử nhân mặc định (máy tính ước lượng cho chọn 4/5) |
| `default_increase_pct` | `10` | % tăng/năm khi trường không công bố lộ trình |
| `default_increase_band_pct` | `3` | Biên ± cho khoảng min–max khi dùng ước lượng |

### `schools`
Hồ sơ trường. `category` gộp `type` + `autonomy_status` của brief thành **một** enum
4 giá trị — ánh xạ thẳng sang badge loại trường ở UI; `tu_thuc_von_nuoc_ngoai`
(RMIT) tách riêng để loại khỏi phép trung vị đại trà (§9 outlier).
`campus` **không** ở đây — cơ sở gắn theo `programs` vì học phí có thể khác nhau
giữa các cơ sở.

### `majors`
Danh mục ngành **dùng chung** mọi trường; cặp "ngành – trường" (F1) hình thành ở
`programs`. `code` = mã ngành cấp IV, **không** UNIQUE (nhiều trường trùng mã),
nullable (ngành mới như "Khoa học dữ liệu" có thể chưa có mã). `slug` là khoá thật.
`requires_practice_license = true` bắt buộc có `practice_profession` (CHECK) →
bật khối "Chi phí sau tốt nghiệp" ở S3.

### `programs` — đơn vị nhỏ nhất có một mức học phí
Tổ hợp `school × major × track × language × campus`. UNIQUE trên
`(school_id, major_id, track, language, COALESCE(campus,''))`.
`display_name` = tên trường tự gọi (khi khác `majors.name`). `is_active` để ẩn
ngành ngừng tuyển mà vẫn giữ lịch sử học phí.
Trang chi tiết S3 (`/truong/{school}/{major}`) gom **tất cả** `programs` cùng
`(school, major)` để dựng bảng "học phí theo năm & hệ".

### `tuition_records` — một mức học phí / chương trình / năm học
UNIQUE `(program_id, academic_year)`. `academic_year` dạng `YYYY-YYYY`, CHECK hai
năm liên tiếp; `academic_year_start` là cột **generated** để lọc / sắp xếp.
- `is_projected = false` → số trường công bố (Năm 1). `true` → dự phóng (Năm 2..N),
  UI luôn gắn nhãn "dự phóng".
- `unit_original = 'dong_tin_chi'` **bắt buộc** `credits_per_year_assumed` (CHECK) —
  hiển thị dòng "Giả định {x} tín chỉ/năm".
- `confidence = 'verified'` **bắt buộc** `source_id` + `verified_at` (CHECK).
- `source_id` nullable + `ON DELETE SET NULL` → trạng thái "chưa có nguồn" (§9).

### `program_increase` — % tăng học phí/năm (1–1 với `programs`)
`increase_source = 'published_roadmap'` bắt buộc `source_id` (CHECK);
`'default_estimate'` → dùng `app_settings.default_increase_pct`.
`roadmap_years_known` = số năm trường đã công bố sẵn (để thu hẹp khoảng min–max).
MVP dùng **một** `r` cho cả khoá (công thức §5); lộ trình %/năm khác nhau từng năm
là hạn chế đã biết (§6).

### `post_grad_requirements` — chi phí hành nghề, gắn theo **ngành**
Các bước sau tốt nghiệp (đào tạo nghề, tập sự, thi, phí hội…). UNIQUE
`(major_id, step_order)`. `confidence` mặc định `estimated`, `verified` mặc định
`false` — luôn kèm callout "nguồn ngoài đề án tuyển sinh" ở S3. Chi phí dạng
khoảng `cost_min..cost_max` (CHECK `cost_max >= cost_min`).

### `sources`
Tài liệu gốc: `url`, `doc_type`, `page_ref`, `published_date`, `fetched_at`,
`checked_by`, `checked_at`. Dùng chung cho `tuition_records`, `program_increase`,
`post_grad_requirements`.

### `data_issue_reports` — F17 "Báo số liệu chưa đúng" (ưu tiên S)
Không bắt buộc thông tin định danh (`reporter_contact` nullable) theo §11 quyền
riêng tư. `status`: `new → reviewing → resolved | rejected`.

## 4. View `school_track_stats` — phục vụ S2

Khoảng **Min–Max / trung vị / số ngành** cho mỗi `(school, track)`, dựa trên số
học phí **công bố mới nhất** (`is_projected = false`, năm học lớn nhất) của từng
chương trình. Không trộn hệ. Min/Max kèm `min_major_id` / `max_major_id` để UI
hiển thị tên ngành tương ứng (yêu cầu S2).

MVP để **VIEW thường** (luôn tươi, không cần vận hành). Khi dữ liệu lớn → chuyển
`MATERIALIZED VIEW` + `REFRESH` sau mỗi đợt nhập liệu.

"Cơ sở tính khoảng: gồm cả CLC–tiên tiến" (bộ lọc S2) = gộp nhiều `track` phía
API, không cần view riêng.

## 5. Giá trị dẫn xuất (tính ở API/build, không lưu)

Từ [`yeu-cau-san-pham.md`](../../hocphi-info/yeu-cau-san-pham.md) §8:

- `amount_year_i = amount_year_1 × (1 + r)^(i-1)`
  với `r` = `program_increase.annual_increase_pct / 100`
  (ưu tiên `published_roadmap`; nếu không có bản ghi → `default_increase_pct`).
- `total_course(program, years)` = Σ `amount_year_i`, `i = 1..years` (years ∈ {4,5}).
- `median_per_year_over_course` = `total_course / years`.
- `total_course_range` = tính lại với `r_low`, `r_high`:
  - `published_roadmap` → biên hẹp (theo `roadmap_years_known`);
  - `default_estimate` → `r ± default_increase_band_pct` điểm %.
- `total_with_license(major)` = `total_course` + Σ `post_grad_requirements.cost_*`
  (hiển thị dạng khoảng).

`amount_year_1` lấy từ `tuition_records` năm `current_intake_year` nếu có; nếu
chưa công bố thì lấy năm gần nhất rồi dự phóng tới `current_intake_year` (đánh dấu
ước lượng).

## 6. Hạn chế đã biết / câu hỏi mở

- **% tăng theo lộ trình từng năm**: MVP chỉ một `r`/chương trình. Nếu trường công
  bố bảng %/năm khác nhau → cần bảng `program_increase_schedule(program_id, year_index, pct)`
  ở v2.
- **`majors` dùng chung vs tên ngành lệch giữa các trường**: giải quyết tạm bằng
  `programs.display_name`. Nếu lệch nhiều → cân nhắc `school_major_aliases`.
- **Nhiều cơ sở, học phí khác nhau**: đã hỗ trợ qua `programs.campus`; UI S4 gom
  theo tab cơ sở.
- **`category` của 50 trường trong seed là phỏng đoán** — chốt lại ở bước 3.
- **Snapshot dữ liệu để chia sẻ link** (§11): chưa mô hình hoá; MVP mã hoá trạng
  thái bộ lọc trong URL, không cần bảng.

## 7. Cách chạy

```bash
# cần golang-migrate: brew install golang-migrate
export DATABASE_URL="postgres://user:pass@localhost:5432/hocphi?sslmode=disable"

migrate -path migrations -database "$DATABASE_URL" up      # tạo schema + seed reference
psql "$DATABASE_URL" -f seeds/001_schools.sql              # 50 trường (tuỳ chọn)

migrate -path migrations -database "$DATABASE_URL" down 1   # rollback 1 bước
```
