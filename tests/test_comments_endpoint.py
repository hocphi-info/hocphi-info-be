"""Binh luan an danh — goi that qua ASGI + DB test (khong mock DB).

IP gia lap bang header `Fly-Client-IP` (giong production sau proxy Fly). Moi test
dung IP rieng khi can tranh gioi han 5 binh luan / 10 phut / IP.
"""

from collections.abc import AsyncGenerator
from datetime import UTC, datetime, timedelta
from typing import Any

import pytest
import pytest_asyncio
from app import comments_guard as guard
from app.db import SessionLocal
from app.main import app
from app.models import Comment
from httpx import ASGITransport, AsyncClient, Response
from sqlalchemy import update
from sqlalchemy.ext.asyncio import AsyncSession

from tests.factories import seed_minimal

THREAD = "bai-viet/hoc-phi-cntt"


@pytest_asyncio.fixture
async def client(db: AsyncSession) -> AsyncGenerator[AsyncClient, None]:
    # `db` chi de TRUNCATE sach bang truoc moi test (xem conftest.py).
    async with AsyncClient(
        transport=ASGITransport(app=app), base_url="http://test"
    ) as c:
        yield c


async def _post(
    client: AsyncClient,
    body: str = "Học phí năm nay có tăng không ạ?",
    *,
    ip: str = "10.0.0.1",
    thread: str = THREAD,
    **extra: Any,
) -> Response:
    return await client.post(
        "/api/v1/comments",
        json={"threadKey": thread, "body": body, **extra},
        headers={"Fly-Client-IP": ip},
    )


async def _list(client: AsyncClient, **params: Any) -> dict[str, Any]:
    resp = await client.get("/api/v1/comments", params={"thread": THREAD, **params})
    assert resp.status_code == 200, resp.text
    data: dict[str, Any] = resp.json()
    return data


async def test_create_and_list_nested_thread(client: AsyncClient) -> None:
    a = (await _post(client, "Gốc", ip="1.1.1.1", authorName=" Phương  Linh ")).json()
    assert a["comment"]["authorName"] == "Phương Linh"
    assert a["deleteToken"]
    parent = a["comment"]["id"]
    ids = [parent]
    # Chuoi 5 cap: 1.1.1.1 va 2.2.2.2 tra loi xen ke.
    for depth in range(1, 5):
        ip = "2.2.2.2" if depth % 2 else "1.1.1.1"
        r = await _post(client, f"Trả lời cấp {depth}", ip=ip, parentId=parent)
        assert r.status_code == 201, r.text
        c = r.json()["comment"]
        assert (c["depth"], c["parentId"], c["rootId"]) == (depth, parent, ids[0])
        parent = c["id"]
        ids.append(parent)

    data = await _list(client)
    assert data["total"] == 5
    assert data["nextOffset"] is None
    got = data["comments"]
    assert [c["id"] for c in got] == ids
    assert got[1]["authorName"] is None  # "An danh"
    # Cung IP + cung chuoi -> cung tag; khac IP -> khac tag.
    assert got[0]["authorTag"] == got[2]["authorTag"] == got[4]["authorTag"]
    assert got[1]["authorTag"] != got[0]["authorTag"]
    assert all(c["isHidden"] is False for c in got)


async def test_sort_and_paging(client: AsyncClient) -> None:
    for i in range(22):
        r = await _post(client, f"Bình luận số {i}", ip=f"10.1.{i}.1")
        assert r.status_code == 201

    newest = await _list(client)
    assert len(newest["comments"]) == 20
    assert newest["comments"][0]["body"] == "Bình luận số 21"
    assert newest["nextOffset"] == 20
    page2 = await _list(client, offset=20)
    assert [c["body"] for c in page2["comments"]] == [
        "Bình luận số 1",
        "Bình luận số 0",
    ]
    assert page2["nextOffset"] is None

    oldest = await _list(client, sort="oldest")
    assert oldest["comments"][0]["body"] == "Bình luận số 0"
    assert oldest["total"] == 22


@pytest.mark.parametrize(
    ("body", "code"),
    [
        ("ok", "too_short"),
        ("Xem ở abc.xyz nhé", "contains_link"),
        ("Gọi 0912 345 678", "contains_phone"),
    ],
)
async def test_rejects_bad_content(client: AsyncClient, body: str, code: str) -> None:
    r = await _post(client, body)
    assert r.status_code == 422
    assert r.json()["detail"]["code"] == code


async def test_thread_validation(client: AsyncClient) -> None:
    await seed_minimal(with_taxonomy=False)

    bad = await _post(client, thread="so-sanh")
    assert (bad.status_code, bad.json()["detail"]["code"]) == (422, "invalid_thread")
    bad_get = await client.get("/api/v1/comments", params={"thread": "../x"})
    assert bad_get.status_code == 422

    missing = await _post(client, thread="truong/khong-co")
    assert (missing.status_code, missing.json()["detail"]["code"]) == (
        404,
        "thread_not_found",
    )
    no_program = await _post(client, thread="nganh/truong-b/digital-art")
    assert no_program.status_code == 404

    assert (await _post(client, thread="truong/truong-a")).status_code == 201
    assert (
        await _post(client, thread="nganh/truong-a/khoa-hoc-may-tinh")
    ).status_code == 201
    assert (await _post(client, thread="nganh")).status_code == 201


