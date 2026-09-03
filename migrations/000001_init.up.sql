-- 000001_init — Schema khởi tạo cho hocphi.info (MVP pilot 50 trường)
-- Postgres >= 14. Chạy bằng golang-migrate (file .up.sql / .down.sql).
--
-- Ngữ cảnh: yeu-cau-san-pham.md §8 (repo hocphi-info). Mọi học phí chuẩn hoá
-- về đồng/năm ngay lúc nhập; số dự phóng và số công bố phân biệt bằng cột riêng.

BEGIN;

-- ─────────────────────────────────────────────────────────────────────────────
-- Helper: tự cập nhật updated_at
-- ─────────────────────────────────────────────────────────────────────────────
CREATE FUNCTION set_updated_at() RETURNS trigger
  LANGUAGE plpgsql AS $$
BEGIN
  NEW.updated_at := now();
  RETURN NEW;
END;
$$;

-- ─────────────────────────────────────────────────────────────────────────────
-- Enum — các bộ giá trị ổn định (ít thay đổi). Thứ dễ mở rộng (thành phố,
-- nhóm ngành) để ở bảng tra cứu bên dưới.
-- ─────────────────────────────────────────────────────────────────────────────
CREATE TYPE school_category AS ENUM (
  'cong_lap',                -- công lập, còn bao cấp ngân sách
  'cong_lap_tu_chu',         -- công lập tự chủ tài chính
  'tu_thuc',                 -- tư thục trong nước
  'tu_thuc_von_nuoc_ngoai'   -- tư thục vốn nước ngoài (RMIT…) — outlier, hiển thị riêng
);

CREATE TYPE program_track AS ENUM (
  'dai_tra',
  'chat_luong_cao',
  'tien_tien',
  'quoc_te'                  -- gồm cả chương trình liên kết
);

CREATE TYPE tuition_unit AS ENUM (
  'dong_nam',
  'dong_thang',
  'dong_tin_chi'
);

CREATE TYPE data_confidence AS ENUM (
  'verified',                -- đã đối chiếu với nguồn gốc
  'published_unverified',    -- trường công bố, chưa đối chiếu
  'estimated'                -- ước lượng
);

CREATE TYPE increase_source_type AS ENUM (
  'published_roadmap',       -- trường công bố lộ trình trong đề án tuyển sinh
  'default_estimate'         -- mặc định (app_settings.default_increase_pct)
);

CREATE TYPE source_doc_type AS ENUM (
  'de_an_tuyen_sinh',
  'thong_bao_hoc_phi',
  'quy_dinh_nghe',
  'khac'
);

-- ─────────────────────────────────────────────────────────────────────────────
-- Bảng tra cứu (reference data) — seed ở migration 000002
-- ─────────────────────────────────────────────────────────────────────────────
CREATE TABLE cities (
  code       text PRIMARY KEY CHECK (code ~ '^[A-Z]{2,10}$'),
  name       text NOT NULL,
  sort_order smallint NOT NULL DEFAULT 0
);

CREATE TABLE major_groups (
  code       text PRIMARY KEY CHECK (code ~ '^[A-Za-z_]{2,20}$'),
  name       text NOT NULL,
  sort_order smallint NOT NULL DEFAULT 0
);

-- key/value cấu hình dùng chung: current_intake_year, default_increase_pct,
-- default_increase_band_pct, course_years_default…
CREATE TABLE app_settings (
  key   text PRIMARY KEY,
  value text NOT NULL,
  note  text
);

-- ─────────────────────────────────────────────────────────────────────────────
-- schools
-- ─────────────────────────────────────────────────────────────────────────────
CREATE TABLE schools (
  id              bigint GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
  slug            text NOT NULL UNIQUE CHECK (slug ~ '^[a-z0-9]+(-[a-z0-9]+)*$'),
  name            text NOT NULL,
  short_name      text,
  city_code       text NOT NULL REFERENCES cities(code),
  category        school_category NOT NULL,
  website         text,
  logo_url        text,
  established_year smallint CHECK (established_year IS NULL OR established_year BETWEEN 1900 AND 2100),
  created_at      timestamptz NOT NULL DEFAULT now(),
  updated_at      timestamptz NOT NULL DEFAULT now()
);
CREATE INDEX schools_city_idx     ON schools (city_code);
CREATE INDEX schools_category_idx ON schools (category);

