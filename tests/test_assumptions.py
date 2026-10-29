import pytest

from catchment import assumptions


def test_max_pair_min_is_longest_promise_less_pick_and_pack():
    assert assumptions.MAX_PAIR_MIN == 17
