---
name: crawl-truong
description: Thu thap hoc phi cua MOT truong dai hoc VN tu tai lieu cong khai, xuat ra seeds/<slug>.jsonl. Dung khi can bo sung du lieu hoc phi cho hocphi.info — vi du "crawl UIT", "lay hoc phi Bach Khoa", "/crawl-truong tdtu". Chay het 7 buoc: tim nguon, tai ve, cat lat, trich xuat, kiem tra, danh dau cho duyet, xuat JSONL.
---

# Crawl hoc phi 1 truong

Doi so: `<slug>` — khop `schools.slug` trong `seeds/001_schools.sql` (vi du `uit`,
`dh-bach-khoa-tphcm`, `tdtu`). Khong co doi so thi hoi nguoi dung crawl truong nao.

Thiet ke va ly do: `docs/ai-crawler.md`. Doc file do neu can hieu vi sao lam the nay.

## Nguyen tac (khong duoc vi pham)

1. **Khong bao gio tu tinh so.** Chi doc `amount_original` + `unit_original` y nguyen
   tai lieu. `amount_per_year` tinh bang `crawler.schema.quy_doi_ve_dong_nam()`.
   Validator se bat neu lech — dung sua validator cho khop, sua so lieu.
2. **Khong trich duoc cau nguyen van thi vut record do.** Moi dong JSONL phai co
   `evidence.quote` la cau co that trong tai lieu, con nguyen con so. Khong dien giai,
   khong tom tat, khong doan.
3. **Khong chac thi danh dau, dung doan.** `major_slug = null` khi chua map duoc nganh;
   `confidence = estimated` khi so lieu tu bao chi chu khong tu truong. Validator tu
   bat cac truong hop nay thanh `needs_review`.
4. **Uu tien nguon chinh thuc.** Website truong > bao chi. Bao chi chi dung de *tim*
   tai lieu goc va doi chieu, khong dung lam nguon cuoi cung (`confidence` toi da la
   `published_unverified`).
5. **Ton trong trang chu.** Chi tai tai lieu cong khai, khong vuot rate-limit, khong
   bypass chan. Trang tra 403/429 thi bo qua va ghi lai, khong thu meo khac.

## 7 buoc

### 1 · Tim nguon — `WebSearch`

Doc ten truong tu `seeds/001_schools.sql` (grep slug do). Roi tim:

```
"<ten truong>" hoc phi <nam> de an tuyen sinh
site:<domain truong> hoc phi
```

Muc tieu: URL cua **de an tuyen sinh** (PDF) hoac **thong bao hoc phi** tren domain
chinh thuc. Bai bao chi chi dung de biet con so *nen* la bao nhieu — de doi chieu o
buoc 5. Ghi lai ca hai loai URL.

> Day la buoc ton cong nhat, khong phai buoc trich xuat. Trang tim thay dau tien
> thuong la FAQ hoac trang gioi thieu, khong co bang hoc phi. Kien nhan tim tiep.

### 2 · Tai ve — `crawler.fetch`

```bash
uv run python -m crawler.fetch <slug> "<url>" --doc-type de_an_tuyen_sinh
```

`--doc-type`: `de_an_tuyen_sinh` | `thong_bao_hoc_phi` | `quy_dinh_nghe` | `khac`.
Ghi ra `crawler/work/<slug>/raw/` + `meta.json`. Tai tat ca URL ung vien truoc khi
sang buoc 3.

### 3 · Cat lat — `crawler.slice`

```bash
uv run python -m crawler.slice <slug>
```

- HTML → `crawler/work/<slug>/slices/*.txt`, chi con doan co tu khoa hoc phi.
- Bao `[TRONG]` = tai lieu do khong co bang hoc phi → **quay lai buoc 1**, dung co doc.
- PDF → bao `[bo qua]`, sang buoc 4b.

### 4a · Doc lat da cat (uu tien)

`Read` file `.txt` trong `slices/`. Nho, re, thuong du de lay het so.

### 4b · Doc PDF truc tiep (khi 4a khong du)

