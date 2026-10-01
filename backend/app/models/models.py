from datetime import date, datetime
from sqlalchemy import Boolean, Date, DateTime, Float, ForeignKey, Integer, String, Text
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
    # 仅「确认入库」的运行为 True；试摆/预览不落运行行
    confirmed: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False, server_default="0")

class Stall(Base):
    """正式入库的占位行。除街段名、摊主号与名称、起止米、宽度外，必须钉
    所属柱间空档序号 gap_index 与起点相对该空档左禁入沿的距离
    offset_from_gap_left_m；派生列均 NOT NULL，数据库层也拒绝缺字段半截行。

    segment_name / vendor_name 为确认当时的名称快照：摊主改名后只影响之后的
    新确认运行，旧运行不回刷。
    """
    __tablename__ = "stalls"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    run_id: Mapped[int] = mapped_column(ForeignKey("allocation_runs.id"))
    segment_id: Mapped[int] = mapped_column(ForeignKey("segments.id"))
    segment_name: Mapped[str] = mapped_column(String(64))
    vendor_id: Mapped[int] = mapped_column(Integer, nullable=False)
    vendor_name: Mapped[str] = mapped_column(String(64))
    start_m: Mapped[float] = mapped_column(Float, nullable=False)
    end_m: Mapped[float] = mapped_column(Float, nullable=False)
    width_m: Mapped[float] = mapped_column(Float, nullable=False)
    gap_index: Mapped[int] = mapped_column(Integer, nullable=False)
    offset_from_gap_left_m: Mapped[float] = mapped_column(Float, nullable=False)
