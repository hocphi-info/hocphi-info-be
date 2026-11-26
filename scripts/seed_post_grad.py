"""Nap chi phi hanh nghe sau tot nghiep (F10) tu 2 file CSV tuyen chon tay:

    uv run python -m scripts.seed_post_grad [--dry-run]

(`scripts.seed` cung goi `run()` o cuoi, nen deploy + `python -m scripts.seed`
la du — xem seeds/README.md.)

- seeds/008_practice_license_majors.csv — nganh nao dan toi nghe can cap phep:
  `major_slug,profession_key,profession_name`. Nhieu nganh chung 1 nghe (vd
  `luat` + `luat-kinh-te` -> `luat-su`). `profession_name` viet thuong, FE ghep
  giua cau ("Muon hanh nghe luật sư ...").
- seeds/009_post_grad_steps.csv — lo trinh TOI THIEU bat buoc cua tung nghe:
  `profession_key,step_order,step_name,provider,duration_months,cost_min,
  cost_max,confidence,note,source_url,source_published_date,checked_on`.
  Nghe co trong 008 ma chua co buoc nao -> FE chi hien canh bao, khong hien so.

KHAC cac buoc seed khac (chi THEM): 2 file nay la nguon su that DUY NHAT cho
`majors.requires_practice_license/practice_profession` va `post_grad_requirements`
(authoritative):
  * nganh co trong 008 -> bat co + ten nghe; nganh dang bat co ma khong con
    trong 008 -> tat co (false/NULL) va soft-delete cac buoc cua no;
  * cac buoc cua 1 nganh khac CSV -> soft-delete het buoc dang hieu luc roi chen
    lai (unique index (major_id, step_order) chi tinh dong chua xoa nen chen lai
    cung step_order duoc). Giong het CSV -> khong dong vao (chay lai khong sinh
    them dong da xoa).
Moi thu chay trong 1 transaction: validate loi hoac slug khong ton tai -> khong
ghi gi ca.
"""

import asyncio
import csv
import sys
from dataclasses import dataclass
from datetime import UTC, date, datetime, time
from pathlib import Path

from app.db import SessionLocal, engine
from app.enums import ConfidenceLevel, SourceDocType
from app.models import Major, PostGradRequirement, Source
from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession

SEEDS_DIR = Path(__file__).resolve().parent.parent / "seeds"
MAJORS_CSV_PATH = SEEDS_DIR / "008_practice_license_majors.csv"
STEPS_CSV_PATH = SEEDS_DIR / "009_post_grad_steps.csv"

MAJORS_COLUMNS = ("major_slug", "profession_key", "profession_name")
STEPS_COLUMNS = (
    "profession_key",
    "step_order",
    "step_name",
    "provider",
    "duration_months",
    "cost_min",
    "cost_max",
    "confidence",
    "note",
    "source_url",
    "source_published_date",
    "checked_on",
)
VALID_URL_PREFIXES = ("http://", "https://")
VALID_CONFIDENCE = {c.value for c in ConfidenceLevel}


class PostGradSeedError(Exception):
    """CSV sai hoac tham chieu nganh khong ton tai — khong ghi gi vao DB."""


@dataclass(frozen=True)
class StepRow:
    step_order: int
    step_name: str
    provider: str | None
    duration_months: int | None
    cost_min: int
    cost_max: int
    confidence: ConfidenceLevel
    note: str | None
    source_url: str
    source_published_date: date | None
    checked_on: date

    def key(self) -> tuple[object, ...]:
        """Phan so sanh voi DB de biet buoc co doi khong (khong gom ngay kiem tra
        — doi ngay chi cap nhat `sources.checked_at`, khong chen lai buoc)."""
        return (
            self.step_order,
            self.step_name,
            self.provider,
            self.duration_months,
            self.cost_min,
            self.cost_max,
            self.confidence,
            self.note,
            self.source_url,
        )


@dataclass
class Counts:
    flagged: int = 0
    unflagged: int = 0
    majors_restepped: int = 0
    steps_inserted: int = 0
    steps_deleted: int = 0
    sources_written: int = 0


def _read_csv(path: Path, columns: tuple[str, ...]) -> list[dict[str, str]]:
    if not path.exists():
        raise PostGradSeedError(f"khong thay {path}")
    # utf-8-sig: tu bo BOM neu Excel them.
    with path.open(encoding="utf-8-sig", newline="") as fh:
        reader = csv.DictReader(fh)
        missing = [c for c in columns if c not in (reader.fieldnames or [])]
        if missing:
            raise PostGradSeedError(f"{path.name}: header thieu cot {missing}")
        return [{k: (v or "").strip() for k, v in row.items()} for row in reader]


