"""Quyet dinh tay: dong nao trong seeds/*.jsonl duoc nap, nap vao nganh nao.

Khong suy luan luc chay (khop chuoi major_name_raw de tim nganh) — de tranh
sai lech vi ky tu Unicode (gach ngang dai/ngan, dau cau) trong ten nganh goc.
Khoa tra cuu la SO DONG (1-indexed, dung thu tu file) — da doi chieu tay tung
dong voi docs/plans/2026-09-05-001-...-plan.md § Phu luc.

25/43 dong duoc nap (18 dong con lai KHONG co trong dict nao ben duoi -> bo qua):
- Nhom A (10): 1 nganh ro rang.
- Nhom C (10: TDTU 6 + USSH 4): 1 gia dung chung ca nhom nhieu nganh, chi nap
  cho nganh duoc NEU TEN, khong suy ra gia cho cac nganh con lai trong nhom.
- NEU rieng (3): ten co hau to chuong trinh (vd "- EPMP") nhung la 1 nganh that.
- UIT (2/4): chi nap dong khong dung UNIQUE constraint cua `programs` (owner
  chot khong mo schema them cot phan biet loai hinh tuyen sinh).

Bo qua (khong co trong dict nao):
- TDTU dong 16-27 (12 dong): chuong trinh lien ket quoc te/song bang — gia chi
  la giai doan 1, chua gom giai doan hoc o nuoc ngoai.
- NEU dong 1,2,3,6: khong phai ten nganh that (CLC/POHE/Tien tien) hoac dinh
  gia theo khoa nhap hoc (ESOM khoa 68).
- UIT dong 3,4: cung nganh/track/ngon ngu/co so voi dong 1 -> dung UNIQUE
  constraint (schema chua phan biet loai hinh tuyen sinh).
"""

from __future__ import annotations

