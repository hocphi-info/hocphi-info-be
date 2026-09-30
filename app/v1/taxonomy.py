"""GET /api/v1/taxonomy, /api/v1/taxonomy/{code} — doc cay phan loai nganh
(Linh vuc -> Nhom nganh -> Nganh) kem so lieu "co du lieu hoc phi".

Cho MCP server (chang B) va bat ky client nao can duyet cay. Day la cho
`WITH RECURSIVE` co ly do that:

- di LEN theo `parent_code` -> `path` (breadcrumb tu linh vuc xuong nut dang xem);
- di XUONG -> moi hau due cua nut (tinh `majors` + `children`), gop so lieu ve
  tung con truc tiep.

Cay co do sau co dinh 3 cap nen `LIKE 'ma%'` cung du; van dung de quy vi
`parent_code` la nguon su that (mot truy van cho moi cap, them cap khong phai
sua). Chi dem nhanh CO du lieu (co ban ghi hoc phi da cong bo, chuong trinh /
nganh / truong chua xoa mem); khoang hoc phi nam 1 chi tinh he DAI TRA
(STATS_TRACK) — cung nguyen tac "khong tron he" nhu `relatedMajors`.
`unclassified` = nganh chua co ma 7 so (`majors.code IS NULL`).
"""

import re

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import distinct, func, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.sql import Select

from app.db import get_session
from app.models import Major, Program, School, TaxonomyNode
from app.queries import latest_published_tuition_subquery
from app.schemas.common import CamelModel
from app.v1.schools import STATS_TRACK

router = APIRouter(tags=["taxonomy"])

UNCLASSIFIED = "unclassified"
UNCLASSIFIED_NAME = "Chưa phân loại"
_CODE_RE = re.compile(r"^(\d{3}|\d{5}|\d{7})$")


# ── Response models ─────────────────────────────────────────────────────────
class TaxonomyNodeRefOut(CamelModel):
    code: str
    name: str
    # 0 = "Chua phan loai" (nut gia); 1 = linh vuc, 2 = nhom nganh, 3 = nganh.
    level: int


class TaxonomyChildOut(TaxonomyNodeRefOut):
    """Nut con truc tiep CO du lieu; so dem gop tu TOAN BO hau due."""

    n_majors: int
    n_programs: int


class TaxonomySummaryOut(CamelModel):
    n_majors: int
    n_programs: int


class TaxonomyMajorOut(CamelModel):
    """Nganh cua hocphi co du lieu duoi nut dang xem."""

    slug: str
    name: str
    code: str | None
    # So truong co it nhat 1 chuong trinh cua nganh nay co hoc phi cong bo.
    n_schools: int
    # Khoang hoc phi nam 1 CHI he dai tra; null khi nganh chi co he khac.
    min_year1_amount: int | None
    max_year1_amount: int | None


class TaxonomyRootsOut(CamelModel):
    """Cac linh vuc co du lieu (+ tong nganh chua phan loai neu > 0)."""

    fields: list[TaxonomyChildOut]
    unclassified: TaxonomySummaryOut | None


class TaxonomyNodeDetailOut(TaxonomyNodeRefOut):
    n_majors: int
    n_programs: int
    # Tu linh vuc xuong nut dang xem (bao gom chinh no). Rong voi `unclassified`.
    path: list[TaxonomyNodeRefOut]
    children: list[TaxonomyChildOut]
    majors: list[TaxonomyMajorOut]


# ── Query helpers ───────────────────────────────────────────────────────────
def _data_rows() -> Select:
    """1 dong / chuong trinh CO hoc phi cong bo, kem nganh — nen cua moi phep dem."""
    latest_tr = latest_published_tuition_subquery()
    return (
        select(
            Program.id.label("program_id"),
            Program.school_id.label("school_id"),
            Program.track.label("track"),
            Major.id.label("major_id"),
            Major.slug.label("major_slug"),
            Major.name.label("major_name"),
            Major.code.label("major_code"),
            latest_tr.c.amount_per_year.label("amount"),
        )
        .select_from(Program)
        .join(Major, Major.id == Program.major_id)
        .join(School, School.id == Program.school_id)
        .join(latest_tr, latest_tr.c.program_id == Program.id)
        .where(
            Program.deleted_at.is_(None),
            Major.deleted_at.is_(None),
            School.deleted_at.is_(None),
        )
    )


