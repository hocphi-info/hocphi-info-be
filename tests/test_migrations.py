"""Alembic round-trip: upgrade head -> downgrade base -> upgrade head khong loi.

Khong dung fixture `_schema`/`engine`/`db` cua conftest — tu goi `command.upgrade`/
`command.downgrade` truc tiep de kiem chinh migration 0001, doc lap voi cac test
khac. Chay xong luon dung o "head" nen khong pha trang thai cac test con lai
(fixture `_schema` goi `upgrade head` lai sau do la no-op).
"""

from alembic import command

from tests.conftest import _alembic_config


def test_upgrade_downgrade_upgrade_roundtrip() -> None:
    cfg = _alembic_config()
    command.upgrade(cfg, "head")
    command.downgrade(cfg, "base")
    command.upgrade(cfg, "head")