# {ten_file_jsonl: {so_dong (1-indexed): major_slug}} — dong khong co trong
# dict con cua file do se bi bo qua khi nap.
ROW_TO_MAJOR_SLUG: dict[str, dict[int, str]] = {
    "tdtu.jsonl": {
        1: "ke-toan",
        2: "thiet-ke-do-hoa",
        3: "duoc-hoc",
        4: "du-lich",
        5: "bao-ho-lao-dong",
        6: "ke-toan",  # nhom C — chi nap cho "Ke toan", bo qua 3 nganh con lai
        7: "xa-hoi-hoc",
        8: "kinh-doanh-quoc-te",  # nhom C — bo qua Marketing, QTKD (NH-KS)
        9: "ngon-ngu-anh",
        10: "ngon-ngu-trung-quoc",
        11: "thiet-ke-do-hoa",  # nhom C — bo qua 9 nganh con lai trong nhom
        12: "ke-toan",  # nhom C — bo qua Tai chinh ngan hang
        13: "ngon-ngu-anh",  # track/language khac dong 9 -> program rieng
        14: "kinh-doanh-quoc-te",  # nhom C — bo qua Marketing, QTKD (NH-KS)
        15: "ky-thuat-dieu-khien-tu-dong-hoa",  # nhom C — bo qua 4 nganh con lai
        # 16-27: chuong trinh lien ket quoc te/song bang — bo qua (xem docstring).
    },
    "neu.jsonl": {
        # 1,2,3: ten he dao tao (CLC/POHE/Tien tien), khong phai nganh that — bo qua.
        4: "quan-ly-cong-va-chinh-sach",
        5: "ky-thuat-phan-mem",
        # 6: dinh gia theo khoa nhap hoc (ESOM, khoa 68) — bo qua, khong mo schema.
        7: "quan-tri-khach-san-quoc-te",
    },
    "uit.jsonl": {
        1: "cong-nghe-thong-tin",
        2: "cong-nghe-thong-tin",  # track=tien_tien, language=en -> program khac dong 1
        # 3,4: trung (school,major,track,language,campus) voi dong 1 -> dung
        # UNIQUE constraint cua `programs` — bo qua (owner chot khong mo schema).
    },
    "dh-van-lang.jsonl": {
        1: "du-lich",
    },
    "ussh-tphcm.jsonl": {
        1: "triet-hoc",
        2: "xa-hoi-hoc",
        3: "bao-chi",
        4: "ngon-ngu-anh",
    },
    # 2026-09-05 (Tuần 4 batch) — mọi dòng của 3 file này có major_name_raw là
    # tên ngành cụ thể (không phải tên nhóm/hệ chung như uet.jsonl/ueb.jsonl,
    # 2 file đó KHÔNG có trong dict này nên bị bỏ qua toàn bộ khi seed).
    "hutech.jsonl": {
        1: "y-khoa",
        2: "duoc-hoc",
        3: "ky-thuat-xet-nghiem-y-hoc",
        4: "dieu-duong",
        5: "truyen-thong-da-phuong-tien",
        6: "thiet-ke-do-hoa",
        7: "cong-nghe-dien-anh-truyen-hinh",
        8: "thanh-nhac",
        9: "quan-tri-kinh-doanh",
        10: "quan-tri-va-phap-che-doanh-nghiep",
        11: "quan-tri-nhan-luc",
        12: "logistics-va-quan-ly-chuoi-cung-ung",
        13: "bat-dong-san",
        14: "kinh-doanh-quoc-te",
        15: "marketing",
        16: "digital-marketing",
        17: "marketing-va-truyen-thong-sang-tao",
        18: "ke-toan",
        19: "tai-chinh-ngan-hang",
        20: "thuong-mai-dien-tu",
        21: "kinh-doanh-thuong-mai",
        22: "cong-nghe-tai-chinh",
        23: "kinh-te-so",
        24: "quan-tri-nha-hang-va-dich-vu-an-uong",
        25: "quan-tri-khach-san",
        26: "quan-tri-dich-vu-du-lich-va-lu-hanh",
        27: "quan-tri-su-kien",
        28: "he-thong-thong-tin-quan-ly",
        29: "quan-ly-the-duc-the-thao",
        30: "luat",
        31: "luat-kinh-te",
        32: "ngon-ngu-anh",
        33: "ngon-ngu-nhat",
        34: "ngon-ngu-han",
        35: "ngon-ngu-trung-quoc",
        36: "tam-ly-hoc",
        37: "quan-he-cong-chung",
        38: "thiet-ke-thoi-trang",
        39: "thiet-ke-noi-that",
        40: "digital-art",
        41: "khoa-hoc-du-lieu",
        42: "cong-nghe-sinh-hoc",
        43: "cong-nghe-thuc-pham",
        44: "cong-nghe-tham-my",
        45: "kien-truc",
        46: "thu-y",
        47: "thu-y-cong-nghe-so",
        48: "cong-nghe-thong-tin",
        49: "an-toan-thong-tin",
        50: "an-ninh-mang",
        51: "khoa-hoc-may-tinh",
        52: "tri-tue-nhan-tao",
        53: "robot-tri-tue-nhan-tao",
        54: "cong-nghe-ky-thuat-o-to",
        55: "cong-nghe-o-to-dien",
        56: "cong-nghe-o-to-thong-minh",
        57: "ky-thuat-co-khi",
        58: "ky-thuat-co-dien-tu",
        59: "ky-thuat-dieu-khien-tu-dong-hoa",
        60: "ky-thuat-dien-tu-vien-thong",
        61: "ky-thuat-dien",
        62: "ky-thuat-may-tinh",
        63: "ky-thuat-xay-dung",
        64: "quan-ly-xay-dung",
    },
    "ulis.jsonl": {
        1: "ngon-ngu-anh",
        2: "ngon-ngu-phap",
        3: "ngon-ngu-duc",
        4: "ngon-ngu-trung-quoc",
        5: "ngon-ngu-nhat",  # nguon: "Ngon ngu Nhat Ban" — dung chung slug voi HUTECH
        6: "ngon-ngu-han",  # nguon: "Ngon ngu Han Quoc" — dung chung slug voi HUTECH
        7: "ngon-ngu-nga",
        8: "ngon-ngu-a-rap",
        9: "van-hoa-va-truyen-thong-xuyen-quoc-gia",
        10: "tieng-viet-va-van-hoa-viet-nam",
    },
    "dh-hoa-sen.jsonl": {
        1: "cong-nghe-thong-tin",
    },
}
