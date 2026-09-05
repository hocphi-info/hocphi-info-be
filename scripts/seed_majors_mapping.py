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
}
