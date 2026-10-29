import pytest

from catchment import assumptions


def test_derived_constants():
    a = assumptions
    assert a.MAX_PAIR_MIN == 17
    assert a.ORDERS_PER_HOUSEHOLD_DAY == pytest.approx(0.082, abs=0.0005)
    assert a.ORDERS_PER_STORE_DAY == pytest.approx(1576, abs=1)
    assert round(a.CAPACITY) == 2364   # 02-plan and the decision log