-- ─────────────────────────────────────────────────────────────────────────────
-- majors — danh mục ngành dùng chung cho mọi trường (cặp "ngành – trường"
-- hình thành ở bảng programs). code = mã ngành cấp IV, KHÔNG unique vì nhiều
-- trường dùng chung một mã.
-- ─────────────────────────────────────────────────────────────────────────────
CREATE TABLE majors (
  id                        bigint GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
  slug                      text NOT NULL UNIQUE CHECK (slug ~ '^[a-z0-9]+(-[a-z0-9]+)*$'),
  name                      text NOT NULL,
  code                      text,
  group_code                text NOT NULL REFERENCES major_groups(code),
  requires_practice_license boolean NOT NULL DEFAULT false,
  practice_profession       text,
  created_at                timestamptz NOT NULL DEFAULT now(),
  updated_at                timestamptz NOT NULL DEFAULT now(),
  CHECK (NOT requires_practice_license OR practice_profession IS NOT NULL)
);
CREATE INDEX majors_group_idx    ON majors (group_code);
CREATE INDEX majors_code_idx     ON majors (code);
CREATE INDEX majors_practice_idx ON majors (requires_practice_license) WHERE requires_practice_license;

-- ─────────────────────────────────────────────────────────────────────────────
-- sources — mọi con số đều truy được về 1 nguồn có ngày
-- ─────────────────────────────────────────────────────────────────────────────
CREATE TABLE sources (
  id             bigint GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
  url            text NOT NULL,
  doc_type       source_doc_type NOT NULL DEFAULT 'khac',
  title          text,
  page_ref       text,                -- trang / mục trong tài liệu
  published_date date,
  fetched_at     timestamptz,
  checked_by     text,
  checked_at     timestamptz,
  created_at     timestamptz NOT NULL DEFAULT now(),
  updated_at     timestamptz NOT NULL DEFAULT now()
);

-- ─────────────────────────────────────────────────────────────────────────────
-- programs — đơn vị nhỏ nhất có MỘT mức học phí:
-- trường × ngành × hệ × ngôn ngữ giảng dạy × cơ sở
-- ─────────────────────────────────────────────────────────────────────────────
CREATE TABLE programs (
  id           bigint GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
  school_id    bigint NOT NULL REFERENCES schools(id) ON DELETE CASCADE,
  major_id     bigint NOT NULL REFERENCES majors(id)  ON DELETE RESTRICT,
  track        program_track NOT NULL,
  language     text NOT NULL DEFAULT 'vi' CHECK (language ~ '^[a-z]{2}(_[a-z]{2})*$'),
  campus       text,                -- NULL = cơ sở chính
  display_name text,                -- tên ngành theo cách trường gọi (nếu khác majors.name)
  note         text,
  is_active    boolean NOT NULL DEFAULT true,
  created_at   timestamptz NOT NULL DEFAULT now(),
  updated_at   timestamptz NOT NULL DEFAULT now()
);
-- một tổ hợp (trường, ngành, hệ, ngôn ngữ, cơ sở) chỉ tồn tại một lần
CREATE UNIQUE INDEX programs_unique_idx
  ON programs (school_id, major_id, track, language, COALESCE(campus, ''));
CREATE INDEX programs_school_idx ON programs (school_id);
CREATE INDEX programs_major_idx  ON programs (major_id);
CREATE INDEX programs_track_idx  ON programs (track);

