"""Quyet dinh tay: dong nao trong seeds/*.jsonl duoc nap, nap vao nganh nao.

Khong suy luan luc chay (khop chuoi major_name_raw de tim nganh) — de tranh
sai lech vi ky tu Unicode (gach ngang dai/ngan, dau cau) trong ten nganh goc.
Khoa tra cuu la SO DONG (1-indexed, dung thu tu file) — da doi chieu tay tung
dong voi docs/plans/2026-09-05-001-...-plan.md § Phu luc.

Gia tri trong dict con:
- str: 1 dong -> 1 nganh (nhom A: nganh ro rang; nhom C: 1 gia dung chung ca
  nhom nhieu nganh, chi nap cho nganh duoc NEU TEN).
- list[str]: 1 dong -> NHIEU nganh cung gia (fan-out). `scripts/seed.py` lap qua
  list tao N `programs` + N `tuition_records`. Dung khi truong ra 1 muc/HE cho
  hang chuc nganh (HCMUT he Chuong trinh tieu chuan: 1 dong -> 41 nganh).
- khong co trong dict: bo qua khi nap (vd uet.jsonl/ueb.jsonl toan ten he).

TDTU dong 28 (them 2026-09-06): Du lich (Chuyen nganh Huong dan du lich) o CO SO
CHINH TP.HCM, Nhom 1 = 31,26 tr/nam — bu vao cho dong 4 (cung nganh nhung o Phan
hieu Khanh Hoa, 20,5 tr). 2 dong = 2 `programs` khac campus. Ca 2 gan
`display_name` qua ROW_TO_DISPLAY_NAME ben duoi.

Bo qua (khong co trong dict nao):
- TDTU dong 16-27 (12 dong): chuong trinh lien ket quoc te/song bang — gia chi
  la giai doan 1, chua gom giai doan hoc o nuoc ngoai.
- NEU dong 1,2,3,6: khong phai ten nganh that (CLC/POHE/Tien tien) hoac dinh
  gia theo khoa nhap hoc (ESOM khoa 68).
- UIT dong 3,4: cung nganh/track/ngon ngu/co so voi dong 1 -> dung UNIQUE
  constraint (schema chua phan biet loai hinh tuyen sinh).
"""

from __future__ import annotations

