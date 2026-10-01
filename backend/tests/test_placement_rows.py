import pytest

from app.services.placement_rows import (
    PlacementValidationError,
    build_placement_rows,
    validate_placement_rows,
)

GAPS = [
    {"index": 1, "start_m": 0.0, "end_m": 9.75},
    {"index": 2, "start_m": 10.25, "end_m": 19.75},
]


def ok_row(**kw):
    row = dict(segment_name="东街段", vendor_id=1, vendor_name="阿强烧烤",
               start_m=4.0, end_m=8.0, width_m=4.0,
               span_index=1, span_left_m=0.0, span_right_m=9.75,
               offset_from_span_left_m=4.0)
    row.update(kw)
    return row


def test_valid_rows_pass():
    validate_placement_rows([ok_row(), ok_row(vendor_id=2, span_index=2, span_left_m=10.25,
                                              span_right_m=19.75, start_m=10.25, end_m=14.25,
                                              offset_from_span_left_m=0.0)], GAPS)


def test_missing_field_fails():
    with pytest.raises(PlacementValidationError, match="缺字段"):
        validate_placement_rows([ok_row(offset_from_span_left_m=None)], GAPS)


@pytest.mark.parametrize("bad", [0, 3, -1, 99])
def test_span_index_out_of_range(bad):
    with pytest.raises(PlacementValidationError, match="越界"):
        validate_placement_rows([ok_row(span_index=bad)], GAPS)


def test_offset_mismatch_fails():
    with pytest.raises(PlacementValidationError, match="距左禁入沿"):
        validate_placement_rows([ok_row(offset_from_span_left_m=4.5)], GAPS)


def test_span_edge_mismatch_fails():
    with pytest.raises(PlacementValidationError, match="禁入沿"):
        validate_placement_rows([ok_row(span_left_m=0.5)], GAPS)


def test_width_mismatch_fails():
    with pytest.raises(PlacementValidationError, match="宽度"):
        validate_placement_rows([ok_row(width_m=3.9)], GAPS)


def test_outside_gap_fails():
    with pytest.raises(PlacementValidationError, match="越出所属空档"):
        validate_placement_rows([ok_row(start_m=9.8, end_m=13.8,
                                        offset_from_span_left_m=9.8)], GAPS)


def test_empty_name_fails():
    with pytest.raises(PlacementValidationError, match="为空"):
        validate_placement_rows([ok_row(vendor_name="  ")], GAPS)


def test_build_rows_leaves_missing_as_none_for_validator():
    rows = build_placement_rows({"placements": [{"vendor_id": 1, "vendor_name": "阿强烧烤"}]}, "东街段")
    assert rows[0]["offset_from_span_left_m"] is None
    with pytest.raises(PlacementValidationError, match="缺字段"):
        validate_placement_rows(rows, GAPS)