-- ─────────────────────────────────────────────────────────────────────────────
-- tuition_records — một mức học phí cho một chương trình trong một năm học.
-- is_projected = true nghĩa là số dự phóng (Năm 2..N), luôn hiển thị nhãn.
-- ─────────────────────────────────────────────────────────────────────────────
CREATE TABLE tuition_records (
  id                       bigint GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
  program_id               bigint NOT NULL REFERENCES programs(id) ON DELETE CASCADE,
  academic_year            text NOT NULL
                             CHECK (academic_year ~ '^\d{4}-\d{4}$'
                                    AND substring(academic_year from 6 for 4)::int
                                      = substring(academic_year from 1 for 4)::int + 1),
  academic_year_start      smallint GENERATED ALWAYS AS
                             (substring(academic_year from 1 for 4)::smallint) STORED,
  amount_per_year          bigint NOT NULL CHECK (amount_per_year >= 0),   -- đồng/năm, đã chuẩn hoá
  unit_original            tuition_unit NOT NULL DEFAULT 'dong_nam',
  amount_original          bigint CHECK (amount_original IS NULL OR amount_original >= 0),
  credits_per_year_assumed smallint CHECK (credits_per_year_assumed IS NULL OR credits_per_year_assumed > 0),
  is_projected             boolean NOT NULL DEFAULT false,
  confidence               data_confidence NOT NULL DEFAULT 'published_unverified',
  source_id                bigint REFERENCES sources(id) ON DELETE SET NULL,
  verified_by              text,
  verified_at              timestamptz,
  note                     text,
  created_at               timestamptz NOT NULL DEFAULT now(),
  updated_at               timestamptz NOT NULL DEFAULT now(),
  UNIQUE (program_id, academic_year),
  -- quy đổi từ đồng/tín chỉ bắt buộc phải ghi số tín chỉ giả định
  CHECK (unit_original <> 'dong_tin_chi' OR credits_per_year_assumed IS NOT NULL),
  -- đã xác minh thì phải có nguồn + thời điểm đối chiếu
  CHECK (confidence <> 'verified' OR (source_id IS NOT NULL AND verified_at IS NOT NULL))
);
CREATE INDEX tuition_program_idx       ON tuition_records (program_id);
CREATE INDEX tuition_year_idx          ON tuition_records (academic_year_start);
CREATE INDEX tuition_published_idx     ON tuition_records (program_id, academic_year_start) WHERE NOT is_projected;

-- ─────────────────────────────────────────────────────────────────────────────
-- program_increase — % tăng học phí/năm cho một chương trình (1–1 với programs)
-- ─────────────────────────────────────────────────────────────────────────────
CREATE TABLE program_increase (
  program_id          bigint PRIMARY KEY REFERENCES programs(id) ON DELETE CASCADE,
  annual_increase_pct numeric(5,2) NOT NULL CHECK (annual_increase_pct >= 0 AND annual_increase_pct <= 100),
  increase_source     increase_source_type NOT NULL DEFAULT 'default_estimate',
  roadmap_years_known smallint CHECK (roadmap_years_known IS NULL OR roadmap_years_known >= 0),
  source_id           bigint REFERENCES sources(id) ON DELETE SET NULL,
  note                text,
  created_at          timestamptz NOT NULL DEFAULT now(),
  updated_at          timestamptz NOT NULL DEFAULT now(),
  CHECK (increase_source <> 'published_roadmap' OR source_id IS NOT NULL)
);

-- ─────────────────────────────────────────────────────────────────────────────
-- post_grad_requirements — chi phí hành nghề sau tốt nghiệp, gắn theo NGÀNH
-- (không thuộc học phí nhà trường, nguồn khác đề án tuyển sinh)
-- ─────────────────────────────────────────────────────────────────────────────
CREATE TABLE post_grad_requirements (
  id              bigint GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
  major_id        bigint NOT NULL REFERENCES majors(id) ON DELETE CASCADE,
  step_order      smallint NOT NULL CHECK (step_order > 0),
  step_name       text NOT NULL,
  provider        text,                -- đơn vị tổ chức (Học viện Tư pháp…)
  duration_months smallint CHECK (duration_months IS NULL OR duration_months >= 0),
  cost_min        bigint CHECK (cost_min IS NULL OR cost_min >= 0),
  cost_max        bigint CHECK (cost_max IS NULL OR cost_max >= 0),
  cost_note       text,
  confidence      data_confidence NOT NULL DEFAULT 'estimated',
  source_id       bigint REFERENCES sources(id) ON DELETE SET NULL,
  verified        boolean NOT NULL DEFAULT false,
  created_at      timestamptz NOT NULL DEFAULT now(),
  updated_at      timestamptz NOT NULL DEFAULT now(),
  UNIQUE (major_id, step_order),
  CHECK (cost_min IS NULL OR cost_max IS NULL OR cost_max >= cost_min)
);
CREATE INDEX pgr_major_idx ON post_grad_requirements (major_id);

