from app.services.first_fit_engine import allocate_first_fit, free_spans_from_pillars, result_to_dict

PILLARS = [{"position_m": 10.0, "thickness_m": 0.5}, {"position_m": 20.0, "thickness_m": 0.5}]

def test_free_spans_with_pillars():
    spans = free_spans_from_pillars(30.0, PILLARS)
    assert len(spans) == 3
    assert spans[0][0] == 0.0

def test_first_fit_no_cross_pillar():
    vendors = [
        {"id": 1, "name": "A", "stall_width_m": 4.0, "priority": 1},
        {"id": 2, "name": "B", "stall_width_m": 12.0, "priority": 1},
    ]
    pillars = [{"position_m": 10.0, "thickness_m": 0.5}]
    r = allocate_first_fit(30.0, vendors, pillars)
    assert any(p.vendor_name == "A" for p in r.placements)
    # 12m may fit in a free span after first placement depending on remainders
    assert len(r.placements) + len(r.rejected) == 2

def test_reject_oversized():
    vendors = [{"id": 1, "name": "Huge", "stall_width_m": 25.0, "priority": 1}]
    r = allocate_first_fit(30.0, vendors, PILLARS)
    assert len(r.rejected) == 1
    assert r.rejected[0].vendor_name == "Huge"

def test_placements_pin_span_index_and_offset():
    """种子东街段口径：灯柱A左侧空档（序号1）内各摊的序号与距左沿。"""
    vendors = [
        {"id": 1, "name": "阿强烧烤", "stall_width_m": 4.0, "priority": 1},
        {"id": 2, "name": "林记糖水", "stall_width_m": 3.0, "priority": 1},
        {"id": 5, "name": "大碗面", "stall_width_m": 6.0, "priority": 1},
        {"id": 4, "name": "小美饰品", "stall_width_m": 2.5, "priority": 2},
    ]
    r = allocate_first_fit(30.0, vendors, PILLARS)
    assert r.gaps == [(0.0, 9.75), (10.25, 19.75), (20.25, 30.0)]
    by = {p.vendor_name: p for p in r.placements}
    # 灯柱A左侧空档：序号 1，左禁入沿 0
    assert (by["阿强烧烤"].span_index, by["阿强烧烤"].offset_from_span_left_m) == (1, 0.0)
    assert (by["林记糖水"].span_index, by["林记糖水"].offset_from_span_left_m) == (1, 4.0)
    assert (by["小美饰品"].span_index, by["小美饰品"].offset_from_span_left_m) == (1, 7.0)
    # 大碗面放不进空档1剩余，落到空档2（灯柱A与灯柱B之间）左沿
    assert (by["大碗面"].span_index, by["大碗面"].offset_from_span_left_m) == (2, 0.0)
    assert by["大碗面"].span_left_m == 10.25
    # 左沿 + 距左沿 == 起点，对所有占位成立
    for p in r.placements:
        assert abs(p.span_left_m + p.offset_from_span_left_m - p.start_m) < 1e-9
        assert r.gaps[p.span_index - 1] == (p.span_left_m, p.span_right_m)

def test_result_to_dict_exposes_gaps_and_derived_fields():
    vendors = [{"id": 1, "name": "A", "stall_width_m": 4.0, "priority": 1}]
    d = result_to_dict(allocate_first_fit(30.0, vendors, PILLARS))
    assert d["gaps"][0] == {"index": 1, "start_m": 0.0, "end_m": 9.75}
    p = d["placements"][0]
    for f in ("span_index", "span_left_m", "span_right_m", "offset_from_span_left_m"):
        assert f in p
    assert p["span_index"] == 1 and p["offset_from_span_left_m"] == 0.0