# {ten_file_jsonl: {so_dong (1-indexed): major_slug | [major_slug, ...]}} — dong
# khong co trong dict con cua file do se bi bo qua khi nap.
#
# Gia tri la LIST = fan-out: 1 dong JSONL (1 muc hoc phi cong bo o MUC HE) ap
# cho NHIEU nganh cung mot gia. `scripts/seed.py` lap qua list, tao 1 `programs`
# + 1 `tuition_records` cho moi nganh (cung amount, cung source, khac major_id).
# Dung khi truong ra 1 muc/he cho hang chuc nganh (vd HCMUT he Chuong trinh tieu
# chuan). `ROW_TO_DISPLAY_NAME` BO QUA dong dang list (moi nganh giu ten
# `majors.name` cua no).
ROW_TO_MAJOR_SLUG: dict[str, dict[int, str | list[str]]] = {
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
        28: "du-lich",  # co so chinh TP.HCM, Nhom 1 — doi voi dong 4 (Khanh Hoa)
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
    # 2026-09-05 (batch 2) — ca 2 file deu la bang chinh thuc, day du ten
    # nganh cu the (dh-quoc-te-tphcm.jsonl: thong bao 25/TB-DHQT; hcmus.jsonl:
    # quyet dinh 3295/QD-KHTN). uel.jsonl KHONG map — 3 dong cua no la ten
    # chuong trinh theo ngon ngu giang day, khong phai ten nganh cu the.
    "dh-quoc-te-tphcm.jsonl": {
        1: "quan-tri-kinh-doanh",
        2: "marketing",
        3: "tai-chinh-ngan-hang",
        4: "ke-toan",
        5: "kinh-te",
        6: "ngon-ngu-anh",
        7: "cong-nghe-thong-tin",
        8: "khoa-hoc-du-lieu",
        9: "khoa-hoc-may-tinh",
        10: "thong-ke",
        11: "toan-ung-dung",
        12: "ky-thuat-he-thong-cong-nghiep",
        13: "logistics-va-quan-ly-chuoi-cung-ung",
        14: "cong-nghe-sinh-hoc",
        15: "hoa-hoc-hoa-sinh",
        16: "cong-nghe-thuc-pham",
        17: "ky-thuat-hoa-hoc",
        18: "ky-thuat-y-sinh",
        19: "quan-ly-xay-dung",
        20: "ky-thuat-xay-dung",
        21: "ky-thuat-dieu-khien-tu-dong-hoa",
        22: "ky-thuat-dien-tu-vien-thong",
        23: "ky-thuat-khong-gian",
    },
    "dh-khoa-hoc-tu-nhien-tphcm.jsonl": {
        1: "sinh-hoc",
        2: "cong-nghe-sinh-hoc",
        3: "vat-ly-hoc",
        4: "cong-nghe-vat-ly-dien-tu-va-tin-hoc",
        5: "hoa-hoc",
        6: "khoa-hoc-vat-lieu",
        7: "dia-chat-hoc",
        8: "kinh-te-dat-dai",
        9: "hai-duong-hoc",
        10: "khoa-hoc-moi-truong",
        11: "toan-hoc",
        12: "khoa-hoc-du-lieu",
        13: "toan-ung-dung",
        14: "toan-tin",
        15: "thong-ke",
        16: "tri-tue-nhan-tao",
        17: "nhom-nganh-cong-nghe-thong-tin",
        18: "cong-nghe-vat-lieu",
        19: "cong-nghe-ky-thuat-moi-truong",
        20: "ky-thuat-dien-tu-vien-thong",
        21: "ky-thuat-hat-nhan",
        22: "vat-ly-y-khoa",
        23: "ky-thuat-dia-chat",
        24: "quan-ly-tai-nguyen-va-moi-truong",
        25: "cong-nghe-ban-dan",
        26: "thiet-ke-vi-mach",
        27: "cong-nghe-giao-duc",
    },
    # 2026-09-06 — ftu.jsonl / hcmute.jsonl crawl o muc HE / KHOI NGANH, phan
    # lon dong la ten he ("Chuong trinh Tieu chuan/Tich hop/CLC/Tien tien") hoac
    # "Khoi nganh X" gop nhieu nganh -> KHONG map, bo qua. Chi map dong nao neu
    # dich danh 1 nganh; nhom nhieu nganh 1 gia thi chi lay nganh NEU TEN dau,
    # khong rai gia (cung quy tac nhom C: TDTU/USSH). 3/7 dong ftu + 1/11 dong
    # hcmute duoc nap.
    "ftu.jsonl": {
        # 1-3: ten he (Tieu chuan/Tich hop/CLC) — bo qua.
        4: "quan-tri-khach-san",  # nhom "Dinh huong NN quoc te" — nganh neu ten dau
        # 5: "cac nganh con lai" — bo qua.
        6: "kinh-te-doi-ngoai",  # nhom CT tien tien — bo qua QTKD, TC-NH
        7: "kinh-doanh-quoc-te",  # i-Hons Queensland — bo qua Phan tich du lieu KD
    },
    "hcmute.jsonl": {
        # 1,3-11: "Khoi nganh X" / chuong trinh lien ket — gop nhieu nganh, bo qua.
        2: "cong-nghe-truyen-thong",  # dong duy nhat dich danh 1 nganh
    },
    # 2026-09-06 (dot 2) — crawl 5 truong, uu tien nguon *.edu.vn chinh thuc.
    # - ump.jsonl: bang "Hoc phi du kien" trong de an tuyen sinh 1608/TTTS-DHYD
    #   (Hieu truong ky), moi dong 1 nganh Y-Duoc cu the, don vi dong/nam -> map
    #   het, TRU dong 7 ("Dieu duong chuyen nganh Gay me hoi suc") vi trung
    #   (school,major=dieu-duong,track,language,campus) voi dong 6 -> dung UNIQUE
    #   constraint cua `programs` (cung 48tr, khong mat thong tin).
    # - ou-tphcm.jsonl: cot "MUC HOC PHI BINH QUAN" cho CA NHOM nganh -> ap dung
    #   quy tac nhom C (TDTU/USSH): chi nap cho nganh NEU TEN DAU moi dong, khong
    #   rai gia cho cac nganh con lai. review_reason da ghi ro day la binh quan.
    # - tmu.jsonl: KHONG map dong nao — ca 4 dong deu la ten HE dao tao
    #   ("Cac chuong trinh dao tao chuan/IPOP/song bang quoc te/tien tien"),
    #   khong phai ten nganh (giong uet.jsonl / ueb.jsonl).
    "ump.jsonl": {
        1: "y-khoa",
        2: "y-hoc-du-phong",
        3: "y-hoc-co-truyen",
        4: "duoc-hoc",
        5: "hoa-duoc",
        6: "dieu-duong",
        # 7: "Dieu duong chuyen nganh Gay me hoi suc" — trung UNIQUE voi dong 6, bo qua.
        8: "ho-sinh",
        9: "dinh-duong",
        10: "rang-ham-mat",
        11: "ky-thuat-phuc-hinh-rang",
        12: "ky-thuat-xet-nghiem-y-hoc",
        13: "ky-thuat-hinh-anh-y-hoc",
        14: "ky-thuat-phuc-hoi-chuc-nang",
        15: "y-te-cong-cong",
        16: "cong-tac-xa-hoi",
        17: "cong-nghe-duoc-pham",
        18: "tam-ly-hoc",
    },
    "ou-tphcm.jsonl": {
        1: "cong-nghe-sinh-hoc",  # nhom: CNSH, CN thuc pham, Sinh hoc ung dung
        2: "cong-nghe-ky-thuat-cong-trinh-xay-dung",  # nhom: + QL xd, Kien truc
        3: "cong-nghe-thong-tin",  # nhom: CNTT, KHMT, KHDL, HTTTQL, TTNT, KTPM...
        4: "ke-toan",  # nhom: Ke toan, Kiem toan, TC-NH, QTKD, Marketing, KDQT...
        5: "kinh-te",  # nhom: Kinh te, QL cong, XHH, CTXH, Dong Nam A hoc, Tam ly hoc
        6: "ngon-ngu-nhat",  # nhom: NN Nhat, NN Trung, NN Anh, NN Han
        7: "tai-chinh-ngan-hang",  # he TIEN TIEN, nhom nganh dau tien neu ten
    },
    # 2026-09-10 — HCMUT. Nguon: thong bao muc thu hoc phi nam hoc 2026-2027 tren
    # hcmut.edu.vn (noi dung lay qua API /api/home/content/item, trang render JS).
    # Truong ra 1 muc/HE, khong theo nganh. Owner chot "phuong an C" (2026-09-10):
    #   - Dong 1 (he Chuong trinh tieu chuan): FAN-OUT ra ca 41 nganh dai hoc
    #     chinh quy (danh sach nganh lay tu hcmut.edu.vn/tuyen-sinh/mo-ta-nganh-
    #     dao-tao, BO khoi PFIEV vi khoa <=2018 khong con tuyen). 20 nganh da co
    #     slug tu truoc, 21 nganh them moi o seeds/002_majors.sql (2026-09-10).
    #   - Dong 2-8 (cac he tieng Anh / tien tien / Nhat / lien ket): chua co danh
    #     sach nganh tung he -> tam map 1-2 nganh NEU TEN (kieu nhom A/C). Bo sung
    #     sau khi crawl trang OISP.
    "dh-bach-khoa-tphcm.jsonl": {
        1: [
            "thiet-ke-vi-mach",
            "ky-thuat-dien-tu-vien-thong",
            "ky-thuat-dieu-khien-tu-dong-hoa",
            "ky-thuat-dien",
            "kinh-te-xay-dung",
            "ky-thuat-xay-dung-cong-trinh-giao-thong",
            "ky-thuat-trac-dia-ban-do",
            "ky-thuat-xay-dung",
            "ky-thuat-xay-dung-cong-trinh-thuy",
            "ky-thuat-xay-dung-cong-trinh-bien",
            "ky-thuat-co-so-ha-tang",
            "kien-truc",
            "cong-nghe-ky-thuat-vat-lieu-xay-dung",
            "ky-thuat-co-dien-tu",
            "ky-thuat-nhiet",
            "ky-thuat-det",
            "ky-thuat-co-khi",
            "cong-nghe-det-may",
            "bao-duong-cong-nghiep",
            "ky-thuat-hoa-hoc",
            "cong-nghe-thuc-pham",
            "cong-nghe-sinh-hoc",
            "ky-thuat-may-tinh",
            "khoa-hoc-may-tinh",
            "ky-thuat-vat-lieu",
            "khoa-hoc-du-lieu",
            "vat-ly-ky-thuat",
            "co-ky-thuat",
            "ky-thuat-tau-thuy",
            "cong-nghe-ky-thuat-o-to",
            "ky-thuat-hang-khong",
            "quan-tri-kinh-doanh",
            "logistics-va-quan-ly-chuoi-cung-ung",
            "ky-thuat-he-thong-cong-nghiep",
            "quan-ly-cong-nghiep",
            "dia-ky-thuat-xay-dung",
            "ky-thuat-dau-khi",
            "ky-thuat-dia-chat",
            "kinh-te-tai-nguyen-thien-nhien",
            "quan-ly-tai-nguyen-va-moi-truong",
            "ky-thuat-moi-truong",
        ],
        2: "khoa-hoc-may-tinh",  # CTTA tieng Anh — nganh dai dien (chua co ds)
        3: "khoa-hoc-may-tinh",  # CTTT tien tien — track khac dong 2 -> program rieng
        4: "khoa-hoc-may-tinh",  # CTQT chuyen tiep quoc te — track khac -> rieng
        5: ["khoa-hoc-du-lieu", "ky-thuat-hat-nhan"],  # CTTA nhom uu dai — neu ten
        6: "ky-thuat-dien-tu-vien-thong",  # CTNB chuyen tiep Nhat — nganh neu ten
        7: ["khoa-hoc-may-tinh", "co-ky-thuat"],  # CTHNB dinh huong Nhat — neu ten
        8: ["tri-tue-nhan-tao", "cong-nghe-thong-tin"],  # lien ket UTS — neu ten
    },
    "dh-thang-long.jsonl": {
        # 25 nganh, muc Nam 1/hoc ky x 2 ky (anh bang hoc phi tren thanglong.edu.vn).
        # 15, 16: chuong trinh rieng (7340101A / 7340301A) -> slug rieng, khong gop
        # vao quan-tri-kinh-doanh / ke-toan (dung UNIQUE program, gia khac).
        1: "thanh-nhac",
        2: "thiet-ke-do-hoa",
        3: "ngon-ngu-anh",
        4: "ngon-ngu-trung-quoc",
        5: "ngon-ngu-nhat",
        6: "ngon-ngu-han",
        7: "kinh-te-quoc-te",
        8: "viet-nam-hoc",
        9: "truyen-thong-da-phuong-tien",
        10: "quan-tri-kinh-doanh",
        11: "marketing",
        12: "thuong-mai-dien-tu",
        13: "tai-chinh-ngan-hang",
        14: "ke-toan",
        15: "quan-tri-kinh-doanh-chuan-nghe-nghiep-quoc-te",
        16: "ke-toan-acca",
        17: "luat-kinh-te",
        18: "khoa-hoc-may-tinh",
        19: "he-thong-thong-tin",
        20: "cong-nghe-thong-tin",
        21: "tri-tue-nhan-tao",
        22: "logistics-va-quan-ly-chuoi-cung-ung",
        23: "dieu-duong",
        24: "quan-tri-dich-vu-du-lich-va-lu-hanh",
        25: "quan-tri-khach-san",
    },
    # 2026-10-16 — DH Y khoa Pham Ngoc Thach, de an tuyen sinh 2026 trang 11.
    # Dong 1-4: muc rieng tung nganh. Dong 5 "Cac nganh cu nhan" (47 tr/nam):
    # FAN-OUT ra 10 nganh con lai trong danh sach 14 nganh truong dao tao
    # (owner doi chieu danh sach nganh, 2026-10-16).
    "dh-y-khoa-pham-ngoc-thach.jsonl": {
        1: "y-khoa",
        2: "rang-ham-mat",
        3: "duoc-hoc",
        4: "y-hoc-co-truyen",
        5: [
            "khuc-xa-nhan-khoa",
            "ky-thuat-xet-nghiem-y-hoc",
            "ky-thuat-hinh-anh-y-hoc",
            "ky-thuat-phuc-hoi-chuc-nang",
            "ky-thuat-gay-me-hoi-suc",
            "dieu-duong",
            "dinh-duong",
            "ho-sinh",
            "y-te-cong-cong",
            "tam-ly-hoc",
        ],
    },
    # 2026-10-16 — them 13 file (Tuan crawl batch 2). Chi map vao nganh DA CO
    # trong seeds/002_majors.sql; dong 'ap dung chung' khong liet ke nganh -> bo qua
    # (giu quy uoc cua uet/ueb). Cac file con lai chua co dong nao map duoc:
    # aof, buh, dh-gtvt-tphcm, dh-van-lang, haui, hlu, huce, rmit-vietnam, tmu,
    # ueb, uel, uet, utc — can danh sach nganh tung he truoc khi fan-out.
    # bav.jsonl bo qua: 1-4 (khoi nganh / CLC ap dung chung),
    # 7, 9 (lien ket khong neu nganh)
    "bav.jsonl": {
        5: "ke-toan",  # dinh huong Nhat Ban — display_name rieng
        6: [
            "tai-chinh-ngan-hang",
            "quan-tri-kinh-doanh",
            "marketing",
        ],  # UWE: Ngan hang & TC quoc te, QTKD quoc te, Marketing
        8: "logistics-va-quan-ly-chuoi-cung-ung",  # Genoa (QTKD trung dong 6)
    },
    # dh-fpt-ha-noi.jsonl bo qua: 6,7,9,12,13,26-28,31,34,35: chua co nganh;
    # 15,17,19: trung UNIQUE voi Ngon ngu X; 37: trung tri-tue-nhan-tao
    "dh-fpt-ha-noi.jsonl": {
        1: "cong-nghe-thong-tin",
        2: "ky-thuat-phan-mem",
        3: "tri-tue-nhan-tao",
        4: "khoa-hoc-du-lieu",
        5: "an-toan-thong-tin",
        8: "he-thong-thong-tin",
        10: "truyen-thong-da-phuong-tien",
        11: "quan-he-cong-chung",
        14: "ngon-ngu-anh",
        16: "ngon-ngu-han",
        18: "ngon-ngu-trung-quoc",
        20: "luat",
        21: "luat-kinh-te",
        22: "marketing",
        23: "kinh-doanh-quoc-te",
        24: "thuong-mai-dien-tu",
        25: "quan-tri-kinh-doanh",
        29: "quan-tri-khach-san",
        30: "quan-tri-dich-vu-du-lich-va-lu-hanh",
        32: "logistics-va-quan-ly-chuoi-cung-ung",
        33: "cong-nghe-tai-chinh",
        36: "tai-chinh-ngan-hang",
        38: "an-ninh-mang",
    },
    # dh-fpt-tphcm.jsonl bo qua: nhu dh-fpt-ha-noi.jsonl
    "dh-fpt-tphcm.jsonl": {
        1: "cong-nghe-thong-tin",
        2: "ky-thuat-phan-mem",
        3: "tri-tue-nhan-tao",
        4: "khoa-hoc-du-lieu",
        5: "an-toan-thong-tin",
        8: "he-thong-thong-tin",
        10: "truyen-thong-da-phuong-tien",
        11: "quan-he-cong-chung",
        14: "ngon-ngu-anh",
        16: "ngon-ngu-han",
        18: "ngon-ngu-trung-quoc",
        20: "luat",
        21: "luat-kinh-te",
        22: "marketing",
        23: "kinh-doanh-quoc-te",
        24: "thuong-mai-dien-tu",
        25: "quan-tri-kinh-doanh",
        29: "quan-tri-khach-san",
        30: "quan-tri-dich-vu-du-lich-va-lu-hanh",
        32: "logistics-va-quan-ly-chuoi-cung-ung",
        33: "cong-nghe-tai-chinh",
        36: "tai-chinh-ngan-hang",
        38: "an-ninh-mang",
    },
    # ftu2.jsonl bo qua: 6: Truyen thong Marketing tich hop — chua co nganh
    "ftu2.jsonl": {
        1: "kinh-te-doi-ngoai",
        2: "kinh-te-doi-ngoai",
        3: "logistics-va-quan-ly-chuoi-cung-ung",  # DHNNQT Logistics toan cau
        4: "quan-tri-kinh-doanh",
        5: "quan-tri-kinh-doanh",
        7: "tai-chinh-ngan-hang",
        8: "tai-chinh-ngan-hang",
        9: "ke-toan",  # nhom C: Ke toan - Kiem toan -> chi nap Ke toan
    },
    "hmu.jsonl": {
        1: "y-khoa",
        2: "y-hoc-co-truyen",
        3: "khuc-xa-nhan-khoa",
        4: "ky-thuat-xet-nghiem-y-hoc",
        5: "ky-thuat-phuc-hoi-chuc-nang",
        6: "dieu-duong",
        7: "ho-sinh",
        8: "ky-thuat-hinh-anh-y-hoc",
        9: "rang-ham-mat",
        10: "ky-thuat-phuc-hinh-rang",
        11: "y-khoa",
        12: "dieu-duong",
        13: "ky-thuat-xet-nghiem-y-hoc",
        14: "ky-thuat-phuc-hoi-chuc-nang",
        15: "ky-thuat-hinh-anh-y-hoc",
        16: "y-hoc-du-phong",
        17: "y-te-cong-cong",
        18: "dinh-duong",
        19: "tam-ly-hoc",
        20: "cong-tac-xa-hoi",
    },
    "hup.jsonl": {
        1: "duoc-hoc",
        2: "hoa-duoc",
        3: "cong-nghe-sinh-hoc",
        4: "hoa-hoc",
        5: "duoc-hoc",
    },
    # hus.jsonl bo qua: 3,8,9,11,15-19,22-24,26: chua co nganh dung ma
    # (vd 'KH may tinh va thong tin' != KHMT)
    "hus.jsonl": {
        1: "toan-hoc",
        2: "toan-tin",
        4: "khoa-hoc-du-lieu",
        5: "vat-ly-hoc",
        6: "khoa-hoc-vat-lieu",
        7: "cong-nghe-ban-dan",
        10: "hoa-hoc",
        12: "hoa-duoc",
        13: "sinh-hoc",
        14: "cong-nghe-sinh-hoc",
        20: "khoa-hoc-moi-truong",
        21: "cong-nghe-ky-thuat-moi-truong",
        25: "hai-duong-hoc",
        27: "dia-chat-hoc",
        28: "quan-ly-tai-nguyen-va-moi-truong",
    },
    # hust.jsonl bo qua: 3,4,11 (ap dung chung), 9 (PFIEV), 10 (IPE)
    "hust.jsonl": {
        1: "quan-tri-kinh-doanh",  # TROY-BA
        2: "khoa-hoc-may-tinh",  # TROY-IT
        5: "ke-toan",  # nhom C — bo qua KH tinh toan, Hoa my pham
        6: "khoa-hoc-du-lieu",  # Elitech KHDL & TTNT
        7: "logistics-va-quan-ly-chuoi-cung-ung",
        8: "cong-nghe-thong-tin",  # nhom C: CNTT Viet Nhat / Viet Phap
    },
    # ptit.jsonl bo qua: 1,2,4: ap dung chung
    "ptit.jsonl": {
        3: [
            "cong-nghe-thong-tin",
            "tri-tue-nhan-tao",
        ],  # CNTT (dinh huong ung dung), CNTT Viet-Nhat, TTNT — bo qua Game
    },
    # ueh.jsonl bo qua: con lai: he ap dung chung, khong neu nganh
    "ueh.jsonl": {
        7: "ke-toan-acca",  # ACCA/ICAEW nganh Ke toan/Kiem toan
    },
    # ufm.jsonl bo qua: 2,3,6,7: ap dung chung; 4: Kiem toan — chua co nganh
    "ufm.jsonl": {
        1: "ngon-ngu-anh",
        5: "cong-nghe-tai-chinh",
    },
    # ussh-hn.jsonl bo qua: nganh trong nhom chua co trong majors deu bi bo qua
    "ussh-hn.jsonl": {
        1: [
            "bao-chi",
            "tam-ly-hoc",
            "quan-tri-khach-san",
            "quan-he-cong-chung",
            "quan-tri-dich-vu-du-lich-va-lu-hanh",
        ],
        2: [
            "viet-nam-hoc",
            "xa-hoi-hoc",
        ],
        3: [
            "cong-tac-xa-hoi",
            "triet-hoc",
            "truyen-thong-da-phuong-tien",
        ],
    },
    # vnua.jsonl bo qua: 1-3,5: nhom nganh ap dung chung
    "vnua.jsonl": {
        4: "thu-y",
    },
}