-- ─────────────────────────────────────────────────────────────────────────────
-- data_issue_reports — F17 "Báo số liệu chưa đúng" (ưu tiên S). Không bắt buộc
-- thông tin định danh (§11 quyền riêng tư).
-- ─────────────────────────────────────────────────────────────────────────────
CREATE TABLE data_issue_reports (
  id               bigint GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
  target_kind      text NOT NULL CHECK (target_kind IN
                     ('program','tuition_record','post_grad_requirement','school','major','other')),
  target_id        bigint,
  target_desc      text,              -- mô tả tự do mục đang báo (trường/ngành/hệ/năm)
  suggested_value  text,
  source_url       text,
  note             text,
  reporter_contact text,              -- tuỳ chọn
  status           text NOT NULL DEFAULT 'new'
                     CHECK (status IN ('new','reviewing','resolved','rejected')),
  created_at       timestamptz NOT NULL DEFAULT now(),
  updated_at       timestamptz NOT NULL DEFAULT now()
);
CREATE INDEX data_issue_status_idx ON data_issue_reports (status);

-- ─────────────────────────────────────────────────────────────────────────────
-- Trigger updated_at
-- ─────────────────────────────────────────────────────────────────────────────
CREATE TRIGGER trg_schools_updated               BEFORE UPDATE ON schools               FOR EACH ROW EXECUTE FUNCTION set_updated_at();
CREATE TRIGGER trg_majors_updated                BEFORE UPDATE ON majors                FOR EACH ROW EXECUTE FUNCTION set_updated_at();
CREATE TRIGGER trg_sources_updated               BEFORE UPDATE ON sources               FOR EACH ROW EXECUTE FUNCTION set_updated_at();
CREATE TRIGGER trg_programs_updated              BEFORE UPDATE ON programs              FOR EACH ROW EXECUTE FUNCTION set_updated_at();
CREATE TRIGGER trg_tuition_records_updated       BEFORE UPDATE ON tuition_records       FOR EACH ROW EXECUTE FUNCTION set_updated_at();
CREATE TRIGGER trg_program_increase_updated      BEFORE UPDATE ON program_increase      FOR EACH ROW EXECUTE FUNCTION set_updated_at();
CREATE TRIGGER trg_post_grad_requirements_updated BEFORE UPDATE ON post_grad_requirements FOR EACH ROW EXECUTE FUNCTION set_updated_at();
CREATE TRIGGER trg_data_issue_reports_updated    BEFORE UPDATE ON data_issue_reports    FOR EACH ROW EXECUTE FUNCTION set_updated_at();

-- ─────────────────────────────────────────────────────────────────────────────
-- View school_track_stats — phục vụ S2 (tra cứu theo trường: khoảng Min–Max,
-- trung vị, số ngành) TÁCH THEO HỆ. Dựa trên số học phí công bố mới nhất
-- (không dự phóng) của mỗi chương trình. Không trộn hệ.
--
-- MVP: để VIEW thường cho luôn tươi. Nếu dữ liệu lớn lên → đổi thành
-- MATERIALIZED VIEW + REFRESH sau mỗi lần nhập liệu.
-- ─────────────────────────────────────────────────────────────────────────────
CREATE VIEW school_track_stats AS
WITH latest_published AS (
  SELECT DISTINCT ON (t.program_id)
         p.id          AS program_id,
         p.school_id,
         p.major_id,
         p.track,
         t.amount_per_year,
         t.academic_year_start
  FROM tuition_records t
  JOIN programs p ON p.id = t.program_id
  WHERE NOT t.is_projected
    AND p.is_active
  ORDER BY t.program_id, t.academic_year_start DESC
)
SELECT
  lp.school_id,
  lp.track,
  count(*)                                                          AS n_programs,
  min(lp.amount_per_year)                                           AS min_amount,
  (array_agg(lp.major_id ORDER BY lp.amount_per_year ASC,  lp.major_id))[1] AS min_major_id,
  percentile_cont(0.5) WITHIN GROUP (ORDER BY lp.amount_per_year)   AS median_amount,
  max(lp.amount_per_year)                                           AS max_amount,
  (array_agg(lp.major_id ORDER BY lp.amount_per_year DESC, lp.major_id))[1] AS max_major_id,
  min(pi.annual_increase_pct)                                       AS increase_pct_min,
  max(pi.annual_increase_pct)                                       AS increase_pct_max
FROM latest_published lp
LEFT JOIN program_increase pi ON pi.program_id = lp.program_id
GROUP BY lp.school_id, lp.track;

COMMIT;
