"""Tests for recorded EOD CSV parsing and template extraction."""

from pathlib import Path

import numpy as np
import pytest

from eod_sim.recorded_pulse import (
    DEFAULT_RECORDED_ID,
    extract_central_pulse,
    get_recorded_template,
    parse_recorded_csv,
    project_data_dir,
)


def test_parse_recorded_csv_roundtrip():
    path = project_data_dir() / "EOD_row_02.csv"
    mv = parse_recorded_csv(path)
    assert len(mv) == 586
    assert mv[0] == pytest.approx(-0.254130084067583)


def test_extract_central_pulse_normalizes_peak():
    path = project_data_dir() / "EOD_row_02.csv"
    mv = parse_recorded_csv(path)
    time_s, shape, baseline, left, right, raw_peak = extract_central_pulse(
        mv, 195_312.0
    )

    assert baseline == pytest.approx(-0.19, abs=0.05)
    assert raw_peak > 200.0
    assert right > left
    assert time_s[0] == pytest.approx(0.0)
    assert np.max(np.abs(shape)) == pytest.approx(1.0, rel=1e-6)
    assert shape.max() == pytest.approx(146.0352130990942 / raw_peak, rel=1e-3)
    assert shape.min() == pytest.approx(-249.6461442846338 / raw_peak, rel=1e-3)


def test_bundled_template_duration_near_200us():
    tpl = get_recorded_template(DEFAULT_RECORDED_ID)
    assert tpl.duration_us == pytest.approx(200.0, rel=0.05)
    assert tpl.source_id == DEFAULT_RECORDED_ID


def test_unknown_recorded_source_raises():
    with pytest.raises(ValueError, match="Unknown recorded source"):
        get_recorded_template("missing_source")