# {ten_file_jsonl: {so_dong: display_name}} — ghi de `programs.display_name` khi
# ten trong tai lieu goc chi tiet hon ten `majors` dung chung (name drift, xem
# docs/schema.md §"majors dung chung"). Chi dat khi that su can — mac dinh
# `display_name` = NULL va UI hien `majors.name`. `scripts/seed.py` set khi tao
# program moi, va backfill khi program da ton tai nhung `display_name` con NULL.
ROW_TO_DISPLAY_NAME: dict[str, dict[int, str]] = {
    "tdtu.jsonl": {
        4: "Du lịch (Chuyên ngành Hướng dẫn du lịch)",  # Phan hieu Khanh Hoa
        28: "Du lịch (Chuyên ngành Hướng dẫn du lịch)",  # co so chinh TP.HCM
    },
    # 2026-10-16 — ten goc chi tiet hon ten nganh dung chung.
    "bav.jsonl": {5: "Kế toán định hướng Nhật Bản"},
    "dh-fpt-ha-noi.jsonl": {
        4: "Khoa học dữ liệu và ứng dụng",
        38: "An ninh mạng và An toàn số",
        32: "Logistics và quản lý chuỗi cung ứng toàn cầu",
    },
    "dh-fpt-tphcm.jsonl": {
        4: "Khoa học dữ liệu và ứng dụng",
        38: "An ninh mạng và An toàn số",
        32: "Logistics và quản lý chuỗi cung ứng toàn cầu",
    },
    "ftu2.jsonl": {
        3: "Logistics toàn cầu và đổi mới chuỗi cung ứng",
        9: "Kế toán - Kiểm toán",
    },
    "hus.jsonl": {7: "Công nghệ bán dẫn (thuộc ngành Khoa học vật liệu)"},
    "hust.jsonl": {
        1: "Quản trị kinh doanh (TROY-BA)",
        2: "Khoa học máy tính (TROY-IT)",
        6: "Khoa học Dữ liệu và Trí tuệ nhân tạo (Elitech)",
        7: "Logistics và Quản lý chuỗi cung ứng (Elitech)",
    },
    "hup.jsonl": {5: "Dược học (liên kết ĐH Sydney)"},
    "ueh.jsonl": {7: "Kế toán/Kiểm toán tích hợp ACCA và ICAEW"},
}
