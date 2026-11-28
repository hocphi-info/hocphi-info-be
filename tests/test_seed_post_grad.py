"""scripts/seed_post_grad.py — nap co nganh can cap phep + cac buoc hanh nghe tu
2 CSV, theo kieu AUTHORITATIVE (CSV la nguon su that duy nhat).

`seed_minimal()` nap 002_majors.sql (co `luat`, `luat-kinh-te`, `y-khoa`...) ghi
that qua SessionLocal; `run()` cung tu mo SessionLocal + commit that. Fixture `db`
TRUNCATE `majors` + `post_grad_requirements` o dau moi test. `sources` KHONG bi
TRUNCATE nen moi test dung URL rieng (`_url(tag)`) de khong phu thuoc thu tu.
"""

import csv
from pathlib import Path

import pytest
import scripts.seed_post_grad as mod
from app.enums import ConfidenceLevel, SourceDocType
from app.models import Major, PostGradRequirement, Source
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from tests.factories import seed_minimal

_LAW = [
    ("luat", "luat-su", "luật sư"),
    ("luat-kinh-te", "luat-su", "luật sư"),
    ("y-khoa", "bac-si", "bác sĩ"),
]


def _url(tag: str, n: int) -> str:
    return f"https://example.org/{tag}/{n}"


def _step(tag: str, order: int, cost: tuple[int, int] = (1_000_000, 2_000_000)) -> dict:
    return {
        "profession_key": "luat-su",
        "step_order": str(order),
        "step_name": f"Buoc {order}",
        "provider": "HVTP",
        "duration_months": "12",
        "cost_min": str(cost[0]),
        "cost_max": str(cost[1]),
        "confidence": "estimated",
        "note": "",
        "source_url": _url(tag, order),
        "source_published_date": "2026-01-07",
        "checked_on": "2026-11-26",
    }


def _write(path: Path, columns: tuple[str, ...], rows: list[dict]) -> None:
    with path.open("w", encoding="utf-8", newline="") as fh:
        writer = csv.DictWriter(fh, fieldnames=columns)
        writer.writeheader()
        writer.writerows(rows)