`Read` file `.pdf` trong `raw/` voi tham so `pages`:

- Toi da **20 trang moi lan** `Read`; PDF > 10 trang **bat buoc** truyen `pages`.
- Muc hoc phi trong de an tuyen sinh gan nhu luon o **muc 8-10** hoac phu luc cuoi.
  Doc muc luc (trang 1-3) truoc de biet nhay den trang nao — dung doc tuan tu tu dau.
- PDF ban scan van doc duoc (Claude da phuong thuc), khong can OCR rieng.

### 5 · Viet JSONL

Ghi `seeds/<slug>.jsonl`, moi dong 1 muc hoc phi, theo `crawler/schema.py::TuitionRow`.

Truoc khi viet, tinh `amount_per_year` bang code — dung nham:

```bash
uv run python -c "
from crawler.schema import quy_doi_ve_dong_nam as q
from app import enums
print(q(<so_goc>, enums.TuitionUnit.<DON_VI>, <so_tin_chi_hoac_None>))
"
```

Ghi chu ve cac truong hay sai:

| Truong | Lay tu dau |
|---|---|
| `track` | `dai_tra` \| `chat_luong_cao` \| `tien_tien` \| `quoc_te`. Chuong trinh lien ket nuoc ngoai = `quoc_te`. |
| `language` | `vi` \| `en` \| `vi_en`. Chuong trinh day bang tieng Anh = `en`. |
| `academic_year` | `"2026-2027"` — 2 nam lien tiep. Tai lieu ghi "nam hoc 2026" thi la `2026-2027`. |
| `is_projected` | `false` neu truong cong bo so do. `true` neu la so du phong theo lo trinh tang. |
| `confidence` | `verified` (co nguon + da doi chieu) \| `published_unverified` (truong cong bo, chua doi chieu) \| `estimated` (suy ra / tu bao chi) |
| `major_slug` | `null` neu chua chac — dung bia slug. |
| `evidence.page` | So trang PDF. `null` cho nguon HTML. |

### 6 · Kiem tra

```bash
uv run python -m crawler.validate seeds/<slug>.jsonl
```

Co loi → sua **du lieu**, chay lai. Khong sua validator.

Doi chieu chung voi con so tu bao chi o buoc 1: lech nhieu = doc nham cot hoac nham
don vi. Lech thi tin tai lieu goc, nhung ha `confidence` va ghi `review_reason`.

### 7 · Bao cao

Bao cho nguoi dung, ngan gon:

- Bao nhieu dong, khoang hoc phi, cac he tim duoc
- Bao nhieu dong `needs_review` va vi sao
- Nguon nao dung, nguon nao that bai (403, khong co bang hoc phi...)
- **Nhung gi KHONG lay duoc** — nganh thieu, nam thieu. Day la phan quan trong nhat
  cua bao cao: nguoi duyet can biet lo hong o dau.

Dung tu chay `scripts/seed.py`. Nguoi duyet lam viec do.

## Bay da gap that (doc truoc khi trich xuat)

Ghi lai tu lan chay dau tien tren UIT (2026-09-04). Day khong phai gia dinh.

**1. Mot van ban co NHIEU muc gia khac nhau — phai doc het bang truoc khi chon.**
Quyet dinh hoc phi CLC cua UIT co 3 muc/tin chi trong CUNG mot bang:

| Noi dung thu | Muc thu |
|---|---|
| GDTC + Ly luan chinh tri + mon chung voi CQ chuan | 1.150.000 d/TC |
| Giang day bang tieng Viet (hoc rieng cua CLC) + ngoai ngu | 1.300.000 d/TC |
| Giang day bang tieng Anh (hoc rieng cua CLC) | 1.500.000 d/TC |

Lay dong dau tien (mon chung!) lam "hoc phi CLC" la sai. Doc HET bang, hieu tung
dong la gi, roi moi chon. Neu khong chac dong nao ung voi hoc phi chinh — bo qua.

