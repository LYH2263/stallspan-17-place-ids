import json
from datetime import datetime
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import func, select
from sqlalchemy.orm import Session
from app.database import get_db
from app.models.models import AllocationRun, Pillar, PlacementRow, Segment, Vendor
from app.services.first_fit_engine import allocate_first_fit, free_spans_from_pillars, result_to_dict
from app.services.placement_rows import (
    PlacementValidationError,
    build_placement_rows,
    placement_row_to_dict,
    validate_placement_rows,
)

router = APIRouter(prefix="/allocate", tags=["allocate"])


def _compute(segment_id: int, db: Session):
    """只读计算：切空 + First-Fit，不落库。预览与确认共用同一口径。"""
    seg = db.get(Segment, segment_id)
    if not seg:
        raise HTTPException(404, "街段不存在")
    pillars = [{"position_m": p.position_m, "thickness_m": p.thickness_m, "label": p.label}
               for p in db.scalars(select(Pillar).where(Pillar.segment_id == segment_id)
                                   .order_by(Pillar.position_m)).all()]
    vendors = [{"id": v.id, "name": v.name, "stall_width_m": v.stall_width_m, "priority": v.priority}
               for v in db.scalars(select(Vendor).where(Vendor.market_day_id == seg.market_day_id)).all()]
    result = result_to_dict(allocate_first_fit(seg.width_m, vendors, pillars))
    result["segment"] = {"id": seg.id, "name": seg.name, "width_m": seg.width_m}
    result["pillars"] = pillars
    return seg, result


def _run_payload(run: AllocationRun, db: Session) -> dict:
    """已入库运行的接口口径：占位行只从库行出，主图点开与运行抽屉同一份。"""
    snap = json.loads(run.result_json)
    rows = db.scalars(select(PlacementRow).where(PlacementRow.run_id == run.id)
                      .order_by(PlacementRow.start_m, PlacementRow.id)).all()
    return {
        "persisted": True,
        "run_id": run.id,
        "created_at": run.created_at.isoformat(),
        **snap,
        "placements": [placement_row_to_dict(r) for r in rows],
    }


@router.post("/preview")
def preview(segment_id: int = 1, db: Session = Depends(get_db)):
    """试摆预览：只算不写，run_id 为空，绝不冒充已入库。"""
    _, result = _compute(segment_id, db)
    return {"persisted": False, "run_id": None, "created_at": None, **result}


@router.post("/confirm")
def confirm(segment_id: int = 1, db: Session = Depends(get_db)):
    """确认入库：派生字段先与切空结果对账，不符即整次失败、行数不增。"""
    seg, result = _compute(segment_id, db)
    rows = build_placement_rows(result, seg.name)
    try:
        validate_placement_rows(rows, result["gaps"])
    except PlacementValidationError as e:
        db.rollback()
        # 派生字段口径错误，不是空隙不足；不得写成空档不够的文案
        raise HTTPException(422, f"占位行派生字段校验失败：{e}")
    snapshot = {k: result[k] for k in ("segment", "pillars", "gaps", "rejected", "free_spans")}
    run = AllocationRun(segment_id=seg.id, created_at=datetime.utcnow(),
                        result_json=json.dumps(snapshot, ensure_ascii=False))
    db.add(run)
    db.flush()
    for r in rows:
        db.add(PlacementRow(run_id=run.id, segment_id=seg.id, **r))
    db.commit()
    db.refresh(run)
    return _run_payload(run, db)


@router.get("/latest")
def latest(segment_id: int = 1, db: Session = Depends(get_db)):
    """最近一次已入库运行；没有就是空态。只读，绝不顺手写运行。"""
    run = db.scalars(select(AllocationRun).where(AllocationRun.segment_id == segment_id)
                     .order_by(AllocationRun.id.desc())).first()
    if run:
        return _run_payload(run, db)
    seg = db.get(Segment, segment_id)
    if not seg:
        raise HTTPException(404, "街段不存在")
    pillars = [{"position_m": p.position_m, "thickness_m": p.thickness_m, "label": p.label}
               for p in db.scalars(select(Pillar).where(Pillar.segment_id == segment_id)
                                   .order_by(Pillar.position_m)).all()]
    gaps = free_spans_from_pillars(seg.width_m, pillars)
    return {
        "persisted": False,
        "run_id": None,
        "created_at": None,
        "segment": {"id": seg.id, "name": seg.name, "width_m": seg.width_m},
        "pillars": pillars,
        "gaps": [{"index": i + 1, "start_m": a, "end_m": b} for i, (a, b) in enumerate(gaps)],
        "placements": [],
        "rejected": [],
        "free_spans": [{"start_m": a, "end_m": b} for a, b in gaps],
    }


@router.get("/runs")
def list_runs(segment_id: int = 1, db: Session = Depends(get_db)):
    """运行抽屉的目录：只列已入库运行，预览永远进不来。"""
    runs = db.scalars(select(AllocationRun).where(AllocationRun.segment_id == segment_id)
                      .order_by(AllocationRun.id.desc())).all()
    counts = dict(db.execute(
        select(PlacementRow.run_id, func.count()).group_by(PlacementRow.run_id)).all())
    out = []
    for run in runs:
        snap = json.loads(run.result_json)
        out.append({
            "id": run.id,
            "segment_id": run.segment_id,
            "segment_name": (snap.get("segment") or {}).get("name"),
            "created_at": run.created_at.isoformat(),
            "placement_count": int(counts.get(run.id, 0)),
        })
    return out


@router.get("/runs/{run_id}")
def get_run(run_id: int, db: Session = Depends(get_db)):
    run = db.get(AllocationRun, run_id)
    if not run:
        raise HTTPException(404, "运行不存在")
    return _run_payload(run, db)
