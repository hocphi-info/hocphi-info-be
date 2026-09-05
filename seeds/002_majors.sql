-- seeds/002_majors — 17 ngành tối thiểu để nạp 26 dòng học phí thật đã duyệt
-- trong seeds/*.jsonl (xem docs/plans/2026-09-05-001-...-plan.md § Phụ lục).
--
-- `code` = NULL (mã ngành cấp IV chưa xác định cho pilot này — cho phép theo
-- schema §3). `group_code` gán theo nhóm GẦN NGHĨA NHẤT trong 6 nhóm cố định
-- đã seed ở migration 0001 (CNTT/KY_THUAT/KINH_TE/Y_DUOC/LUAT/LOGISTICS) — vài
-- ngành (ngôn ngữ, xã hội học, triết học, báo chí...) không có nhóm khớp thật
-- sự, đây là lựa chọn TẠM, owner nên xem lại nếu sau này thêm nhóm ngành mới.
-- `requires_practice_license` để false cho tất cả kể cả Dược học — chưa gán
-- post_grad_requirements (việc của Tuần 3), tránh vi phạm CHECK
-- ck_majors_practice_profession và bịa practice_profession chưa có nguồn.
--
-- Idempotent qua ON CONFLICT (slug) — partial unique index (xem 001_schools.sql).

INSERT INTO majors (slug, name, code, group_code, standard_years) VALUES
  ('ke-toan',                          'Kế toán',                                  NULL, 'KINH_TE',   4),
  ('thiet-ke-do-hoa',                  'Thiết kế đồ họa',                          NULL, 'KY_THUAT',  4),
  ('duoc-hoc',                         'Dược học',                                 NULL, 'Y_DUOC',    6),
  ('du-lich',                          'Du lịch',                                  NULL, 'KINH_TE',   4),
  ('bao-ho-lao-dong',                  'Bảo hộ lao động',                          NULL, 'KY_THUAT',  4),
  ('xa-hoi-hoc',                       'Xã hội học',                               NULL, 'LUAT',      4),
  ('ngon-ngu-anh',                     'Ngôn ngữ Anh',                             NULL, 'KINH_TE',   4),
  ('ngon-ngu-trung-quoc',              'Ngôn ngữ Trung Quốc',                      NULL, 'KINH_TE',   4),
  ('kinh-doanh-quoc-te',               'Kinh doanh quốc tế',                       NULL, 'KINH_TE',   4),
  ('ky-thuat-dieu-khien-tu-dong-hoa',  'Kỹ thuật điều khiển và tự động hóa',       NULL, 'KY_THUAT',  4),
  ('quan-ly-cong-va-chinh-sach',       'Quản lý công và chính sách',               NULL, 'LUAT',      4),
  ('ky-thuat-phan-mem',                'Kỹ thuật phần mềm',                        NULL, 'CNTT',      4),
  ('quan-tri-khach-san-quoc-te',       'Quản trị khách sạn quốc tế',               NULL, 'KINH_TE',   4),
  ('cong-nghe-thong-tin',              'Công nghệ thông tin',                      NULL, 'CNTT',      4),
  ('triet-hoc',                        'Triết học',                                NULL, 'LUAT',      4),
  ('bao-chi',                          'Báo chí',                                  NULL, 'LUAT',      4)
ON CONFLICT (slug) WHERE deleted_at IS NULL DO NOTHING;
