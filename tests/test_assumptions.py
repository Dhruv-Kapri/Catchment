import pandas as pd
import pytest

from catchment import assumptions, fetch


def test_max_pair_min_is_longest_promise_less_pick_and_pack() -> None:
    assert assumptions.MAX_PAIR_MIN == 17


def test_orders_per_store_day_from_blinkit_orders_and_stores() -> None:
    assert assumptions.ORDERS_PER_STORE_DAY == pytest.approx(1576, abs=1)


def test_orders_per_household_day_is_the_calibration_target() -> None:
    assert assumptions.ORDERS_PER_HOUSEHOLD_DAY == pytest.approx(0.094, abs=0.0005)


def test_capacity_matches_02_plan() -> None:
    assert round(assumptions.CAPACITY) == 2364   # 02-plan and the decision log


def test_table_lists_every_input() -> None:
    t = assumptions.table()
    assert list(t.columns) == ["Input", "Value", "Source", "Date", "Status"]
    assert list(t.Input) == [
        # 00-demand
        "Household size", "Multiplier bounds", "Operator orders, Q2 FY27", "Operator stores",
        "Competitor stores (next-largest brand)",
        "NCR dark stores (all brands)", "NCR population",
        # 01-reach
        "Pick-and-pack allowance", "Pairs kept in the table", "Second road for snapping",
        # 02-plan
        "Default scenario", "Lever ranges", "Slow-traffic factor", "New stores, N", "Orders per store per day", "Capacity per store",
        "Network size", "Operator/competitor split",
        "Store placement", "Competitor reach", "Demand split", "Sites for new stores",
        "Assignment tie-break", "Integer scale", "Plan budget", "Solver",
    ]


def test_table_cells_are_non_empty() -> None:
    t = assumptions.table()
    for col in ("Input", "Value", "Source", "Date", "Status"):
        assert t[col].astype(str).str.strip().ne("").all()


def test_status_and_values_match_the_notebook_tables() -> None:
    t = assumptions.table().set_index("Input")
    verified = {"Household size", "Operator orders, Q2 FY27", "Operator stores", "NCR dark stores (all brands)",
                "NCR population", "Orders per store per day", "Competitor stores (next-largest brand)"}
    assert set(t.index[t.Status == "Verified"]) == verified
    assert set(t.Status) == {"Verified", "Assumption"}
    dated = verified - {"Orders per store per day", "Competitor stores (next-largest brand)"}
    assert t.loc[list(dated), "Date"].eq("2026-10-29").all()
    assert t.loc["Competitor stores (next-largest brand)", "Date"] == "2026-11-01"
    assert t.loc["Competitor stores (next-largest brand)", "Value"] == "1,240 at quarter end"
    assert t.loc["Operator/competitor split", "Status"] == "Assumption"
    assert "68.9%" in t.loc["Operator/competitor split", "Value"]
    assert "39 and 18" in t.loc["Operator/competitor split", "Value"]
    assert "both Verified" in t.loc["Operator/competitor split", "Source"]
    assert t.loc["Household size", "Value"] == "4.5 persons"
    assert t.loc["Multiplier bounds", "Value"] == "0.5 to 1.5"
    assert t.loc["Operator orders, Q2 FY27", "Value"] == "398.9 M over 92 days"
    assert t.loc["Operator stores", "Value"] == "2,751 at quarter end"
    assert t.loc["NCR dark stores (all brands)", "Value"] == "~400"
    assert t.loc["NCR population", "Value"] == "30.2 M"
    assert t.loc["Pick-and-pack allowance", "Value"] == "3 min, fixed"
    assert t.loc["Pairs kept in the table", "Value"].startswith("Free-flow ≤ 17 min")
    assert "5 m" in t.loc["Second road for snapping", "Value"] and "100 m" in t.loc["Second road for snapping", "Value"]
    assert "2,364 orders per day" in t.loc["Capacity per store", "Value"]


def test_default_multiplier_is_the_spot_check_figure() -> None:
    assert assumptions.MULTIPLIER == 1.8
    row = assumptions.table().set_index("Input").loc["Default scenario"]
    assert "1.8" in row.Value and "3.9 min" in row.Value
    assert "Spot check" in row.Source and "1.79" in row.Source and row.Date == "2026-11-01"
    assert "02-plan and 03-area ran at 1.4" in row.Source   # their committed outputs predate the change


def test_lever_ranges_row_traces_the_narrowed_promise_range() -> None:
    row = assumptions.table().set_index("Input").loc["Lever ranges"]
    assert row.Status == "Assumption" and "promise 8-16 min" in row.Value   # narrowed from 8-20 by 04-plan (#30)
    assert "2026-11-03" in row.Source and "2026-11-05" in row.Source and row.Date == "2026-11-05"   # the narrowing and the steps trace to their decision-log entries


def test_network_size_is_area_demand_over_orders_per_store_day() -> None:
    assert assumptions.network_size(57 * assumptions.ORDERS_PER_STORE_DAY) == 57
    assert assumptions.network_size(0.4 * assumptions.ORDERS_PER_STORE_DAY) == 0
    assert assumptions.network_size(56.6 * assumptions.ORDERS_PER_STORE_DAY) == 57


def test_operator_share_is_the_reported_store_split() -> None:
    assert assumptions.OPERATOR_SHARE == pytest.approx(2751 / (2751 + 1240))


@pytest.mark.parametrize("n, operator, competitor", [(0, 0, 0), (1, 1, 0), (2, 1, 1), (3, 2, 1), (10, 7, 3), (57, 39, 18), (100, 69, 31)])
def test_brand_split_follows_the_reported_counts(n: int, operator: int, competitor: int) -> None:
    assert assumptions.brand_split(n) == {"Operator": operator, "Competitor": competitor}


def test_area_network_size_matches_the_built_demand() -> None:
    path = fetch.DATA / "demand-r9.parquet"
    if not path.exists():
        pytest.skip(f"{path} not built")
    demand = pd.read_parquet(path)["demand"]
    assert assumptions.network_size(demand.sum()) == assumptions.AREA_NETWORK_SIZE
