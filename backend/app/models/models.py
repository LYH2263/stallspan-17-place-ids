from datetime import date, datetime
from sqlalchemy import Date, DateTime, Float, ForeignKey, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column
from app.database import Base

class MarketDay(Base):
    __tablename__ = "market_days"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    name: Mapped[str] = mapped_column(String(64))
    day: Mapped[date] = mapped_column(Date)

class Segment(Base):
    __tablename__ = "segments"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    market_day_id: Mapped[int] = mapped_column(ForeignKey("market_days.id"))
    name: Mapped[str] = mapped_column(String(64))
    width_m: Mapped[float] = mapped_column(Float)

class Vendor(Base):
    __tablename__ = "vendors"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    market_day_id: Mapped[int] = mapped_column(ForeignKey("market_days.id"))
    name: Mapped[str] = mapped_column(String(64))
    stall_width_m: Mapped[float] = mapped_column(Float)
    priority: Mapped[int] = mapped_column(Integer, default=1)

class Pillar(Base):
    __tablename__ = "pillars"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    segment_id: Mapped[int] = mapped_column(ForeignKey("segments.id"))
    position_m: Mapped[float] = mapped_column(Float)
    thickness_m: Mapped[float] = mapped_column(Float, default=0.4)
    label: Mapped[str] = mapped_column(String(32), default="挡柱")

class AllocationRun(Base):
    __tablename__ = "allocation_runs"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    segment_id: Mapped[int] = mapped_column(ForeignKey("segments.id"))
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    result_json: Mapped[str] = mapped_column(Text, default="{}")

class PlacementRow(Base):
    """正式入库的占位行：除街段/摊主/起止/宽度外，钉死所属空档序号与距左禁入沿米数。"""
    __tablename__ = "placement_rows"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    run_id: Mapped[int] = mapped_column(ForeignKey("allocation_runs.id"))
    segment_id: Mapped[int] = mapped_column(ForeignKey("segments.id"))
    segment_name: Mapped[str] = mapped_column(String(64))
    vendor_id: Mapped[int] = mapped_column(Integer)
    vendor_name: Mapped[str] = mapped_column(String(64))
    start_m: Mapped[float] = mapped_column(Float)
    end_m: Mapped[float] = mapped_column(Float)
    width_m: Mapped[float] = mapped_column(Float)
    span_index: Mapped[int] = mapped_column(Integer)              # 所属柱间空档序号（1 起）
    span_left_m: Mapped[float] = mapped_column(Float)             # 空档左禁入沿（米）
    span_right_m: Mapped[float] = mapped_column(Float)            # 空档右禁入沿（米）
    offset_from_span_left_m: Mapped[float] = mapped_column(Float) # 起点距左禁入沿（米）