def _majors_query(data, scope) -> Select:  # type: ignore[no-untyped-def]
    """Ngành co du lieu, gom theo nganh. `scope` la dieu kien loc tren `data`."""
    dai_tra = data.c.track == STATS_TRACK
    return (
        select(
            data.c.major_slug,
            data.c.major_name,
            data.c.major_code,
            func.count(distinct(data.c.school_id)),
            func.min(data.c.amount).filter(dai_tra),
            func.max(data.c.amount).filter(dai_tra),
        )
        .where(scope)
        .group_by(
            data.c.major_id, data.c.major_slug, data.c.major_name, data.c.major_code
        )
        .order_by(func.count(distinct(data.c.school_id)).desc(), data.c.major_name)
    )


def _major_out(row) -> TaxonomyMajorOut:  # type: ignore[no-untyped-def]
    slug, name, code, n_schools, lo, hi = row
    return TaxonomyMajorOut(
        slug=slug,
        name=name,
        code=code,
        n_schools=n_schools,
        min_year1_amount=lo,
        max_year1_amount=hi,
    )


def _descendants_cte(root_code: str):  # type: ignore[no-untyped-def]
    """`WITH RECURSIVE`: chinh nut + moi hau due (di XUONG theo parent_code)."""
    sub = (
        select(TaxonomyNode.code)
        .where(TaxonomyNode.code == root_code)
        .cte("sub", recursive=True)
    )
    return sub.union_all(
        select(TaxonomyNode.code).where(TaxonomyNode.parent_code == sub.c.code)
    )


# ── Endpoints ───────────────────────────────────────────────────────────────
@router.get("/api/v1/taxonomy", response_model=TaxonomyRootsOut)
async def get_taxonomy_roots(
    session: AsyncSession = Depends(get_session),
) -> TaxonomyRootsOut:
    data = _data_rows().subquery("data")

    # Moi hang cua `data` -> linh vuc cua nganh (nganh -> nhom -> linh vuc, cung la
    # 2 lan tu tham chieu; day chi la JOIN vi cap co dinh, khong can de quy).
    group_node = TaxonomyNode.__table__.alias("g")
    field_node = TaxonomyNode.__table__.alias("f")
    major_node = TaxonomyNode.__table__.alias("m")
    rows = (
        await session.execute(
            select(
                field_node.c.code,
                field_node.c.name,
                field_node.c.level,
                func.count(distinct(data.c.major_id)),
                func.count(distinct(data.c.program_id)),
            )
            .select_from(data)
            .join(major_node, major_node.c.code == data.c.major_code)
            .join(group_node, group_node.c.code == major_node.c.parent_code)
            .join(field_node, field_node.c.code == group_node.c.parent_code)
            .group_by(field_node.c.code, field_node.c.name, field_node.c.level)
            .order_by(func.count(distinct(data.c.program_id)).desc(), field_node.c.code)
        )
    ).all()

    unclassified = (
        await session.execute(
            select(
                func.count(distinct(data.c.major_id)),
                func.count(distinct(data.c.program_id)),
            ).where(data.c.major_code.is_(None))
        )
    ).one()

    return TaxonomyRootsOut(
        fields=[
            TaxonomyChildOut(
                code=code, name=name, level=level, n_majors=n_majors, n_programs=n_progs
            )
            for code, name, level, n_majors, n_progs in rows
        ],
        unclassified=(
            TaxonomySummaryOut(n_majors=unclassified[0], n_programs=unclassified[1])
            if unclassified[1]
            else None
        ),
    )


