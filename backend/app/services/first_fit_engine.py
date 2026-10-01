"""1D First-Fit stall placement along a street segment; stalls cannot cross pillars.

口径约定（切空结果 / 主图点开信息 / 正式入库行三处必须同一口径）：
- 挡柱按厚度展开为禁入区间，禁入区间之间的可放区间称为「柱间空档」，自街段起点
  从 1 开始编号（序号 1 为起点到第一根挡柱左沿之间的空档，含无挡柱的整段情形）。
- 每个落点必须钉两个派生字段：
    gap_index                 所属柱间空档序号（1-based）
    offset_from_gap_left_m    起点相对该空档「左禁入沿」的距离米，
                              左禁入沿即空档左边界（街段起点或上一挡柱右沿）。
"""
from __future__ import annotations
from dataclasses import asdict, dataclass

# 起止米 / 宽度 / 距柱对账允许的数值误差
EPS = 1e-6


@dataclass
class Gap:
    index: int
    start_m: float          # 左禁入沿（街段起点 0 或上一挡柱右沿）
    end_m: float            # 右禁入沿（下一挡柱左沿或街段终点）

@dataclass
class Placement:
    vendor_id: int
    vendor_name: str
    start_m: float
    end_m: float
    width_m: float
    gap_index: int                      # 所属柱间空档序号（1-based）
    offset_from_gap_left_m: float       # 起点距该空档左禁入沿的距离米

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
    free_spans: list[tuple[float, float]]
    gaps: list[Gap]

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


def gaps_from_spans(spans: list[tuple[float, float]]) -> list[Gap]:
    return [Gap(index=i + 1, start_m=round(a, 3), end_m=round(b, 3))
            for i, (a, b) in enumerate(spans)]


def allocate_first_fit(width_m: float, vendors: list[dict], pillars: list[dict]) -> AllocResult:
    """vendors sorted by priority ascending then id; each needs stall_width_m contiguous in one free span (no pillar cross)."""
    spans = free_spans_from_pillars(width_m, pillars)
    gaps = gaps_from_spans(spans)
    # mutable remaining capacity per span; index 对齐 gaps 序号 - 1
    remain = [[a, b] for a, b in spans]
    ordered = sorted(vendors, key=lambda v: (v.get("priority", 1), v["id"]))
    placements: list[Placement] = []
    rejected: list[Rejected] = []
    for v in ordered:
        need = float(v["stall_width_m"])
        placed = False
        for gi, span in enumerate(remain):
            avail = span[1] - span[0]
            if avail + 1e-9 >= need:
                start = span[0]
                end = start + need
                gap = gaps[gi]
                placements.append(Placement(
                    v["id"], v["name"],
                    round(start, 3), round(end, 3), need,
                    gap_index=gap.index,
                    offset_from_gap_left_m=round(start - gap.start_m, 3),
                ))
                span[0] = end
                placed = True
                break
        if not placed:
            rejected.append(Rejected(v["id"], v["name"], need, "无连续空档可放下且不跨越挡柱"))
    free = [(round(a, 3), round(b, 3)) for a, b in remain if b - a > 1e-6]
    return AllocResult(placements, rejected, free, gaps)


def validate_placements(placements: list[dict], gaps: list[dict]) -> list[str]:
    """入库前对账：字段缺失 / 序号越界 / 距柱与起止对不上时返回错误说明列表（空列表即通过）。

    这些是数据一致性错误，调用方必须整次写入失败，不得冒充「空隙不足」。
    """
    errors: list[str] = []
    gap_by_index = {int(g["index"]): g for g in gaps}
    required = ("vendor_id", "vendor_name", "start_m", "end_m", "width_m",
                "gap_index", "offset_from_gap_left_m")
    for i, p in enumerate(placements):
        tag = f"第{i + 1}行(vendor_id={p.get('vendor_id')})"
        missing = [k for k in required if p.get(k) is None]
        if missing:
            errors.append(f"{tag}缺字段: {','.join(missing)}")
            continue
        gi = int(p["gap_index"])
        gap = gap_by_index.get(gi)
        if gap is None:
            errors.append(f"{tag}空档序号越界: {gi}（切空共{len(gaps)}档）")
            continue
        start, end = float(p["start_m"]), float(p["end_m"])
        width, offset = float(p["width_m"]), float(p["offset_from_gap_left_m"])
        g_lo, g_hi = float(gap["start_m"]), float(gap["end_m"])
        if start < g_lo - EPS or end > g_hi + EPS:
            errors.append(f"{tag}起止[{start},{end}]超出空档{gi}[{g_lo},{g_hi}]（跨挡柱）")
        if abs((end - start) - width) > EPS:
            errors.append(f"{tag}宽度{width}与起止{end - start:.3f}对不上")
        if abs((start - g_lo) - offset) > EPS:
            errors.append(
                f"{tag}距左禁入沿{offset}与起止推算{start - g_lo:.3f}对不上（空档{gi}左沿{g_lo}）")
    return errors

def result_to_dict(r: AllocResult) -> dict:
    return {
        "placements": [asdict(p) for p in r.placements],
        "rejected": [asdict(x) for x in r.rejected],
        "free_spans": [{"start_m": a, "end_m": b} for a, b in r.free_spans],
        "gaps": [asdict(g) for g in r.gaps],
    }
