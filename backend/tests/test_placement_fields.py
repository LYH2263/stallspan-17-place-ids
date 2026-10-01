from app.services.first_fit_engine import (
    allocate_first_fit, free_spans_from_pillars, gaps_from_spans, validate_placements,
)

PILLARS_SEED = [{"position_m": 10.0, "thickness_m": 0.5}, {"position_m": 20.0, "thickness_m": 0.5}]


def test_seed_gaps_left_of_pillar_a():
    """东街段 30m + 灯柱A@10(厚0.5)、灯柱B@20(厚0.5)：
    空档#1 = [0, 9.75]，即灯柱A左侧空档。"""
    gaps = gaps_from_spans(free_spans_from_pillars(30.0, PILLARS_SEED))
    assert [(g.index, g.start_m, g.end_m) for g in gaps] == [
        (1, 0.0, 9.75), (2, 10.25, 19.75), (3, 20.25, 30.0),
    ]


def _seed_vendors():
    return [
        {"id": 1, "name": "阿强烧烤", "stall_width_m": 4.0, "priority": 1},
        {"id": 2, "name": "林记糖水", "stall_width_m": 3.0, "priority": 1},
        {"id": 3, "name": "老周水果", "stall_width_m": 5.0, "priority": 2},
        {"id": 4, "name": "小美饰品", "stall_width_m": 2.5, "priority": 2},
        {"id": 5, "name": "大碗面", "stall_width_m": 6.0, "priority": 1},
        {"id": 6, "name": "手作皮具", "stall_width_m": 3.5, "priority": 3},
        {"id": 7, "name": "巨型舞台车", "stall_width_m": 12.0, "priority": 9},
    ]


def test_placements_carry_gap_index_and_offset():
    r = allocate_first_fit(30.0, _seed_vendors(), PILLARS_SEED)
    by_name = {p.vendor_name: p for p in r.placements}

    # 灯柱A左侧空档（#1，左禁入沿 0）：阿强0m、林记4m、小美7m
    assert by_name["阿强烧烤"].gap_index == 1
    assert by_name["阿强烧烤"].offset_from_gap_left_m == 0.0
    assert by_name["林记糖水"].gap_index == 1
    assert by_name["林记糖水"].offset_from_gap_left_m == 4.0
    assert by_name["小美饰品"].gap_index == 1
    assert by_name["小美饰品"].offset_from_gap_left_m == 7.0

    # 空档#2 左禁入沿 10.25：大碗面贴沿、手作皮具距沿 6m
    assert by_name["大碗面"].gap_index == 2
    assert by_name["大碗面"].offset_from_gap_left_m == 0.0
    assert by_name["大碗面"].start_m == 10.25
    assert by_name["手作皮具"].gap_index == 2
    assert by_name["手作皮具"].offset_from_gap_left_m == 6.0
    assert abs(by_name["手作皮具"].start_m - 16.25) < 1e-9

    # 老周水果落到空档#3，贴左禁入沿 20.25
    assert by_name["老周水果"].gap_index == 3
    assert by_name["老周水果"].offset_from_gap_left_m == 0.0
    assert by_name["老周水果"].start_m == 20.25


def test_oversized_rejected_is_gap_shortage_not_consistency():
    r = allocate_first_fit(30.0, _seed_vendors(), PILLARS_SEED)
    assert [x.vendor_name for x in r.rejected] == ["巨型舞台车"]
    # 能放下的 6 个落点全部通过对账（空隙不足与字段对账两码事）
    gaps = [{"index": g.index, "start_m": g.start_m, "end_m": g.end_m} for g in r.gaps]
    from dataclasses import asdict
    assert validate_placements([asdict(p) for p in r.placements], gaps) == []


def test_validate_missing_field():
    gaps = [{"index": 1, "start_m": 0.0, "end_m": 9.75}]
    p = {"vendor_id": 1, "vendor_name": "A", "start_m": 0.0, "end_m": 4.0,
         "width_m": 4.0, "gap_index": 1}  # 缺 offset_from_gap_left_m
    errs = validate_placements([p], gaps)
    assert len(errs) == 1 and "缺字段" in errs[0]


def test_validate_gap_index_out_of_range():
    gaps = [{"index": 1, "start_m": 0.0, "end_m": 9.75}]
    p = {"vendor_id": 1, "vendor_name": "A", "start_m": 0.0, "end_m": 4.0,
         "width_m": 4.0, "gap_index": 9, "offset_from_gap_left_m": 0.0}
    errs = validate_placements([p], gaps)
    assert len(errs) == 1 and "序号越界" in errs[0]


def test_validate_offset_mismatch():
    gaps = [{"index": 1, "start_m": 0.0, "end_m": 9.75}]
    # 起点 4.0 距左沿应为 4.0，却报 3.2 —— 距柱与起止对不上
    p = {"vendor_id": 1, "vendor_name": "A", "start_m": 4.0, "end_m": 8.0,
         "width_m": 4.0, "gap_index": 1, "offset_from_gap_left_m": 3.2}
    errs = validate_placements([p], gaps)
    assert len(errs) == 1 and "距左禁入沿" in errs[0]


def test_validate_cross_pillar():
    gaps = [{"index": 1, "start_m": 0.0, "end_m": 9.75}]
    p = {"vendor_id": 1, "vendor_name": "A", "start_m": 7.0, "end_m": 11.0,
         "width_m": 4.0, "gap_index": 1, "offset_from_gap_left_m": 7.0}
    errs = validate_placements([p], gaps)
    assert any("超出空档" in e for e in errs)


def test_validate_width_mismatch():
    gaps = [{"index": 1, "start_m": 0.0, "end_m": 9.75}]
    p = {"vendor_id": 1, "vendor_name": "A", "start_m": 0.0, "end_m": 4.0,
         "width_m": 3.5, "gap_index": 1, "offset_from_gap_left_m": 0.0}
    errs = validate_placements([p], gaps)
    assert any("宽度" in e and "对不上" in e for e in errs)