@router.get("/api/v1/taxonomy/{code}", response_model=TaxonomyNodeDetailOut)
async def get_taxonomy_node(
    code: str,
    session: AsyncSession = Depends(get_session),
) -> TaxonomyNodeDetailOut:
    data = _data_rows().subquery("data")

    if code == UNCLASSIFIED:
        majors = [
            _major_out(r)
            for r in (
                await session.execute(_majors_query(data, data.c.major_code.is_(None)))
            ).all()
        ]
        n_programs = await session.scalar(
            select(func.count(distinct(data.c.program_id))).where(
                data.c.major_code.is_(None)
            )
        )
        return TaxonomyNodeDetailOut(
            code=UNCLASSIFIED,
            name=UNCLASSIFIED_NAME,
            level=0,
            n_majors=len(majors),
            n_programs=n_programs or 0,
            path=[],
            children=[],
            majors=majors,
        )

    if not _CODE_RE.match(code):
        raise HTTPException(status_code=404, detail="Taxonomy node not found")

    # 1) di LEN: nut + to tien -> `path` (root truoc).
    anc = (
        select(
            TaxonomyNode.code,
            TaxonomyNode.name,
            TaxonomyNode.level,
            TaxonomyNode.parent_code,
        )
        .where(TaxonomyNode.code == code)
        .cte("anc", recursive=True)
    )
    anc = anc.union_all(
        select(
            TaxonomyNode.code,
            TaxonomyNode.name,
            TaxonomyNode.level,
            TaxonomyNode.parent_code,
        ).where(TaxonomyNode.code == anc.c.parent_code)
    )
    path_rows = (
        await session.execute(
            select(anc.c.code, anc.c.name, anc.c.level).order_by(anc.c.level)
        )
    ).all()
    if not path_rows:
        raise HTTPException(status_code=404, detail="Taxonomy node not found")
    path = [TaxonomyNodeRefOut(code=c, name=n, level=lv) for c, n, lv in path_rows]
    node = path[-1]

    # 2) di XUONG: moi hau due cua nut -> ngành co du lieu + tong.
    sub = _descendants_cte(code)
    scope = data.c.major_code.in_(select(sub.c.code))
    majors = [
        _major_out(r) for r in (await session.execute(_majors_query(data, scope))).all()
    ]
    n_programs = await session.scalar(
        select(func.count(distinct(data.c.program_id))).where(scope)
    )

    # 3) con truc tiep CO du lieu, moi con gop so lieu tu hau due cua no:
    # `tree(child_code, code)` gan moi nut ve "con truc tiep" ma no thuoc.
    tree = (
        select(TaxonomyNode.code.label("child_code"), TaxonomyNode.code.label("code"))
        .where(TaxonomyNode.parent_code == code)
        .cte("tree", recursive=True)
    )
    tree = tree.union_all(
        select(tree.c.child_code, TaxonomyNode.code).where(
            TaxonomyNode.parent_code == tree.c.code
        )
    )
    child_node = TaxonomyNode.__table__.alias("c")
    child_rows = (
        await session.execute(
            select(
                child_node.c.code,
                child_node.c.name,
                child_node.c.level,
                func.count(distinct(data.c.major_id)),
                func.count(distinct(data.c.program_id)),
            )
            .select_from(tree)
            .join(child_node, child_node.c.code == tree.c.child_code)
            .join(data, data.c.major_code == tree.c.code)
            .group_by(child_node.c.code, child_node.c.name, child_node.c.level)
            .order_by(func.count(distinct(data.c.program_id)).desc(), child_node.c.code)
        )
    ).all()

    return TaxonomyNodeDetailOut(
        code=node.code,
        name=node.name,
        level=node.level,
        n_majors=len(majors),
        n_programs=n_programs or 0,
        path=path,
        children=[
            TaxonomyChildOut(code=c, name=n, level=lv, n_majors=nm, n_programs=npg)
            for c, n, lv, nm, npg in child_rows
        ],
        majors=majors,
    )
