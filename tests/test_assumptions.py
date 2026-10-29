import pytest

from catchment import assumptions


def test_max_pair_min_is_longest_promise_less_pick_and_pack():
    assert assumptions.MAX_PAIR_MIN == 17


def test_orders_per_store_day_from_blinkit_orders_and_stores():
    assert assumptions.ORDERS_PER_STORE_DAY == pytest.approx(1576, abs=1)


def test_orders_per_household_day_is_the_calibration_target():
    assert assumptions.ORDERS_PER_HOUSEHOLD_DAY == pytest.approx(0.082, abs=0.0005)


def test_capacity_matches_02_plan():
    assert round(assumptions.CAPACITY) == 2364   # 02-plan and the decision log


def test_table_lists_every_input():
    t = assumptions.table()
    assert list(t.columns) == ["Input", "Value", "Source", "Date", "Status"]
    assert list(t.Input) == [
        # 00-demand
        "Household size", "Multiplier bounds", "Blinkit orders, Q2 FY27", "Blinkit stores",
        "NCR dark stores (all brands)", "NCR population",
        # 01-reach
        "Pick-and-pack allowance", "Pairs kept in the table",
        # 02-plan
        "Default scenario", "New stores, N", "Orders per store per day", "Capacity per store",
        "Brands and store counts", "Store placement", "Competitor reach", "Demand split", "Sites for new stores",
        "Assignment tie-break", "Integer scale", "Solver",
    ]


def test_table_cells_are_non_empty():
    t = assumptions.table()
    for col in ("Input", "Value", "Source", "Date", "Status"):
        assert t[col].astype(str).str.strip().ne("").all()


def test_status_and_values_match_the_notebook_tables():
    t = assumptions.table().set_index("Input")
    verified = {"Household size", "Blinkit orders, Q2 FY27", "Blinkit stores", "NCR dark stores (all brands)",
                "NCR population", "Orders per store per day"}
    assert set(t.index[t.Status == "Verified"]) == verified
    assert set(t.Status) == {"Verified", "Assumption"}
    assert t.loc[list(verified - {"Orders per store per day"}), "Date"].eq("2026-10-29").all()
    assert t.loc["Household size", "Value"] == "4.5 persons"
    assert t.loc["Multiplier bounds", "Value"] == "0.5 to 1.5"
    assert t.loc["Blinkit orders, Q2 FY27", "Value"] == "398.9 M over 92 days"
    assert t.loc["Blinkit stores", "Value"] == "2,751 at quarter end"
    assert t.loc["NCR dark stores (all brands)", "Value"] == "~400"
    assert t.loc["NCR population", "Value"] == "34.7 M"
    assert t.loc["Pick-and-pack allowance", "Value"] == "3 min, fixed"
    assert t.loc["Pairs kept in the table", "Value"].startswith("Free-flow ≤ 17 min")
    assert "2,364 orders per day" in t.loc["Capacity per store", "Value"]
