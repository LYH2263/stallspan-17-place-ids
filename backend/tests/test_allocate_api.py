from sqlalchemy import func, select

from app.models.models import AllocationRun, PlacementRow
from tests.conftest import seed_market


def run_count(db):
    return db.scalar(select(func.count()).select_from(AllocationRun)) or 0


def row_count(db):
    return db.scalar(select(func.count()).select_from(PlacementRow)) or 0


def test_preview_zero_write(client, db_session):
    seed_market(db_session)
    r = client.post("/api/allocate/preview?segment_id=1")
    assert r.status_code == 200
    body = r.json()
    assert body["persisted"] is False and body["run_id"] is None
    assert len(body["placements"]) == 6  # 巨型舞台车放不下
    assert run_count(db_session) == 0 and row_count(db_session) == 0


def test_latest_is_read_only_empty_state(client, db_session):
    seed_market(db_session)
    r = client.get("/api/allocate/latest?segment_id=1")
    assert r.status_code == 200
    body = r.json()
    assert body["persisted"] is False and body["run_id"] is None
    assert body["placements"] == [] and body["rejected"] == []
    assert run_count(db_session) == 0 and row_count(db_session) == 0


def test_confirm_persists_rows_with_derived_fields(client, db_session):
    seed_market(db_session)
    r = client.post("/api/allocate/confirm?segment_id=1")
    assert r.status_code == 200
    body = r.json()
    assert body["persisted"] is True and body["run_id"]
    rows = db_session.scalars(select(PlacementRow)).all()
    assert len(rows) == len(body["placements"]) == 6
    # 灯柱A左侧空档（序号1，左禁入沿 0）三摊对账
    by_name = {p["vendor_name"]: p for p in body["placements"]}
    assert (by_name["阿强烧烤"]["span_index"], by_name["阿强烧烤"]["offset_from_span_left_m"]) == (1, 0.0)
    assert (by_name["林记糖水"]["span_index"], by_name["林记糖水"]["offset_from_span_left_m"]) == (1, 4.0)
    assert (by_name["小美饰品"]["span_index"], by_name["小美饰品"]["offset_from_span_left_m"]) == (1, 7.0)
    # 接口口径 == 库行口径（主图点开 / 运行抽屉同一份）
    row_by_vendor = {row.vendor_id: row for row in rows}
    for p in body["placements"]:
        dbrow = row_by_vendor[p["vendor_id"]]
        assert p["segment_name"] == dbrow.segment_name == "东街段"
        assert p["span_index"] == dbrow.span_index
        assert p["offset_from_span_left_m"] == dbrow.offset_from_span_left_m
        assert p["start_m"] == dbrow.start_m and p["end_m"] == dbrow.end_m
    # latest 回放同一运行，行数不再变
    lat = client.get("/api/allocate/latest?segment_id=1").json()
    assert lat["persisted"] is True and lat["run_id"] == body["run_id"]
    assert [p["vendor_id"] for p in lat["placements"]] == [p["vendor_id"] for p in body["placements"]]
    assert run_count(db_session) == 1


def test_rename_new_confirm_new_name_old_run_keeps_old(client, db_session):
    seed_market(db_session)
    first = client.post("/api/allocate/confirm?segment_id=1").json()
    vid = next(p["vendor_id"] for p in first["placements"] if p["vendor_name"] == "阿强烧烤")
    r = client.patch(f"/api/vendors/{vid}", json={"name": "阿强炭烤"})
    assert r.status_code == 200 and r.json()["name"] == "阿强炭烤"
    second = client.post("/api/allocate/confirm?segment_id=1").json()
    assert second["run_id"] != first["run_id"]
    names_new = {p["vendor_name"] for p in second["placements"]}
    assert "阿强炭烤" in names_new and "阿强烧烤" not in names_new
    # 旧运行旧名不回刷
    old = client.get(f"/api/allocate/runs/{first['run_id']}").json()
    names_old = {p["vendor_name"] for p in old["placements"]}
    assert "阿强烧烤" in names_old and "阿强炭烤" not in names_old


def test_missing_field_fails_whole_write(client, db_session, monkeypatch):
    seed_market(db_session)
    from app.api import allocate as alloc
    orig = alloc.build_placement_rows

    def broken(result, segment_name):
        rows = orig(result, segment_name)
        for row in rows:
            row["offset_from_span_left_m"] = None  # 模拟派生字段缺失
        return rows

    monkeypatch.setattr(alloc, "build_placement_rows", broken)
    r = client.post("/api/allocate/confirm?segment_id=1")
    assert r.status_code == 422
    detail = r.json()["detail"]
    assert "校验失败" in detail
    assert "无连续空档" not in detail  # 不得冒充空隙不足
    assert run_count(db_session) == 0 and row_count(db_session) == 0
    lat = client.get("/api/allocate/latest?segment_id=1").json()
    assert lat["persisted"] is False  # 没留下半截运行


def test_out_of_range_span_index_fails_whole_write(client, db_session, monkeypatch):
    seed_market(db_session)
    from app.api import allocate as alloc
    orig = alloc.build_placement_rows

    def broken(result, segment_name):
        rows = orig(result, segment_name)
        rows[0]["span_index"] = 99  # 序号越界
        return rows

    monkeypatch.setattr(alloc, "build_placement_rows", broken)
    r = client.post("/api/allocate/confirm?segment_id=1")
    assert r.status_code == 422
    assert "越界" in r.json()["detail"]
    assert run_count(db_session) == 0 and row_count(db_session) == 0


def test_runs_listing_only_persisted(client, db_session):
    seed_market(db_session)
    client.post("/api/allocate/preview?segment_id=1")  # 预览不进目录
    assert client.get("/api/allocate/runs?segment_id=1").json() == []
    client.post("/api/allocate/confirm?segment_id=1")
    client.post("/api/allocate/confirm?segment_id=1")
    runs = client.get("/api/allocate/runs?segment_id=1").json()
    assert len(runs) == 2
    assert runs[0]["id"] > runs[1]["id"]  # 新的在前
    assert all(r["placement_count"] == 6 and r["segment_name"] == "东街段" for r in runs)
