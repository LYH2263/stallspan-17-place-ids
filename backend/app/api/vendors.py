from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.orm import Session
from app.database import get_db
from app.models.models import Vendor

router = APIRouter(prefix="/vendors", tags=["vendors"])


class VendorRename(BaseModel):
    name: str


@router.get("")
def list_vendors(db: Session = Depends(get_db)):
    return [{"id": r.id, "market_day_id": r.market_day_id, "name": r.name,
             "stall_width_m": r.stall_width_m, "priority": r.priority}
            for r in db.scalars(select(Vendor).order_by(Vendor.priority, Vendor.id)).all()]


@router.patch("/{vendor_id}")
def rename_vendor(vendor_id: int, payload: VendorRename, db: Session = Depends(get_db)):
    """改名只影响之后的确认；已入库运行里是当时的名字快照，不回刷。"""
    v = db.get(Vendor, vendor_id)
    if not v:
        raise HTTPException(404, "摊主不存在")
    name = payload.name.strip()
    if not name:
        raise HTTPException(422, "名称不能为空")
    v.name = name
    db.commit()
    return {"id": v.id, "market_day_id": v.market_day_id, "name": v.name,
            "stall_width_m": v.stall_width_m, "priority": v.priority}
