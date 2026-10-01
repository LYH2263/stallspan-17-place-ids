from sqlalchemy import func, select

from app.models.models import AllocationRun, Stall, Vendor


def test_preview_writes_nothing(client):
    before_runs = client  # noqa: F841 (client fixture handles setup)
    r = client.post("/api/allocate/preview?segment_id=1")
    assert r.status_code == 200
    body = r.json()
    assert body["confirmed"] is False and body["id"] is None
    # 试摆零写：无运行、无库行
    from app.database import SessionLocal
    with SessionLocal() as s:
        assert s.scalar(select(func.count()).select_from(AllocationRun)) == 0
        assert s.scalar(select(func.count()).select_from(Stall)) == 0


def test_confirm_persists_run_and_stalls_with_gap_fields(client):
    r = client.post("/api/allocate/confirm?segment_id=1")
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["confirmed"] is True and body["id"] == 1
    from app.database import SessionLocal
    with SessionLocal() as s:
        assert s.scalar(select(func.count()).select_from(AllocationRun)) == 1
        stalls = s.scalars(select(Stall).order_by(Stall.gap_index, Stall.start_m)).all()
        assert len(stalls) == len(body["placements"]) == 6
        for st in stalls:
            assert st.gap_index is not None
            assert st.offset_from_gap_left_m is not None
            assert abs((st.end_m - st.start_m) - st.width_m) < 1e-9
        # 灯柱A左侧空档 #1 内三个摊：距柱 0 / 4 / 7
        gap1 = [st for st in stalls if st.gap_index == 1]
        assert sorted(st.offset_from_gap_left_m for st in gap1) == [0.0, 4.0, 7.0]
        assert all(st.segment_name == "东街段" for st in stalls)


def test_confirm_then_runs_drawer_and_run_detail_agree(client):
    c = client.post("/api/allocate/confirm?segment_id=1").json()
    runs = client.get("/api/allocate/runs?segment_id=1").json()
    assert len(runs) == 1 and runs[0]["id"] == c["id"] and runs[0]["placement_count"] == 6
    detail = client.get(f"/api/allocate/runs/{c['id']}").json()
    # 运行抽屉库行 与 切空结果 同口径
    pl = {p["vendor_id"]: p for p in c["placements"]}
    assert len(detail["stalls"]) == 6
    for st in detail["stalls"]:
        p = pl[st["vendor_id"]]
        assert st["start_m"] == p["start_m"] and st["end_m"] == p["end_m"]
        assert st["width_m"] == p["width_m"]
        assert st["gap_index"] == p["gap_index"]
        assert st["offset_from_gap_left_m"] == p["offset_from_gap_left_m"]
        assert st["vendor_name"] == p["vendor_name"]
    # 主图点开信息与库行同口径：缺口字段在任一来源都不允许为 None
    for p in c["placements"]:
        assert p["gap_index"] is not None and p["offset_from_gap_left_m"] is not None


def test_latest_without_confirmation_is_readonly_preview(client):
    r = client.get("/api/allocate/latest?segment_id=1")
    assert r.status_code == 200
    body = r.json()
    assert body["confirmed"] is False and body["id"] is None
    from app.database import SessionLocal
    with SessionLocal() as s:
        assert s.scalar(select(func.count()).select_from(AllocationRun)) == 0


def test_consistency_failure_is_atomic_and_not_gap_shortage(client, monkeypatch):
    """破坏引擎产出（抹掉派生字段）后确认：整次写入失败、行数不增，且错误是
    placement_consistency_error 而非空隙不足。"""
    from app.api import allocate as alloc_api
    from app.services import first_fit_engine as engine

    orig = engine.result_to_dict

    def sabotaged(result):
        d = orig(result)
        for p in d["placements"]:
            p["gap_index"] = None
            p["offset_from_gap_left_m"] = None
        return d

    monkeypatch.setattr(alloc_api, "result_to_dict", sabotaged)
    r = client.post("/api/allocate/confirm?segment_id=1")
    assert r.status_code == 422
    err = r.json()["detail"]
    assert err["error"] == "placement_consistency_error"
    assert any("缺字段" in x for x in err["details"])
    # 不得冒充空隙不足
    assert all("空隙" not in x for x in err["details"])
    from app.database import SessionLocal
    with SessionLocal() as s:
        assert s.scalar(select(func.count()).select_from(AllocationRun)) == 0
        assert s.scalar(select(func.count()).select_from(Stall)) == 0
    # 失败后再正常确认仍可成功（证明未留半截状态）
    monkeypatch.undo()
    r2 = client.post("/api/allocate/confirm?segment_id=1")
    assert r2.status_code == 200 and r2.json()["confirmed"] is True
    with SessionLocal() as s:
        assert s.scalar(select(func.count()).select_from(Stall)) == 6


def test_gap_shortage_does_not_block_confirm(client):
    """巨型舞台车 12m 任何空档都放不下（空隙不足）→ rejected，其余 6 行正常入库。"""
    body = client.post("/api/allocate/confirm?segment_id=1").json()
    assert [x["vendor_name"] for x in body["rejected"]] == ["巨型舞台车"]
    assert len(body["placements"]) == 6


def test_rename_followed_by_new_confirm_keeps_old_run_snapshot(client):
    c1 = client.post("/api/allocate/confirm?segment_id=1").json()
    vid = c1["placements"][0]["vendor_id"]
    old_name = c1["placements"][0]["vendor_name"]

    r = client.patch(f"/api/vendors/{vid}", json={"name": "阿强改名版"})
    assert r.status_code == 200 and r.json()["name"] == "阿强改名版"

    c2 = client.post("/api/allocate/confirm?segment_id=1").json()
    assert c2["id"] != c1["id"]
    # 旧运行旧名不回刷
    old = client.get(f"/api/allocate/runs/{c1['id']}").json()
    old_stall = next(s for s in old["stalls"] if s["vendor_id"] == vid)
    assert old_stall["vendor_name"] == old_name
    # 新确认跟新名
    new_stall = next(s for s in c2["placements"] if s["vendor_id"] == vid)
    assert new_stall["vendor_name"] == "阿强改名版"
    new_detail = client.get(f"/api/allocate/runs/{c2['id']}").json()
    assert next(s for s in new_detail["stalls"] if s["vendor_id"] == vid)["vendor_name"] == "阿强改名版"
    # 名册当前名也是新名
    with __import__("app.database", fromlist=["SessionLocal"]).SessionLocal() as s:
        assert s.get(Vendor, vid).name == "阿强改名版"