def _opt_int(raw: str) -> int | None:
    return int(raw) if raw else None


def parse_csvs() -> tuple[dict[str, tuple[str, str]], dict[str, list[StepRow]]]:
    """Doc + validate ca 2 file. Tra (slug -> (profession_key, profession_name),
    profession_key -> cac buoc theo step_order). Gom het loi roi raise 1 lan."""
    errors: list[str] = []

    majors: dict[str, tuple[str, str]] = {}
    names: dict[str, str] = {}
    for line_no, row in enumerate(_read_csv(MAJORS_CSV_PATH, MAJORS_COLUMNS), 2):
        slug = row["major_slug"]
        key, name = row["profession_key"], row["profession_name"]
        if not (slug and key and name):
            errors.append(f"008 dong {line_no}: thieu major_slug/profession_key/name")
            continue
        if slug in majors:
            errors.append(f"008 dong {line_no}: {slug!r} bi lap")
        if names.setdefault(key, name) != name:
            errors.append(f"008 dong {line_no}: {key!r} co 2 ten nghe khac nhau")
        majors[slug] = (key, name)

    steps: dict[str, list[StepRow]] = {}
    for line_no, row in enumerate(_read_csv(STEPS_CSV_PATH, STEPS_COLUMNS), 2):
        where = f"009 dong {line_no}"
        key = row["profession_key"]
        if key not in names:
            errors.append(f"{where}: profession_key {key!r} khong co trong 008")
            continue
        try:
            step = StepRow(
                step_order=int(row["step_order"]),
                step_name=row["step_name"],
                provider=row["provider"] or None,
                duration_months=_opt_int(row["duration_months"]),
                # Bat buoc co so: "mien phi" phai ghi ro 0 — de trong se bi hieu
                # nham la 0d va keo tong xuong.
                cost_min=int(row["cost_min"]),
                cost_max=int(row["cost_max"]),
                confidence=ConfidenceLevel(row["confidence"]),
                note=row["note"] or None,
                source_url=row["source_url"],
                source_published_date=(
                    date.fromisoformat(row["source_published_date"])
                    if row["source_published_date"]
                    else None
                ),
                checked_on=date.fromisoformat(row["checked_on"]),
            )
        except ValueError as exc:
            errors.append(f"{where}: {exc}")
            continue
        if not step.step_name:
            errors.append(f"{where}: thieu step_name")
        if not 0 <= step.cost_min <= step.cost_max:
            errors.append(f"{where}: can 0 <= cost_min <= cost_max")
        if step.duration_months is not None and step.duration_months < 0:
            errors.append(f"{where}: duration_months am")
        if not step.source_url.startswith(VALID_URL_PREFIXES):
            errors.append(f"{where}: source_url phai bat dau bang http(s)://")
        steps.setdefault(key, []).append(step)

    for key, rows in steps.items():
        rows.sort(key=lambda s: s.step_order)
        orders = [s.step_order for s in rows]
        if orders != list(range(1, len(rows) + 1)):
            errors.append(f"009 {key!r}: step_order phai lien tuc tu 1, dang {orders}")

    if errors:
        raise PostGradSeedError("\n".join(errors))
    return majors, steps


def _checked_at(d: date) -> datetime:
    # Gio trua UTC (= 19h gio VN): FE/Workers dinh dang theo UTC hay theo gio VN
    # deu ra dung ngay owner ghi, khong lech sang hom truoc.
    return datetime.combine(d, time(12, 0), tzinfo=UTC)


async def _upsert_source(session: AsyncSession, step: StepRow, counts: Counts) -> str:
    """Theo `url` (khong co UNIQUE, dedup theo quy uoc nhu scripts/seed.py).
    Khac `_get_or_create_source` cua seed: CAP NHAT ngay kiem tra + ngay ban hanh
    khi CSV doi, vi day la thong tin FE hien ("Nguon kiem tra lan cuoi")."""
    source = await session.scalar(
        select(Source).where(Source.url == step.source_url, Source.deleted_at.is_(None))
    )
    checked_at = _checked_at(step.checked_on)
    if source is None:
        source = Source(
            url=step.source_url,
            doc_type=SourceDocType.QUY_DINH_NGHE,
            published_date=step.source_published_date,
            checked_at=checked_at,
        )
        session.add(source)
        await session.flush()
        counts.sources_written += 1
        return source.id
    if (source.checked_at, source.published_date) != (
        checked_at,
        step.source_published_date,
    ):
        source.checked_at = checked_at
        source.published_date = step.source_published_date
        counts.sources_written += 1
    return source.id


