"""Du lieu test dung chung cho cac test endpoint phan loai nganh.

Tu dung du lieu nho (2 truong, vai nganh) — KHONG dung seeds/*.jsonl (khong con
track trong git, xem tests/markers.py) nen chay day du tren CI. Nganh + danh muc +
alias lay tu seeds/002..006 (co track). Ghi that vao DB qua `SessionLocal` (nhu
`scripts.seed`) vi endpoint doc bang session rieng, khong thay SAVEPOINT cua
fixture `db`; test chi can co fixture `db` de TRUNCATE sach truoc moi test.
"""

from pathlib import Path

from app.db import SessionLocal
from app.enums import ConfidenceLevel, ProgramTrack, SchoolCategory, TuitionUnit
from app.models import Major, Program, School, TuitionRecord
from scripts.seed import (
    SEEDS_DIR,
    apply_major_taxonomy,
    load_aliases,
    load_taxonomy,
)
from sqlalchemy import select, text

# (truong, nganh, he, hoc phi nam 1)
PROGRAMS = [
    ("truong-a", "khoa-hoc-may-tinh", ProgramTrack.DAI_TRA, 30_000_000),
    ("truong-a", "ky-thuat-phan-mem", ProgramTrack.DAI_TRA, 32_000_000),
    ("truong-a", "ky-thuat-phan-mem", ProgramTrack.CHAT_LUONG_CAO, 90_000_000),
    ("truong-a", "tri-tue-nhan-tao", ProgramTrack.CHAT_LUONG_CAO, 80_000_000),
    ("truong-a", "cong-nghe-thong-tin", ProgramTrack.DAI_TRA, 28_000_000),
    ("truong-a", "digital-art", ProgramTrack.DAI_TRA, 25_000_000),
    ("truong-b", "khoa-hoc-may-tinh", ProgramTrack.DAI_TRA, 40_000_000),
    ("truong-b", "ky-thuat-phan-mem", ProgramTrack.DAI_TRA, 44_000_000),
]


# Doc 1 lan luc import (ham async khong nen doc file blocking).
MAJORS_SQL = (Path(SEEDS_DIR) / "002_majors.sql").read_text(encoding="utf-8")


async def seed_minimal(*, with_taxonomy: bool = True) -> None:
    async with SessionLocal() as s:
        await s.execute(text(MAJORS_SQL))
        if with_taxonomy:
            await load_taxonomy(s)
            await apply_major_taxonomy(s)
            await load_aliases(s)

        schools = {
            slug: School(
                slug=slug,
                name=name,
                short_name=slug.upper(),
                city_code="HCM",
                category=SchoolCategory.CONG_LAP,
            )
            for slug, name in (("truong-a", "Truong A"), ("truong-b", "Truong B"))
        }
        s.add_all(schools.values())
        majors = {m.slug: m for m in (await s.scalars(select(Major))).all()}
        await s.flush()

        for school_slug, major_slug, track, amount in PROGRAMS:
            program = Program(
                school_id=schools[school_slug].id,
                major_id=majors[major_slug].id,
                track=track,
                language="vi",
            )
            s.add(program)
            await s.flush()
            s.add(
                TuitionRecord(
                    program_id=program.id,
                    academic_year="2026-2027",
                    amount_per_year=amount,
                    unit_original=TuitionUnit.DONG_NAM,
                    amount_original=amount,
                    confidence=ConfidenceLevel.PUBLISHED_UNVERIFIED,
                )
            )
        await s.commit()