async def test_parent_must_be_in_same_thread(client: AsyncClient) -> None:
    other = (await _post(client, thread="bai-viet")).json()["comment"]["id"]
    r = await _post(client, parentId=other)
    assert (r.status_code, r.json()["detail"]["code"]) == (404, "parent_not_found")
    r = await _post(client, parentId="01NOTEXIST")
    assert r.status_code == 404


async def test_rate_limit_per_ip(client: AsyncClient) -> None:
    for _ in range(5):
        assert (await _post(client, ip="9.9.9.9")).status_code == 201
    r = await _post(client, ip="9.9.9.9")
    assert r.status_code == 429
    assert r.json()["detail"]["code"] == "rate_limited"
    assert 0 < int(r.headers["Retry-After"]) <= 600
    # IP khac khong bi anh huong.
    assert (await _post(client, ip="9.9.9.10")).status_code == 201


async def test_turnstile_failure_rejects(
    client: AsyncClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    async def deny(token: str | None, ip: str) -> bool:
        return False

    monkeypatch.setattr(guard, "verify_turnstile", deny)
    r = await _post(client, turnstileToken="bad")
    assert (r.status_code, r.json()["detail"]["code"]) == (400, "turnstile_failed")
    assert (await _list(client))["total"] == 0


async def test_self_delete(client: AsyncClient) -> None:
    created = (await _post(client)).json()
    cid, token = created["comment"]["id"], created["deleteToken"]

    wrong = await client.delete(
        f"/api/v1/comments/{cid}", headers={"X-Delete-Token": "sai"}
    )
    assert (wrong.status_code, wrong.json()["detail"]["code"]) == (
        403,
        "invalid_token",
    )
    ok = await client.delete(
        f"/api/v1/comments/{cid}", headers={"X-Delete-Token": token}
    )
    assert ok.status_code == 204
    assert (await _list(client))["comments"] == []
    again = await client.delete(
        f"/api/v1/comments/{cid}", headers={"X-Delete-Token": token}
    )
    assert again.status_code == 404


async def test_self_delete_window_expires(client: AsyncClient) -> None:
    created = (await _post(client)).json()
    cid = created["comment"]["id"]
    async with SessionLocal() as s:
        await s.execute(
            update(Comment)
            .where(Comment.id == cid)
            .values(created_at=datetime.now(UTC) - timedelta(minutes=16))
        )
        await s.commit()
    r = await client.delete(
        f"/api/v1/comments/{cid}", headers={"X-Delete-Token": created["deleteToken"]}
    )
    assert (r.status_code, r.json()["detail"]["code"]) == (
        409,
        "delete_window_expired",
    )


async def _report(client: AsyncClient, cid: str, ip: str) -> Response:
    return await client.post(
        f"/api/v1/comments/{cid}/reports",
        json={"reason": "spam"},
        headers={"Fly-Client-IP": ip},
    )


async def test_reports_auto_hide_keeps_placeholder(client: AsyncClient) -> None:
    root = (await _post(client, "Gốc bị báo cáo", ip="3.3.3.3")).json()["comment"]
    reply = (await _post(client, "Trả lời", ip="4.4.4.4", parentId=root["id"])).json()

    # Cung IP bao 2 lan chi tinh 1.
    assert (await _report(client, root["id"], "5.0.0.1")).json() == {"hidden": False}
    assert (await _report(client, root["id"], "5.0.0.1")).json() == {"hidden": False}
    assert (await _report(client, root["id"], "5.0.0.2")).json() == {"hidden": False}
    assert (await _report(client, root["id"], "5.0.0.3")).json() == {"hidden": True}

    data = await _list(client)
    assert data["total"] == 1
    placeholder, kept = data["comments"]
    assert placeholder["id"] == root["id"]
    assert placeholder["isHidden"] is True
    assert placeholder["body"] is None and placeholder["authorTag"] is None
    assert kept["id"] == reply["comment"]["id"]

    # Da an thi khong bao cao / tra loi tiep duoc.
    assert (await _report(client, root["id"], "5.0.0.4")).status_code == 404
    r = await _post(client, ip="6.6.6.6", parentId=root["id"])
    assert r.status_code == 404


async def test_hidden_leaves_are_pruned(client: AsyncClient) -> None:
    root = (await _post(client, "Gốc", ip="7.7.7.1")).json()["comment"]
    reply = (await _post(client, "Con", ip="7.7.7.2", parentId=root["id"])).json()
    lone = (await _post(client, "Lẻ loi", ip="7.7.7.3")).json()["comment"]
    async with SessionLocal() as s:
        await s.execute(
            update(Comment)
            .where(Comment.id.in_([root["id"], reply["comment"]["id"], lone["id"]]))
            .values(hidden_at=datetime.now(UTC), hidden_reason="owner")
        )
        await s.commit()
    data = await _list(client)
    assert data == {**data, "total": 0, "comments": []}


async def test_report_unknown_comment_404(client: AsyncClient) -> None:
    assert (await _report(client, "01NOTEXIST", "8.8.8.8")).status_code == 404