@pytest.fixture
def csvs(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> tuple[Path, Path]:
    majors = tmp_path / "008.csv"
    steps = tmp_path / "009.csv"
    monkeypatch.setattr(mod, "MAJORS_CSV_PATH", majors)
    monkeypatch.setattr(mod, "STEPS_CSV_PATH", steps)
    return majors, steps


def _write_all(
    csvs: tuple[Path, Path], majors: list[tuple[str, str, str]], steps: list[dict]
) -> None:
    _write(
        csvs[0],
        mod.MAJORS_COLUMNS,
        [dict(zip(mod.MAJORS_COLUMNS, m, strict=True)) for m in majors],
    )
    _write(csvs[1], mod.STEPS_COLUMNS, steps)


async def _major(db: AsyncSession, slug: str) -> Major:
    major = await db.scalar(select(Major).where(Major.slug == slug))
    assert major is not None
    await db.refresh(major)  # script ghi qua session khac
    return major


async def _live_steps(db: AsyncSession, slug: str) -> list[PostGradRequirement]:
    major = await _major(db, slug)
    return list(
        (
            await db.scalars(
                select(PostGradRequirement)
                .where(
                    PostGradRequirement.major_id == major.id,
                    PostGradRequirement.deleted_at.is_(None),
                )
                .order_by(PostGradRequirement.step_order)
            )
        ).all()
    )


async def test_first_load_flags_majors_and_fans_out_steps(
    db: AsyncSession, csvs: tuple[Path, Path]
) -> None:
    await seed_minimal()
    _write_all(csvs, _LAW, [_step("first", 1), _step("first", 2)])

    counts = await mod.run()

    assert counts.flagged == 3
    for slug in ("luat", "luat-kinh-te"):
        major = await _major(db, slug)
        assert (major.requires_practice_license, major.practice_profession) == (
            True,
            "luật sư",
        )
        steps = await _live_steps(db, slug)
        assert [s.step_order for s in steps] == [1, 2]
        assert steps[0].confidence == ConfidenceLevel.ESTIMATED
    # Nghe co trong 008 nhung chua co buoc -> bat co, khong co buoc nao.
    y_khoa = await _major(db, "y-khoa")
    assert y_khoa.requires_practice_license is True
    assert await _live_steps(db, "y-khoa") == []
    # Nguon: doc_type quy_dinh_nghe + ngay kiem tra (gio trua UTC).
    source = await db.scalar(select(Source).where(Source.url == _url("first", 1)))
    assert source is not None
    assert source.doc_type == SourceDocType.QUY_DINH_NGHE
    assert source.checked_at is not None
    assert source.checked_at.date().isoformat() == "2026-11-26"
    # Ke toan khong co trong CSV -> khong bat co.
    assert (await _major(db, "ke-toan")).requires_practice_license is False


async def test_rerun_same_csv_is_noop(
    db: AsyncSession, csvs: tuple[Path, Path]
) -> None:
    await seed_minimal()
    _write_all(csvs, _LAW, [_step("noop", 1), _step("noop", 2)])
    await mod.run()

    counts = await mod.run()

    assert (counts.flagged, counts.majors_restepped, counts.steps_deleted) == (0, 0, 0)
    total = await db.scalar(
        select(PostGradRequirement.id).where(PostGradRequirement.deleted_at.isnot(None))
    )
    assert total is None  # khong sinh dong da xoa khi CSV khong doi


async def test_fewer_steps_soft_deletes_extra(
    db: AsyncSession, csvs: tuple[Path, Path]
) -> None:
    await seed_minimal()
    _write_all(csvs, _LAW, [_step("fewer", 1), _step("fewer", 2), _step("fewer", 3)])
    await mod.run()

    _write_all(csvs, _LAW, [_step("fewer", 1, cost=(5, 9)), _step("fewer", 2)])
    counts = await mod.run()

    assert counts.majors_restepped == 2  # luat + luat-kinh-te
    steps = await _live_steps(db, "luat")
    assert [(s.step_order, s.cost_min, s.cost_max) for s in steps] == [
        (1, 5, 9),
        (2, 1_000_000, 2_000_000),
    ]


async def test_major_removed_from_csv_is_unflagged(
    db: AsyncSession, csvs: tuple[Path, Path]
) -> None:
    await seed_minimal()
    _write_all(csvs, _LAW, [_step("removed", 1)])
    await mod.run()

    _write_all(csvs, _LAW[:1], [_step("removed", 1)])  # chi con `luat`
    counts = await mod.run()

    assert counts.unflagged == 2
    lkt = await _major(db, "luat-kinh-te")
    assert (lkt.requires_practice_license, lkt.practice_profession) == (False, None)
    assert await _live_steps(db, "luat-kinh-te") == []
    assert len(await _live_steps(db, "luat")) == 1


@pytest.mark.parametrize(
    ("patch", "message"),
    [
        ({"source_url": ""}, "source_url"),
        ({"cost_min": "9", "cost_max": "1"}, "cost_min <= cost_max"),
        ({"cost_min": ""}, "cung co hoac cung trong"),
        ({"cost_min": "", "cost_max": ""}, "note"),
        ({"confidence": "chac-chan"}, "chac-chan"),
        ({"step_order": "3"}, "lien tuc"),
        ({"profession_key": "khong-co"}, "khong co trong 008"),
    ],
)
async def test_invalid_csv_writes_nothing(
    db: AsyncSession, csvs: tuple[Path, Path], patch: dict, message: str
) -> None:
    await seed_minimal()
    _write_all(csvs, _LAW, [_step("bad", 1), {**_step("bad", 2), **patch}])

    with pytest.raises(mod.PostGradSeedError, match=message):
        await mod.run()

    assert (await _major(db, "luat")).requires_practice_license is False


async def test_unknown_major_slug_aborts_whole_run(
    db: AsyncSession, csvs: tuple[Path, Path]
) -> None:
    await seed_minimal()
    _write_all(csvs, [*_LAW, ("khong-ton-tai", "luat-su", "luật sư")], [_step("u", 1)])

    with pytest.raises(mod.PostGradSeedError, match="khong-ton-tai"):
        await mod.run()

    assert (await _major(db, "luat")).requires_practice_license is False


async def test_dry_run_rolls_back(db: AsyncSession, csvs: tuple[Path, Path]) -> None:
    await seed_minimal()
    _write_all(csvs, _LAW, [_step("dry", 1)])

    counts = await mod.run(dry_run=True)

    assert counts.flagged == 3
    assert (await _major(db, "luat")).requires_practice_license is False


async def test_unknown_cost_step_is_stored_as_null(
    db: AsyncSession, csvs: tuple[Path, Path]
) -> None:
    await seed_minimal()
    unknown = {
        **_step("unk", 2),
        "cost_min": "",
        "cost_max": "",
        "note": "Chua cong bo",
    }
    _write_all(csvs, _LAW, [_step("unk", 1), unknown])

    await mod.run()
    counts = await mod.run()  # chay lai voi buoc NULL van la no-op

    steps = await _live_steps(db, "luat")
    assert [(s.cost_min, s.cost_max) for s in steps] == [
        (1_000_000, 2_000_000),
        (None, None),
    ]
    assert counts.majors_restepped == 0


def test_repo_csvs_are_valid() -> None:
    """File CSV that trong seeds/ phai qua validate (CI bat loi nhap tay)."""
    majors, steps = mod.parse_csvs()
    assert majors["luat"] == ("luat-su", "luật sư")
    assert [s.step_order for s in steps["luat-su"]] == [1, 2, 3]
    assert all(s.source_url.startswith("https://") for s in steps["luat-su"])
