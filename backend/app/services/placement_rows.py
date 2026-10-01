"""入库占位行的派生与校验：与当时切空结果同一口径，对不齐即整次作废。

校验失败抛 PlacementValidationError —— 这是数据口径错误，
不是“空隙不足”，调用方不得把它翻译成空档不够。
"""
from __future__ import annotations

TOL = 1e-6

# 正式入库占位行必须钉死的字段
REQUIRED_FIELDS = (
    "segment_name", "vendor_id", "vendor_name",
    "start_m", "end_m", "width_m",
    "span_index", "span_left_m", "span_right_m", "offset_from_span_left_m",
)


class PlacementValidationError(ValueError):
    """占位行派生字段与切空结果对不上（缺字段 / 序号越界 / 距柱与起止不符）。"""


def build_placement_rows(result: dict, segment_name: str) -> list[dict]:
    """从分配结果派生占位行字典。缺字段留 None，交给 validate 统一判废。"""
    rows = []
    for p in result.get("placements") or []:
        rows.append({
            "segment_name": segment_name,
            "vendor_id": p.get("vendor_id"),
            "vendor_name": p.get("vendor_name"),
            "start_m": p.get("start_m"),
            "end_m": p.get("end_m"),
            "width_m": p.get("width_m"),
            "span_index": p.get("span_index"),
            "span_left_m": p.get("span_left_m"),
            "span_right_m": p.get("span_right_m"),
            "offset_from_span_left_m": p.get("offset_from_span_left_m"),
        })
    return rows


def validate_placement_rows(rows: list[dict], gaps: list[dict]) -> None:
    """对照当时切空结果逐行校验；任一不符即抛错，调用方整次回滚。

    gaps: result_to_dict 的 "gaps"（[{"index","start_m","end_m"}...]，序号 1 起）。
    """
    bounds = {int(g["index"]): (float(g["start_m"]), float(g["end_m"])) for g in gaps}
    for i, r in enumerate(rows, start=1):
        who = r.get("vendor_name") or f"第{i}行"
        for f in REQUIRED_FIELDS:
            if r.get(f) is None:
                raise PlacementValidationError(f"占位行缺字段 {f}（{who}）")
        idx = r["span_index"]
        if not isinstance(idx, int) or isinstance(idx, bool) or idx not in bounds:
            raise PlacementValidationError(f"空档序号越界：{idx}（{who}）")
        gap_left, gap_right = bounds[idx]
        start, end, width = float(r["start_m"]), float(r["end_m"]), float(r["width_m"])
        if not str(r["segment_name"]).strip() or not str(r["vendor_name"]).strip():
            raise PlacementValidationError(f"街段名或摊主名为空（{who}）")
        if not isinstance(r["vendor_id"], int) or isinstance(r["vendor_id"], bool):
            raise PlacementValidationError(f"摊主号非法（{who}）")
        if abs(float(r["span_left_m"]) - gap_left) > TOL or abs(float(r["span_right_m"]) - gap_right) > TOL:
            raise PlacementValidationError(f"空档禁入沿与切空结果不符（{who}）")
        if abs(start - gap_left - float(r["offset_from_span_left_m"])) > TOL:
            raise PlacementValidationError(f"距左禁入沿与起点对不上（{who}）")
        if start < gap_left - TOL or end > gap_right + TOL or end <= start:
            raise PlacementValidationError(f"起止越出所属空档（{who}）")
        if width <= 0 or abs(end - start - width) > TOL:
            raise PlacementValidationError(f"宽度与起止对不上（{who}）")


def placement_row_to_dict(r) -> dict:
    """库行 → 接口口径；主图点开与运行抽屉都从这里出，保证同一口径。"""
    return {
        "id": r.id,
        "run_id": r.run_id,
        "segment_id": r.segment_id,
        "segment_name": r.segment_name,
        "vendor_id": r.vendor_id,
        "vendor_name": r.vendor_name,
        "start_m": r.start_m,
        "end_m": r.end_m,
        "width_m": r.width_m,
        "span_index": r.span_index,
        "span_left_m": r.span_left_m,
        "span_right_m": r.span_right_m,
        "offset_from_span_left_m": r.offset_from_span_left_m,
    }
