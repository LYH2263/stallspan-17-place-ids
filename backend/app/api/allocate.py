import json
from datetime import datetime
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.orm import Session
from app.database import get_db
from app.models.models import AllocationRun, Pillar, Segment, Stall, Vendor
from app.services.first_fit_engine import allocate_first_fit, result_to_dict, validate_placements
router = APIRouter(prefix="/allocate", tags=["allocate"])


def _compute(segment_id: int, db: Session) -> tuple[Segment, list[dict], dict]:
    """读取当前街段/挡柱/摊主并试摆，全程只读。"""
    seg = db.get(Segment, segment_id)
    if not seg:
        raise HTTPException(404, "街段不存在")
    pillars = [{"position_m": p.position_m, "thickness_m": p.thickness_m}
               for p in db.scalars(select(Pillar).where(Pillar.segment_id == segment_id)).all()]
    vendors = [{"id": v.id, "name": v.name, "stall_width_m": v.stall_width_m, "priority": v.priority}
               for v in db.scalars(select(Vendor).where(Vendor.market_day_id == seg.market_day_id)).all()]
    result = result_to_dict(allocate_first_fit(seg.width_m, vendors, pillars))
    result["segment"] = {"id": seg.id, "name": seg.name, "width_m": seg.width_m}
    result["pillars"] = pillars
    return seg, pillars, result


@router.post("/preview")
def preview(segment_id: int = 1, db: Session = Depends(get_db)):
    """试摆/预览：零写库。返回结果带 confirmed=False，绝不冒充已入库。"""
    _, _, result = _compute(segment_id, db)
    return {"id": None, "confirmed": False, **result}


@router.post("/confirm")
def confirm(segment_id: int = 1, db: Session = Depends(get_db)):
    """确认入库：对账通过后单事务写一条运行 + 全部占位行。

    - 派生字段（空档序号/距左禁入沿）缺失、序号越界、距柱与起止对不上 →
      整次写入失败、回滚、行数不增（422，错误类型 placement_consistency_error），
      不允许留下缺字段半截行，也不得把这类失败冒充成「空隙不足」。
    - 有空档不足的摊主只会出现在 rejected 里，不阻断其余摊位入库。
    - 摊主名称在确认瞬间快照进库行；摊主之后改名不回刷旧运行。
    """
    seg, _, result = _compute(segment_id, db)
    errors = validate_placements(result["placements"], result["gaps"])
    if errors:
        # 一致性错误：先于任何写入，天然零增行；明确区别于「空隙不足」。
        raise HTTPException(422, {
            "error": "placement_consistency_error",
            "message": "落点派生字段对账失败，整次写入作废，未写入任何行",
            "details": errors,
        })
    run = AllocationRun(segment_id=segment_id, created_at=datetime.utcnow(),
                        result_json=json.dumps({**result, "confirmed": True}, ensure_ascii=False),
                        confirmed=True)
    db.add(run)
    db.flush()  # 取 run.id；此时尚未 commit，出错仍可整体回滚
    stalls = [
        Stall(
            run_id=run.id, segment_id=seg.id, segment_name=seg.name,
            vendor_id=p["vendor_id"], vendor_name=p["vendor_name"],
            start_m=p["start_m"], end_m=p["end_m"], width_m=p["width_m"],
            gap_index=p["gap_index"], offset_from_gap_left_m=p["offset_from_gap_left_m"],
        )
        for p in result["placements"]
    ]
    if len(stalls) != len(result["placements"]):
        db.rollback()
        raise HTTPException(500, {"error": "placement_consistency_error",
                                  "message": "入库行数与试摆落点不符，整次写入作废"})
    db.add_all(stalls)
    try:
        db.commit()
    except Exception:
        db.rollback()
        raise HTTPException(500, {"error": "placement_consistency_error",
                                  "message": "入库提交失败已回滚，行数不增"})
    db.refresh(run)
    return {"id": run.id, "confirmed": True, **result}


def _stall_dict(s: Stall) -> dict:
    """正式入库行口径，字段与切空结果/主图点开信息一致。"""
    return {
        "vendor_id": s.vendor_id,
        "vendor_name": s.vendor_name,
        "start_m": s.start_m,
        "end_m": s.end_m,
        "width_m": s.width_m,
        "gap_index": s.gap_index,
        "offset_from_gap_left_m": s.offset_from_gap_left_m,
        "segment_name": s.segment_name,
    }


@router.get("/runs")
def list_runs(segment_id: int = 1, db: Session = Depends(get_db)):
    """运行抽屉：仅列已确认入库的运行（试摆不留运行）。"""
    runs = db.scalars(
        select(AllocationRun)
        .where(AllocationRun.segment_id == segment_id, AllocationRun.confirmed.is_(True))
        .order_by(AllocationRun.id.desc())
    ).all()
    out = []
    for r in runs:
        data = json.loads(r.result_json)
        out.append({
            "id": r.id,
            "created_at": r.created_at.isoformat(),
            "segment": data.get("segment"),
            "placement_count": len(data.get("placements", [])),
            "rejected_count": len(data.get("rejected", [])),
        })
    return out


@router.get("/runs/{run_id}")
def get_run(run_id: int, db: Session = Depends(get_db)):
    """运行抽屉展开：库行（权威）+ 当时切空/拒入结果，名称为确认时快照。"""
    run = db.get(AllocationRun, run_id)
    if not run or not run.confirmed:
        raise HTTPException(404, "已入库运行不存在")
    data = json.loads(run.result_json)
    stalls = [_stall_dict(s) for s in db.scalars(
        select(Stall).where(Stall.run_id == run_id).order_by(Stall.gap_index, Stall.start_m)).all()]
    return {"id": run.id, "confirmed": True, "created_at": run.created_at.isoformat(), **data,
            "stalls": stalls}


@router.get("/latest")
def latest(segment_id: int = 1, db: Session = Depends(get_db)):
    """最近一次「已确认」运行；从未确认过时返回只读试摆结果（零写，不冒充入库）。"""
    run = db.scalars(select(AllocationRun).where(AllocationRun.segment_id == segment_id)
                     .order_by(AllocationRun.id.desc())).first()
    if not run:
        _, _, result = _compute(segment_id, db)
        return {"id": None, "confirmed": False, **result}
    data = json.loads(run.result_json)
    return {"id": run.id, "confirmed": bool(run.confirmed), **data}
