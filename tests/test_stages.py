"""Tests for circuit stage registry."""

import pytest

from eod_sim.stages.registry import (
    DEFAULT_STAGE_ID,
    get_stage,
    list_stages,
)


def test_default_stage_is_sanity():
    assert DEFAULT_STAGE_ID == "00_sanity_ina333"


def test_sanity_stage_is_runnable():
    stage = get_stage("00_sanity_ina333")
    assert stage.is_runnable
    assert "ideal" in stage.benches
    assert "ti" in stage.benches


def test_mcp6561_sanity_stage_is_runnable():
    stage = get_stage("00_sanity_mcp6561")
    assert stage.is_runnable
    assert stage.benches["default"] == "bench.cir"
    assert not stage.supports_eod_input


def test_passives_stage_is_runnable():
    stage = get_stage("01_passives")
    assert stage.is_runnable
    assert stage.drive_mode == "electrodes"
    assert stage.fixed_rg is False


def test_frontend_stage_is_runnable():
    stage = get_stage("02_frontend")
    assert stage.is_runnable
    assert stage.fixed_rg is True
    assert "ideal" in stage.benches


def test_detector_stage_is_runnable():
    stage = get_stage("03_detector")
    assert stage.is_runnable
    assert stage.comparator_stage is True
    assert stage.signal_nodes["out"] == "comp_out"


def test_unknown_stage_raises():
    with pytest.raises(KeyError, match="Unknown stage"):
        get_stage("99_missing")


def test_list_stages_ordered():
    ids = [stage.id for stage in list_stages()]
    assert ids[0] == "00_sanity_ina333"
    assert "01_passives" in ids
    assert "02_frontend" in ids
    assert "03_detector" in ids