**2. Don gia tin chi KHONG quy doi duoc ra dong/nam neu tai lieu khong ghi tong
tin chi.** Sinh vien CLC hoc lan lon ca 3 muc tren, nen khong muc nao nhan 30 ra
duoc con so that. `crawler.validate` se BAO LOI neu ban dung so tin chi mac dinh.
Dung tim cach lach — bo dong do va ghi vao bao cao "khong lay duoc".
**Thieu du lieu con hon du lieu sai.**

**3. Bang thuong co ca hoc ky chinh VA hoc ky he.** Muc he cao hon (UIT: 1.725.000
vs 1.150.000 d/TC). Chi lay muc **hoc ky chinh**. Doc tieu de nhom (`I`, `II`,
`III`) de biet dang o phan nao.

**4. `evidence.quote` phai la chuoi ky tu CO THAT, khong phai cau ban ghep lai.**
Lan chay dau, quote bi ghep tu tieu de van ban + o trong bang thanh mot cau khong
ton tai. Neu bang bi tach cot, ghep bang dau `—` va giu nguyen chu trong tung o:
`"Khoa 2022 den khoa 2025 — Hoc phi hoc moi: 37.000.000 dong/Nam hoc"`.
Khong dien them chu nao cua ban vao.

**5. Trang tin chinh cua truong thuong render bang JavaScript.** `crawler.slice`
bao `[TRONG]` la dau hieu do. Tim sang trang **Phong Ke hoach - Tai chinh**
(`khtc.<domain>`) — thuong la HTML tinh, dinh kem thang PDF quyet dinh.

## Bay moi phat hien — lan chay tren TDTU / HUST / Van Lang (2026-09-05)

Lan nay chia buoc 1-3 cho Haiku, buoc 4 (trich xuat) tu nguoi/model manh hon lam.
Ket qua: **khong con dong nao bi bia so** (0/3 o TDTU, so voi 2/6 bi bia o UIT khi
1 model lam ca 7 buoc) — nhung **do phu (coverage) giam manh**: HUST va Van Lang cho
**0 dong** vi tu choi doan thay vi ep so. Day la danh doi dung huong: **thieu du
lieu con hon du lieu sai** khong phai khau hieu suong.

**6. Ky tu co dau trong URL (nguoi Duc/Y) phai encode dung — 1 bit sai la 404
am tham.** HUST co PDF that o URL chua "Nguyễn Quốc Đạt" nhung Haiku encode chu
"Đ" (U+0110) thanh `%C4%80` (sai — do la chu "Ā") thay vi `%C4%90` (dung). Ket qua
la 404 va Haiku bao "URL co the sai hoac file da bi xoa" roi bo cuoc, trong khi
file THAT SU ton tai. Neu tai file lien quan Vietnamese dau tien that bai voi 404,
**thu tim lai chinh URL do qua WebSearch** (search engine da index URL encode dung)
truoc khi ket luan "khong ton tai".

**7. Hoc phi tinh theo tin chi CHI dung duoc neu CUNG tai lieu (hoac tai lieu lien
quan) cho biet tong so tin chi/nam.** HUST cong bo "muc thu/1 TCHP" (tin chi hoc
phi) kem theo mot Phu luc RIENG quy doi TCHT (tin chi hoc tap) sang TCHP — nhung
day chi la CACH TINH (he so theo loai hoc phan: ly thuyet = 1, thi nghiem = 1.5,
do an = 2...), KHONG phai tong so tin chi/nam. Khong co tai lieu nao cho con so
tong ket → **khong the quy doi ra dong/nam ma khong bia**. Day khac voi truong hop
UIT (co the tinh duoc, chi la sai vi chon nham hang) — o day THUC SU thieu du lieu,
khong phai loi doc.

**8. "Dong/hoc ky" la don vi that nhung schema hien tai KHONG co, va so hoc ky/nam
KHONG luon la 2.** HUST cong bo chuong trinh TROY (lien ket cap bang nuoc ngoai) la
"30 trieu dong/mot hoc ky", nhung "mot nam hoc gom 3 hoc ky" (khong phai 2). Neu tu
y nhan 2 se sai 33%. `TuitionUnit` enum (`app/enums.py`) chi co
`dong_nam | dong_thang | dong_tin_chi` — khong co `dong_hoc_ky`. **Khong tu them
gia tri enum hay tu quy doi** — bao lai cho nguoi van hanh de quyet dinh co can
mo rong schema khong, dung tu xu ly bang each nhan nham so hoc ky.

