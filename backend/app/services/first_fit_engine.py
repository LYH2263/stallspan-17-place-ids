"""1D First-Fit stall placement along a street segment; stalls cannot cross pillars.

每个占位除起止米外，还钉住所属柱间空档（gaps，1 起序号）与
起点相对该空档左禁入沿的距离米，供入库行 / 主图点开 / 运行抽屉同一口径对账。
"""
from __future__ import annotations
from dataclasses import asdict, dataclass

@dataclass
class Placement:
    vendor_id: int
    vendor_name: str
    start_m: float
    end_m: float
    width_m: float
    span_index: int               # 所属柱间空档序号（1 起，对应 gaps 列表）
    span_left_m: float            # 该空档左禁入沿（米）
    span_right_m: float           # 该空档右禁入沿（米）
    offset_from_span_left_m: float  # 起点相对左禁入沿的距离（米）

@dataclass
class Rejected:
    vendor_id: int
    vendor_name: str
    width_m: float
    reason: str

@dataclass
class AllocResult:
    placements: list[Placement]
    rejected: list[Rejected]
    free_spans: list[tuple[float, float]]   # 分配后剩余空档
    gaps: list[tuple[float, float]]         # 当时切空结果（柱间空档，序号基准）

def free_spans_from_pillars(width_m: float, pillars: list[dict]) -> list[tuple[float, float]]:
    """pillars: position_m, thickness_m — treated as blocked intervals."""
    blocked = []
    for p in pillars:
        half = p.get("thickness_m", 0.4) / 2.0
        lo = max(0.0, p["position_m"] - half)
        hi = min(width_m, p["position_m"] + half)
        if hi > lo:
            blocked.append((lo, hi))
    blocked.sort()
    merged = []
    for lo, hi in blocked:
        if not merged or lo > merged[-1][1]:
            merged.append([lo, hi])
        else:
            merged[-1][1] = max(merged[-1][1], hi)
    spans = []
    cursor = 0.0
    for lo, hi in merged:
        if lo > cursor:
            spans.append((cursor, lo))
        cursor = hi
    if cursor < width_m:
        spans.append((cursor, width_m))
    return [(round(a, 3), round(b, 3)) for a, b in spans if b - a > 1e-6]

def allocate_first_fit(width_m: float, vendors: list[dict], pillars: list[dict]) -> AllocResult:
    """vendors sorted by priority ascending then id; each needs stall_width_m contiguous in one free span (no pillar cross)."""
    gaps = free_spans_from_pillars(width_m, pillars)
    # mutable remaining capacity per gap; index aligns with gaps（序号 = 下标 + 1）
    remain = [[a, b] for a, b in gaps]
    ordered = sorted(vendors, key=lambda v: (v.get("priority", 1), v["id"]))
    placements: list[Placement] = []
    rejected: list[Rejected] = []
    for v in ordered:
        need = float(v["stall_width_m"])
        placed = False
        for idx, span in enumerate(remain):
            avail = span[1] - span[0]
            if avail + 1e-9 >= need:
                start = span[0]
                end = start + need
                gap_left, gap_right = gaps[idx]
                placements.append(Placement(
                    v["id"], v["name"], round(start, 3), round(end, 3), need,
                    span_index=idx + 1,
                    span_left_m=gap_left,
                    span_right_m=gap_right,
                    offset_from_span_left_m=round(start - gap_left, 3),
                ))
                span[0] = end
                placed = True
                break
        if not placed:
            rejected.append(Rejected(v["id"], v["name"], need, "无连续空档可放下且不跨越挡柱"))
    free = [(round(a, 3), round(b, 3)) for a, b in remain if b - a > 1e-6]
    return AllocResult(placements, rejected, free, gaps)

def result_to_dict(r: AllocResult) -> dict:
    return {
        "placements": [asdict(p) for p in r.placements],
        "rejected": [asdict(x) for x in r.rejected],
        "free_spans": [{"start_m": a, "end_m": b} for a, b in r.free_spans],
        "gaps": [{"index": i + 1, "start_m": a, "end_m": b} for i, (a, b) in enumerate(r.gaps)],
    }
