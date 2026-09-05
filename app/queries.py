"""Query helper dung chung nhieu router (majors/program_detail) — rut ra tu
`app/majors.py` de tranh 2 ban subquery y het lech nhau ve sau (Tuan 3).
"""

from sqlalchemy import select
from sqlalchemy.sql.selectable import Subquery

from app.models import TuitionRecord


def latest_published_tuition_subquery() -> Subquery:
    """1 dong / program: ban ghi CONG BO (is_projected=false) moi nhat theo
    nam hoc — cung logic voi CTE `latest` trong VIEW school_track_stats
    (alembic/versions/0001, schema.md §4), viet lai bang ORM de join truc tiep
    voi Program/School/Major thay vi doc qua VIEW (VIEW gom theo truong, khong
    giu tung program rieng le nhu S1/S3 can)."""
    return (
        select(TuitionRecord)
        .where(
            TuitionRecord.deleted_at.is_(None),
            TuitionRecord.is_projected.is_(False),
        )
        .distinct(TuitionRecord.program_id)
        .order_by(TuitionRecord.program_id, TuitionRecord.academic_year_start.desc())
        .subquery()
    )
