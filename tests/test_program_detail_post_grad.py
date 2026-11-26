"""F10 — `postGrad` tren GET /api/v1/schools/{s}/majors/{m}: 3 trang thai (khong
co / co co nhung chua co so / co so) + `totalWithLicense` giu dinh nghia cu.

Dung CSV that trong seeds/008 + 009 (co track, chay duoc tren CI) — tong ky vong
tinh lai tu `parse_csvs()` de test khong vo moi lan owner sua so lieu.
"""

from app.db import SessionLocal
from app.enums import ConfidenceLevel, ProgramTrack, TuitionUnit
from app.main import app
from app.models import Major, Program, School, TuitionRecord
from httpx import ASGITransport, AsyncClient
from scripts.seed_post_grad import parse_csvs
from scripts.seed_post_grad import run as run_post_grad
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from tests.factories import seed_minimal

_EXTRA = (("luat", 25_000_000), ("y-khoa", 50_000_000))


async def _seed() -> None:
    await seed_minimal()
    async with SessionLocal() as s:
        school = await s.scalar(select(School).where(School.slug == "truong-a"))
        assert school is not None
        for slug, amount in _EXTRA:
            major = await s.scalar(select(Major).where(Major.slug == slug))
            assert major is not None
            program = Program(
                school_id=school.id,
                major_id=major.id,
                track=ProgramTrack.DAI_TRA,
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
    await run_post_grad()


async def _detail(major: str) -> dict:
    async with AsyncClient(
        transport=ASGITransport(app=app), base_url="http://test"
    ) as client:
        resp = await client.get(f"/api/v1/schools/truong-a/majors/{major}")
    assert resp.status_code == 200
    return resp.json()


async def test_major_without_license_has_null_post_grad(db: AsyncSession) -> None:
    await _seed()
    body = await _detail("cong-nghe-thong-tin")

    assert body["major"]["requiresPracticeLicense"] is False
    assert body["postGrad"] is None
    program = body["programs"][0]
    assert program["totalWithLicense"] == program["totalCourse"]


async def test_flagged_major_without_data_has_empty_steps(db: AsyncSession) -> None:
    await _seed()
    body = await _detail("y-khoa")

    assert body["major"]["requiresPracticeLicense"] is True
    assert body["postGrad"] == {
        "profession": "bác sĩ",
        "steps": [],
        "totalCostMin": 0,
        "totalCostMax": 0,
        "totalMonths": 0,
        "hasUnknownDuration": False,
        "checkedAt": None,
    }
    program = body["programs"][0]
    assert program["totalWithLicense"] == program["totalCourse"]


async def test_law_major_returns_steps_and_range(db: AsyncSession) -> None:
    await _seed()
    body = await _detail("luat")
    _, steps_csv = parse_csvs()
    expected = steps_csv["luat-su"]

    post_grad = body["postGrad"]
    assert post_grad["profession"] == "luật sư"
    assert [s["stepOrder"] for s in post_grad["steps"]] == [
        s.step_order for s in expected
    ]
    assert post_grad["totalCostMin"] == sum(s.cost_min for s in expected)
    assert post_grad["totalCostMax"] == sum(s.cost_max for s in expected)
    assert post_grad["totalMonths"] == sum(s.duration_months or 0 for s in expected)
    assert post_grad["hasUnknownDuration"] == any(
        s.duration_months is None for s in expected
    )
    first = post_grad["steps"][0]
    assert first["source"]["url"] == expected[0].source_url
    assert first["source"]["docType"] == "quy_dinh_nghe"
    assert first["source"]["checkedAt"].startswith(expected[0].checked_on.isoformat())
    assert post_grad["checkedAt"].startswith(
        min(s.checked_on for s in expected).isoformat()
    )
    # Dinh nghia cu giu nguyen cho MCP: tong hoc phi + Σ cost_max.
    program = body["programs"][0]
    assert program["totalWithLicense"] == (
        program["totalCourse"] + post_grad["totalCostMax"]
    )