async def _live_step_keys(
    session: AsyncSession, major_id: str
) -> list[tuple[object, ...]]:
    rows = (
        await session.execute(
            select(
                PostGradRequirement.step_order,
                PostGradRequirement.step_name,
                PostGradRequirement.provider,
                PostGradRequirement.duration_months,
                PostGradRequirement.cost_min,
                PostGradRequirement.cost_max,
                PostGradRequirement.confidence,
                PostGradRequirement.note,
                Source.url,
            )
            .outerjoin(Source, Source.id == PostGradRequirement.source_id)
            .where(
                PostGradRequirement.major_id == major_id,
                PostGradRequirement.deleted_at.is_(None),
            )
            .order_by(PostGradRequirement.step_order)
        )
    ).all()
    return [tuple(r) for r in rows]


async def _soft_delete_steps(session: AsyncSession, major_id: str) -> int:
    result = await session.execute(
        update(PostGradRequirement)
        .where(
            PostGradRequirement.major_id == major_id,
            PostGradRequirement.deleted_at.is_(None),
        )
        .values(deleted_at=datetime.now(UTC))
    )
    return result.rowcount or 0  # type: ignore[attr-defined]


async def apply(
    session: AsyncSession,
    majors_csv: dict[str, tuple[str, str]],
    steps_csv: dict[str, list[StepRow]],
) -> Counts:
    """Ghi vao `session` (KHONG commit — nguoi goi quyet dinh commit/rollback)."""
    counts = Counts()
    live = {
        m.slug: m
        for m in (
            await session.scalars(select(Major).where(Major.deleted_at.is_(None)))
        ).all()
    }
    unknown = sorted(set(majors_csv) - set(live))
    if unknown:
        raise PostGradSeedError(f"008: nganh khong ton tai trong DB: {unknown}")

    for slug, major in sorted(live.items()):
        wanted = majors_csv.get(slug)
        if wanted is None:
            if major.requires_practice_license:
                major.requires_practice_license = False
                major.practice_profession = None
                counts.unflagged += 1
            counts.steps_deleted += await _soft_delete_steps(session, major.id)
            continue

        key, name = wanted
        if (major.requires_practice_license, major.practice_profession) != (True, name):
            major.requires_practice_license = True
            major.practice_profession = name
            counts.flagged += 1

        steps = steps_csv.get(key, [])
        # Nguon truoc (ke ca khi buoc khong doi) de ngay kiem tra luon theo CSV.
        source_ids = [await _upsert_source(session, s, counts) for s in steps]
        if await _live_step_keys(session, major.id) == [s.key() for s in steps]:
            continue

        counts.majors_restepped += 1
        counts.steps_deleted += await _soft_delete_steps(session, major.id)
        await session.flush()  # xoa truoc khi chen lai cung step_order
        for step, source_id in zip(steps, source_ids, strict=True):
            session.add(
                PostGradRequirement(
                    major_id=major.id,
                    step_order=step.step_order,
                    step_name=step.step_name,
                    provider=step.provider,
                    duration_months=step.duration_months,
                    cost_min=step.cost_min,
                    cost_max=step.cost_max,
                    confidence=step.confidence,
                    verified=step.confidence == ConfidenceLevel.VERIFIED,
                    note=step.note,
                    source_id=source_id,
                )
            )
            counts.steps_inserted += 1
    await session.flush()
    return counts


async def run(*, dry_run: bool = False) -> Counts:
    majors_csv, steps_csv = parse_csvs()
    async with SessionLocal() as session:
        counts = await apply(session, majors_csv, steps_csv)
        if dry_run:
            await session.rollback()
        else:
            await session.commit()
    label = "[dry-run] se" if dry_run else "da"
    print(
        f"  [post_grad] {label}: bat co {counts.flagged} nganh, tat co "
        f"{counts.unflagged}, doi buoc {counts.majors_restepped} nganh "
        f"(+{counts.steps_inserted} / -{counts.steps_deleted} buoc), "
        f"ghi {counts.sources_written} nguon"
    )
    return counts


async def main() -> None:
    try:
        await run(dry_run="--dry-run" in sys.argv[1:])
    except PostGradSeedError as exc:
        print(f"Loi, khong ghi gi:\n{exc}")
        sys.exit(1)
    finally:
        await engine.dispose()


if __name__ == "__main__":
    asyncio.run(main())
