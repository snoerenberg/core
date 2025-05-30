from typing import List, Tuple
from unittest.mock import Mock

import pytest

from control import data
from control.algorithm import common
from control.chargepoint.chargepoint import Chargepoint
from control.ev.ev import Ev
from control.counter import Counter
from control.counter_all import CounterAll
from control.io_device import IoActions


@pytest.fixture(autouse=True)
def cp() -> None:
    data.data_init(Mock())
    data.data.cp_data = {"cp0": Chargepoint(0, None)}
    data.data.io_actions = IoActions()


@pytest.mark.parametrize("set_current, expected_current",
                         [pytest.param(6, None),
                          pytest.param(0, None)])
def test_reset_current(set_current: int, expected_current: int):
    # setup
    data.data.cp_data["cp0"].data.set.current = set_current

    # execution
    common.reset_current()

    # evaluation
    assert data.data.cp_data["cp0"].data.set.current == expected_current


@pytest.mark.parametrize(
    "diff, required_currents, expected_set_current, expected_diffs",
    [
        pytest.param(10, [10, 0, 0], 10, [2, 0, 0], id="set diff one phase"),
        pytest.param(10, [12]*3, 10, [2]*3, id="set diff three phases"),
        pytest.param(8, [8]*3, 8, [0]*3, id="min current is already set, three phases"),
    ])
def test_set_current_counterdiff(diff: float,
                                 required_currents: List[float],
                                 expected_set_current: float,
                                 expected_diffs: List[float],
                                 monkeypatch):
    # setup
    cp = Chargepoint(4, None)
    ev = Ev(0)
    cp.data.control_parameter.required_currents = required_currents
    cp.data.set.charging_ev_data = ev
    cp.data.set.current = 6
    cp.data.get.currents = [10]*3
    get_counters_to_check_mock = Mock(return_value=["cp0", "cp6"])
    monkeypatch.setattr(CounterAll, "get_counters_to_check", get_counters_to_check_mock)
    data.data.counter_data = {"cp0": Mock(spec=Counter), "cp6": Mock(spec=Counter)}

    # evaluation
    common.set_current_counterdiff(8, diff, cp)

    # assertion
    assert cp.data.set.current == expected_set_current
    if max(expected_diffs) != 0:
        assert data.data._counter_data['cp0'].update_values_left.call_args_list[0][0][0] == expected_diffs
        assert data.data._counter_data['cp6'].update_values_left.call_args_list[0][0][0] == expected_diffs


@pytest.mark.parametrize(
    "required_currents, expected_mins_counts",
    [
        ([10, 0, 0], ([6, 0, 0], [1, 0, 0])),
        ([12]*3, ([6]*3, [1]*3))
    ])
def test_get_min_current(required_currents: List[float], expected_mins_counts: Tuple[List[float], List[int]]):
    # setup
    cp = Chargepoint(4, None)
    ev = Ev(0)
    cp.data.control_parameter.required_currents = required_currents
    cp.data.set.charging_ev_data = ev

    # evaluation
    mins_counts = common.get_min_current(cp)

    # assertion
    assert mins_counts == expected_mins_counts


@pytest.mark.parametrize(
    "set_current, diff, expected_current",
    [
        pytest.param(None, 2, 8, id="min current is set, no current has been set on this iteration"),
        pytest.param(6, 2, 6, id="min current is set, current has been set on this iteration"),
        pytest.param(7, 2, 7, id="new current is higher, current has been set on this iteration"),
        pytest.param(9, 2, 8, id="new current is lower, current has been set on this iteration"),
    ])
def test_get_current_to_set(set_current: float, diff: float, expected_current: float):
    # setup & evaluation
    current = common.get_current_to_set(set_current, diff, 6)

    # assertion
    assert current == expected_current


@pytest.mark.parametrize(
    "counts, available_currents, missing_currents, expected_current",
    [
        pytest.param([2]*3, [12, 15, 16], [5]*3, 6),
        pytest.param([2]*3, [1]*3, [2]*3, 0.5),
        pytest.param([2]*3, [0]*3, [2]*3, 0),
    ])
def test_available_currents_for_cp(counts: List[int],
                                   available_currents: List[float],
                                   missing_currents: List[float],
                                   expected_current: float):
    # setup
    cp = Chargepoint(4, None)
    ev = Ev(0)
    cp.data.control_parameter.required_currents = [16]*3
    cp.data.control_parameter.required_current = 16
    cp.data.set.charging_ev_data = ev
    cp.data.set.target_current = 10

    # evaluation
    current = common.available_current_for_cp(cp, counts, available_currents, missing_currents)

    # assertion
    assert current == expected_current


@pytest.mark.parametrize(
    "required_currents_1, required_currents_2, expected_currents",
    [
        pytest.param([6, 10, 15], [20]*3, ([14, 18, 23], [2]*3)),
        pytest.param([6, 10, 15], [6, 0, 0], ([0, 4, 9], [2, 1, 1])),
    ])
def test_get_missing_currents_left(required_currents_1: List[float],
                                   required_currents_2: List[float],
                                   expected_currents: List[float]):
    # setup
    def setup_cp(num: int, required_currents) -> Chargepoint:
        ev = Ev(0)
        cp = Chargepoint(num, None)
        cp.data.control_parameter.required_currents = required_currents
        cp.data.set.charging_ev_data = ev
        return cp

    # evaluation
    currents = common.get_missing_currents_left(
        [setup_cp(1, required_currents_1), setup_cp(2, required_currents_2)])

    # assertion
    assert currents == expected_currents


@pytest.mark.parametrize(
    "consider_less_charging, get_currents, expected_considered",
    [
        pytest.param(False, [6]*3, 6, id="not consider_less_charging, charging less"),
        pytest.param(False, [10]*3, 10, id="not consider_less_charging, charging with set current"),
        pytest.param(True, [0]*3, 10, id="consider_less_charging"),
    ])
def test_consider_less_charging_chargepoint_in_loadmanagement(consider_less_charging: bool,
                                                              get_currents: List[float],
                                                              expected_considered: bool):
    # setup
    cp = Chargepoint(4, None)
    cp.data.get.currents = get_currents
    cp.data.set.current = 10
    cp.data.control_parameter.timestamp_charge_start = 1652683152
    data.data.counter_all_data.data.config.consider_less_charging = consider_less_charging

    # evaluation
    considered = common.consider_less_charging_chargepoint_in_loadmanagement(cp, 10)

    # assertion
    assert considered == expected_considered
