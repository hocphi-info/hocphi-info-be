-- 000002_seed_reference — dữ liệu tra cứu cố định (không phải dữ liệu học phí)

BEGIN;

INSERT INTO cities (code, name, sort_order) VALUES
  ('HCM', 'TP. Hồ Chí Minh', 1),
  ('HN',  'Hà Nội',          2);

-- 6 nhóm ngành ưu tiên cho pilot (yeu-cau-san-pham.md §1.3)
INSERT INTO major_groups (code, name, sort_order) VALUES
  ('CNTT',      'CNTT / KHMT / AI / Khoa học dữ liệu',                 1),
  ('KY_THUAT',  'Kỹ thuật (Điện–Điện tử, Cơ khí, Ô tô, Vi mạch)',      2),
  ('KINH_TE',   'Kinh tế – Tài chính – Ngân hàng – QTKD',              3),
  ('Y_DUOC',    'Y – Dược',                                            4),
  ('LUAT',      'Luật',                                                5),
  ('LOGISTICS', 'Logistics & Quản lý chuỗi cung ứng',                  6);

-- Cấu hình dùng chung cho phần dẫn xuất (tổng cả khoá, dự phóng)
INSERT INTO app_settings (key, value, note) VALUES
  ('current_intake_year',       '2026', 'Năm nhập học của "Năm đầu" đang hiển thị (2026–2027)'),
  ('course_years_default',      '4',    'Số năm khoá cử nhân mặc định'),
  ('default_increase_pct',      '10',   '% tăng học phí/năm khi trường không công bố lộ trình'),
  ('default_increase_band_pct', '3',    'Biên ± cho khoảng min–max khi dùng ước lượng mặc định');

COMMIT;