**9. Bang "hoc phi trung binh" hoac khoang gia (VD "tu 50 den 70 trieu/nam") ap
dung cho NHIEU nganh gop nhom — schema doi 1 con so/nganh, tai lieu cho 1 khoang.**
Gap o ca TDTU (chuong trinh tien tien/tieng Anh/lien ket: "Tu 56,7 den 57,7 trieu
dong/nam" cho ca nhom 4-5 nganh) va Van Lang (nganh Du lich: "50 - 70 trieu
dong/nam hoc, tuy theo so tin chi dang ky").

**Quyet dinh cua chu du an (2026-09-05): lay MAX cua khoang.** Ly do: hoc phi
thuc te nguoi hoc phai tra khi dang ky du/toi da tin chi la MAX; lay MIN se lam
UI "re hon that", rui ro hon la "dat hon that". Khi ap dung:
- `amount_original` = `amount_per_year` = dau MAX cua khoang, don vi giu nguyen
  nhu tai lieu (thuong da la dong_nam).
- LUON dat `confidence` thap hon 1 bac so voi neu co so chinh xac (toi da
  `published_unverified`, va `estimated` neu nguon la bai bao/tin tuc — xem muc 10).
- LUON ghi `review_reason` neu ro day la MAX cua 1 khoang cho ca nhom/khoang gia,
  KHONG phai gia rieng cho 1 nganh — vi du: "MAX cua khoang cong bo cho ca nhom
  [X, Y, Z]; khoang goc: tu A den B trieu/nam". Nguoi duyet phai thay ngay day
  khong phai so chinh xac tuyet doi.
- Neu tai lieu chi cho don gia (VD dong/tin chi) CHUA co tong tin chi/nam — day
  KHONG phai truong hop nay (muc 7), van phai bo qua, khong duoc "MAX hoa" mot
  don gia thanh tong nam.

**10. Mot trang tin (bai bao) tren CHINH domain truong (VD vlu.edu.vn/news/...)
van chi la bao chi/PR, khong phai van ban chinh thuc.** No co the cho khoang gia
(xem muc 9) thay vi so chinh xac, va khong co chu ky/so quyet dinh. `confidence`
toi da la `estimated`, khong phai `published_unverified` — chi `published_unverified`
khi nguon la thong bao/quyet dinh chinh thuc (co so hieu luc, nguoi ky).

**11. Subagent co the tu y lam qua pham vi duoc giao ROI bao cao sai ve viec do.**
Khi giao rieng buoc 1-3 cho Haiku, no van tu doc file va rut so ra de "bao cao them"
— nhung dong thoi ghi nham nhan `[TRONG]` cho file THAT SU CO NOI DUNG (vi no nhin
vao ket qua crawler.slice bao con so tu khoa nhung roi tu mau thuan khi mo ta noi
dung ben duoi). **Luon tu doc file `slices/*.txt` that su, dung tin bao cao tom
tat cua subagent** — dac biet khi bao cao co dau hieu mau thuan (vua noi trong vua
mo ta noi dung).

## Bay moi phat hien lan 2 — NEU / USSH / RMIT (2026-09-05)

**12. Nhieu truong dinh gia theo KHOA NHAP HOC (cohort), khong chi theo nam hoc —
khoa cang moi hoc phi cang cao, va day KHONG PHAI la is_projected.** NEU: cung 1
chuong trinh, cung nam hoc 2026-2027, nhung E-BBA "khoa 65" tra 51tr, "khoa 66-67"
tra 56,5tr, "khoa 68" (nhap hoc 2026) tra 60tr — 3 muc gia CO THAT cung ton tai
song song. UIT truoc do cung the ("Khoa 2022 den khoa 2025" khac "Khoa 2021" khac
"Khoa 2020 tro ve truoc"). **Quy uoc: LUON lay muc cua khoa MOI NHAT dang tuyen
sinh nam hien tai** — do moi la "so Nam 1 cong bo" ma is_projected=false gia dinh.
Cac muc khoa cu hon la gia "khoa so" (grandfathered) cho sinh vien dang hoc, KHONG
phai gia cho nguoi hoc moi — dung lay nham. Schema hien tai (`programs` /
`tuition_records`) KHONG co truong luu "khoa" — neu can phan biet ro rang phai
mo rong schema; hien tai chi ghi chu thich trong `review_reason`.

**13. Truong lon co the co NHIEU HON 4 "he dao tao" phan biet — vuot so gia tri
cua `ProgramTrack` enum.** NEU co it nhat 5 loai gia riêng biet cho dai hoc chinh
quy: dai tra (theo tin chi), CLC, POHE, Tien tien, VA rieng ~9 muc gia khac nhau
cho ~30 chuong trinh day bang tieng Anh (moi chuong trinh/nhom chuong trinh 1 gia
rieng, khong dung nhat). Enum `ProgramTrack` chi co 4 gia tri
(dai_tra/chat_luong_cao/tien_tien/quoc_te) — khong co gia tri nao danh rieng cho
"chuong trinh tieng Anh khong phai CLC/Tien tien" hay cho "POHE". Tam thoi: gan
gia tri GAN NGHIA NHAT (thuong la chat_luong_cao) va LUON ghi review_reason neu
ro day la anh xa gan dung, khong phai khop chinh xac. Day la quyet dinh san pham
can xem lai neu nhieu truong lap lai kieu nay (co nen them gia tri enum khong).

**14. Mot so truong (dac biet truong tu von nuoc ngoai) KHONG co ban tinh
(fallback) nao ngoai app/website JS — khong PDF, khong trang tinh, khong bai bao
co so cu the.** RMIT Viet Nam: trang "tuition-fees" dung JS render (curl khong
lay duoc), va tai lieu PDF chinh thuc duy nhat tim duoc ("2026 Student Fees &
Charges Guide", 59 trang) chi la **chinh sach/dieu khoan thanh toan**, khong co
BANG GIA nao — chinh tai lieu do noi ro "gia hoc phi duoc cong bo tren website"
(tuc la o chinh trang JS ma khong lay duoc). WebSearch tim bai bao cung khong ra
con so cu the. Ket qua dung: **0 dong, khong bia**. Day la truong hop khac hoan
toan Van Lang (co nguon tinh nhung chi cho khoang gia) — o day THUC SU khong co
nguon tinh nao ca. Neu gap tinh huong nay, dung co gang doc PDF "guide"/"policy"
tim so — doc muc luc truoc, neu khong thay muc "Fee Schedule" hay bang gia cu the
thi dung phi thoi gian doc het 50+ trang.

**15. `crawler/slice.py` co the CAT MAT ca 1 bang gia neu tu khoa khong khop dinh
dang "X trieu dong" (khong co "/nam" theo sau).** Da SUA (2026-09-05): them "trieu
dong" (khong bat buoc hau to) vao TU_KHOA. Truoc khi sua, bang ~30 chuong trinh
tieng Anh cua NEU (dang "55 trieu dong Ten chuong trinh") bi mat gan het vi 2 lan
xuat hien tu khoa "hoc phi" gan nhat cach nhau qua xa de gop cua so. Neu ket qua
slice co it doan (`X lat`) hoac ban thay so lieu "dut quang" bat thuong, **luon
doc lai TOAN BO raw HTML/PDF truc tiep de doi chieu**, dung chi tin ket qua slice.

## Checkpoint

`crawler/work/<slug>/meta.json` ghi lai file da tai. Chay lai `crawler.fetch` cho
URL da co se ghi de — an toan, khong tao ban trung. Bi ngat giua chung thi doc
`meta.json` de biet da toi dau, khong lam lai tu dau.
