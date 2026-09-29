"""Phan loai nganh (taxonomy) cho response — helper dung chung cac router.

`MajorOut` xuat hien o 3 endpoint (majors, chi tiet nganh-truong, chi tiet truong);
ca 3 phai nap `taxonomy` + `aliases` qua CUNG mot cho nay de khong lech nhau.

Linh vuc + nhom nganh cua 1 nganh KHONG luu o `majors` — suy ra tu `majors.code`
qua `taxonomy_nodes.parent_code` (nguyen tac "chi luu so goc, suy ra luc truy
van", xem AGENTS.md). Ca hai truy van ben duoi deu gop theo LO (1 truy van cho
ca danh sach nganh) de khong bi N+1.
"""

from collections.abc import Iterable
from dataclasses import dataclass, field

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import aliased

from app.models import Major, MajorAlias, TaxonomyNode
from app.schemas.common import MajorOut, TaxonomyNodeOut, TaxonomyOut


@dataclass
class MajorContext:
    """Du lieu phan loai da nap san cho 1 lo nganh."""

    # khoa = `majors.code` (ma 7 so); nganh chua phan loai (code NULL) khong co mat.
    taxonomy: dict[str, TaxonomyOut] = field(default_factory=dict)
    # khoa = `majors.id`.
    aliases: dict[str, list[str]] = field(default_factory=dict)


async def load_major_context(
    session: AsyncSession, majors: Iterable[Major]
) -> MajorContext:
    majors = list(majors)
    ctx = MajorContext()

    codes = {m.code for m in majors if m.code is not None}
    if codes:
        group = aliased(TaxonomyNode)
        fld = aliased(TaxonomyNode)
        rows = await session.execute(
            select(TaxonomyNode.code, group.code, group.name, fld.code, fld.name)
            .join(group, group.code == TaxonomyNode.parent_code)
            .join(fld, fld.code == group.parent_code)
            .where(TaxonomyNode.code.in_(codes))
        )
        for code, g_code, g_name, f_code, f_name in rows.all():
            ctx.taxonomy[code] = TaxonomyOut(
                field=TaxonomyNodeOut(code=f_code, name=f_name),
                group=TaxonomyNodeOut(code=g_code, name=g_name),
            )

    ids = {m.id for m in majors}
    if ids:
        alias_rows = await session.execute(
            select(MajorAlias.major_id, MajorAlias.alias)
            .where(MajorAlias.major_id.in_(ids))
            .order_by(MajorAlias.alias)
        )
        for major_id, alias in alias_rows.all():
            ctx.aliases.setdefault(major_id, []).append(alias)

    return ctx


def to_major_out(major: Major, ctx: MajorContext) -> MajorOut:
    return MajorOut(
        slug=major.slug,
        name=major.name,
        code=major.code,
        taxonomy=ctx.taxonomy.get(major.code) if major.code is not None else None,
        aliases=ctx.aliases.get(major.id, []),
        standard_years=major.standard_years,
        requires_practice_license=major.requires_practice_license,
        practice_profession=major.practice_profession,
    )
