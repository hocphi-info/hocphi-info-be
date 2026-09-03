-- 000002_seed_reference (down)
-- Lưu ý: chỉ chạy được khi chưa có dữ liệu tham chiếu tới cities/major_groups
-- (tức chưa seed schools/majors). Rollback theo đúng thứ tự: down 000002 trước
-- khi đã down phần dữ liệu phụ thuộc, hoặc down thẳng 000001 (DROP TABLE).

BEGIN;

DELETE FROM app_settings
 WHERE key IN ('current_intake_year','course_years_default',
               'default_increase_pct','default_increase_band_pct');

DELETE FROM major_groups
 WHERE code IN ('CNTT','KY_THUAT','KINH_TE','Y_DUOC','LUAT','LOGISTICS');

DELETE FROM cities WHERE code IN ('HCM','HN');

COMMIT;
