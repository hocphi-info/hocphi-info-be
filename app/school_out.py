"""Dung `SchoolOut` tu model `School` — 1 cho duy nhat cho ca 4 router.

Truoc day moi router liet ke tay tung field (`slug=..., name=..., logo_url=...`);
them field moi (vd `tuition_disclosure`) la phai sua dung ca 4 cho. Giong
`app/taxonomy.py::to_major_out`.
"""

from app.enums import CityCode
from app.models import School
from app.schemas.common import SchoolOut, TuitionDisclosureOut


def to_tuition_disclosure_out(school: School) -> TuitionDisclosureOut | None:
    # CHECK ck_schools_disclosure_evidence dam bao co muc => co ngay + bang chung;
    # kiem lai o day de mypy thu hep kieu (date | None -> date).
    if (
        school.tuition_disclosure is None
        or school.tuition_disclosure_checked_on is None
        or school.tuition_disclosure_evidence_url is None
    ):
        return None
    return TuitionDisclosureOut(
        level=school.tuition_disclosure,
        checked_on=school.tuition_disclosure_checked_on,
        evidence_url=school.tuition_disclosure_evidence_url,
        note=school.tuition_disclosure_note,
    )


def to_school_out(school: School) -> SchoolOut:
    return SchoolOut(
        slug=school.slug,
        name=school.name,
        short_name=school.short_name,
        city_code=CityCode(school.city_code),
        category=school.category,
        logo_url=school.logo_url,
        tuition_disclosure=to_tuition_disclosure_out(school),
    )
