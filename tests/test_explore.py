import dataclasses

import numpy as np
import pandas as pd
import pytest

from catchment import assumptions, explore
from catchment.explore import (
    Case,
    SolveResult,
    evaluate,
    explore_reachable,
    greedy_plan,
    load_case,
    place_placeholder_network,
    solve_plan,
    with_network,
)

# Four hexes, three candidate sites (c1 has rank 0, listed out of order on purpose). Reachable pairs (free-flow
# minutes <= 5.0): c0 -> h0, h1; c1 -> h1, h2; c2 -> h3. Two more pairs are too slow: (c2, h2) and (c0, h3).
DEMAND: list[float] = [100.0, 200.0, 300.0, 400.0]


def hexes() -> pd.DataFrame:
    return pd.DataFrame({"demand": DEMAND}, index=pd.Index(["h0", "h1", "h2", "h3"]))


def candidates() -> pd.DataFrame:
    return pd.DataFrame({"rank": [1, 0, 2]}, index=pd.Index(["c0", "c1", "c2"]))   # c1 is the busiest


def table() -> pd.DataFrame:
    return pd.DataFrame({
        "candidate": ["c0", "c0", "c1", "c1", "c2", "c2", "c0"],
        "hex": ["h0", "h1", "h1", "h2", "h3", "h2", "h3"],
        "minutes": [2.0, 4.0, 3.0, 5.0, 4.0, 5.1, 6.0],
    })


def case() -> Case:
    """Sites in rank order are c1, c0, c2, that is positions 0, 1, 2."""
    return load_case(9, hexes(), candidates(), table())


C_OP: dict[str, list[int]] = {"Operator": [1]}   # the operator's store is on c0, position 1


def test_reachable_boundary() -> None:
    assert explore_reachable(5.0)
    assert not explore_reachable(5.01)
    assert list(explore_reachable(np.array([0.0, 5.0, 5.01, 17.0]))) == [True, True, False, False]
    assert list(explore_reachable(pd.Series([4.9, 5.2]))) == [True, False]


def test_placeholder_defaults_are_pinned() -> None:
    assert explore.MULTIPLIER == 1.4
    assert explore.BRAND_COUNTS == {"Operator": 3, "Competitor A": 4, "Competitor B": 3}
    assert explore.CAP_INT == round(assumptions.CAPACITY * assumptions.SCALE)


def test_load_case_positions_and_filters() -> None:
    C = case()
    assert list(C.sites) == ["c1", "c0", "c2"]
    assert list(C.rank) == [0, 1, 2]
    assert list(C.hexes) == ["h0", "h1", "h2", "h3"]
    pairs = sorted(zip(C.ps.tolist(), C.ph.tolist(), C.pm.tolist()))
    assert pairs == [(0, 1, 3.0), (0, 2, 5.0), (1, 0, 2.0), (1, 1, 4.0), (2, 3, 4.0)]   # slow pairs dropped
    assert list(C.share_int) == [10000, 20000, 30000, 40000]
    assert list(C.new_sites) == [0, 1, 2]
    assert C.cap_int == explore.CAP_INT
    assert C.stores == {} and list(C.k) == [0, 0, 0, 0]


def test_load_case_n_area_hexes_defaults_to_len_hexes_and_can_be_given() -> None:
    assert case().n_area_hexes == 4
    assert load_case(9, hexes(), candidates(), table(), n_area_hexes=50).n_area_hexes == 50


def test_with_network_k_and_share_split_demand_by_one_plus_k() -> None:
    C = with_network(case(), {"Operator": [1], "A": [0], "B": [2]})   # A on c1 (h1, h2), B on c2 (h3)
    assert list(C.k) == [0, 1, 1, 1]
    assert list(C.share_int) == [10000, 10000, 15000, 20000]
    assert list(C.new_sites) == []


def test_with_network_counts_competitor_brands_not_stores() -> None:
    C = with_network(case(), {"Operator": [1], "A": [0, 2]})   # one brand on c1 and c2: k stays 1 where reached
    assert list(C.k) == [0, 1, 1, 1]


def test_with_network_rejects_two_stores_on_one_site() -> None:
    with pytest.raises(ValueError, match="two stores on one site"):
        with_network(case(), {"Operator": [1], "A": [1]})


def test_with_network_cap_int_override() -> None:
    assert with_network(case(), C_OP, cap_int=123).cap_int == 123
    assert with_network(case(), C_OP).cap_int == explore.CAP_INT


def test_with_network_cap_int_zero_is_honoured() -> None:
    assert with_network(case(), C_OP, cap_int=0).cap_int == 0


def test_place_placeholder_network_raises_when_no_site_reaches_demand() -> None:
    C = dataclasses.replace(case(), ps=np.array([], dtype=np.int64), ph=np.array([], dtype=np.int64),
                            pm=np.array([], dtype=np.float64))
    with pytest.raises(ValueError, match="reaches any demand"):
        place_placeholder_network(C, {"Operator": 1})


def test_place_network_is_deterministic_with_the_right_counts() -> None:
    C = case()
    counts = {"Operator": 1, "A": 1, "B": 1}
    a, b = place_placeholder_network(C, counts, seed=7), place_placeholder_network(C, counts, seed=7)
    assert a == b
    assert list(a) == ["Operator", "A", "B"] and all(len(v) == 1 for v in a.values())
    sites = [s for v in a.values() for s in v]
    assert sorted(sites) == [0, 1, 2]   # three stores, three sites, none twice
    assert any(place_placeholder_network(C, counts, seed=s) != a for s in range(8, 40))   # the seed matters


def test_solve_plan_picks_the_obviously_best_site() -> None:
    C = with_network(case(), C_OP)
    r = solve_plan(C, 1)
    assert isinstance(r, SolveResult)
    # c2 (position 2) adds h3, 400 orders; c1 (position 0) would add only h2, 300
    assert (r.status, r.chosen) == ("OPTIMAL", [2])
    assert r.obj == pytest.approx(700.0) and r.bound == pytest.approx(700.0)
    assert (r.pairs, r.new_sites, r.hexes, r.constrained_sites) == (5, 2, 4, 0)
    assert r.total_s >= r.build_s >= 0 and r.solve_s >= 0


def test_solve_plan_result_is_frozen() -> None:
    r = solve_plan(with_network(case(), C_OP), 1)
    with pytest.raises(dataclasses.FrozenInstanceError):
        r.obj = 0.0   # type: ignore[misc]


def test_solve_plan_objective_matches_evaluate_when_capacity_does_not_bind() -> None:
    C = with_network(case(), C_OP)
    r = solve_plan(C, 2)
    _, best = evaluate(C, C.stores["Operator"] + r.chosen)
    assert sorted(r.chosen) == [0, 2]
    assert r.obj == pytest.approx(best / assumptions.SCALE) == pytest.approx(1000.0)


def test_solve_plan_respects_new_sites_argument() -> None:
    C = with_network(case(), C_OP)
    r = solve_plan(C, 1, new_sites=np.array([0]))
    assert r.chosen == [0] and r.new_sites == 1 and r.obj == pytest.approx(600.0)


def test_solve_plan_with_binding_capacity_builds_x_and_matches_evaluate() -> None:
    C = with_network(case(), C_OP, cap_int=25000)   # 250 orders a store: every site's catchment exceeds it
    r = solve_plan(C, 1)
    plain = solve_plan(C, 1, pair_model=True)
    _, best = evaluate(C, C.stores["Operator"] + r.chosen)
    assert r.constrained_sites == 3
    assert r.status == "OPTIMAL" and r.chosen == [0]   # c1 takes h1 (200), c0 keeps h0 (100); c2's h3 (400) never fits
    assert r.obj == pytest.approx(300.0) == pytest.approx(best / assumptions.SCALE)
    assert plain.obj == pytest.approx(r.obj)


def test_evaluate_with_ample_capacity_serves_everything_by_nearest_store() -> None:
    C = with_network(case(), {"Operator": [0, 1, 2]})
    owner, best = evaluate(C, [0, 1, 2])
    assert best == 100000
    assert list(owner) == [1, 0, 0, 2]   # h1 is 3 min from c1 (position 0) against 4 from c0 (position 1)


def test_evaluate_respects_capacity() -> None:
    C = with_network(case(), {"Operator": [1, 0]}, cap_int=25000)
    owner, best = evaluate(C, [1, 0])
    assert best == 30000   # h0 to c0 (100), h1 to c1 (200); h2 (300) exceeds any store's 250
    assert list(owner) == [1, 0, -1, -1]
    for s in (0, 1):
        assert C.share_int[owner == s].sum() <= C.cap_int


def test_evaluate_no_open_sites_serves_nothing() -> None:
    owner, best = evaluate(with_network(case(), C_OP), [])
    assert best == 0 and list(owner) == [-1, -1, -1, -1]


def test_greedy_plan_adds_the_largest_marginal_site_first() -> None:
    C = with_network(case(), C_OP)
    assert greedy_plan(C, 1) == [2]        # c2: +400 against c1: +300
    assert greedy_plan(C, 2) == [2, 0]     # then c1's h2 (h1 is already served by c0)


def test_solve_plan_with_n_above_the_open_sites_is_infeasible() -> None:
    C = with_network(case(), C_OP)   # two open sites
    r = solve_plan(C, 3)
    assert (r.status, r.chosen) == ("INFEASIBLE", [])


def test_frozen_table_is_the_rows_03_area_ran_with() -> None:
    t = explore.table()
    assert list(t.columns) == ["Input", "Value", "Source", "Date", "Status"]
    assert list(t.Input) == [
        "Default scenario", "New stores, N", "Orders per store per day", "Capacity per store",
        "Brands and store counts", "Store placement", "Competitor reach", "Demand split",
        "Sites for new stores", "Assignment tie-break", "Integer scale", "Solver"]
    row = t.set_index("Input").Value
    assert f"multiplier {explore.MULTIPLIER}," in row["Default scenario"] and "1.8" not in row["Default scenario"]
    assert ", ".join(f"{b} {n}" for b, n in explore.BRAND_COUNTS.items()) in row["Brands and store counts"]


def test_the_live_assumptions_the_frozen_notebooks_read_still_have_their_stage_1_values() -> None:
    # explore reads these from assumptions (only MULTIPLIER and BRAND_COUNTS are frozen literals), so a stage 2+ change to one
    # would silently change 02-plan's and 03-area's inputs and explore.table()'s rows. Values from a49625c (stage 1 closed).
    stage_1: dict[str, float] = {
        "BLINKIT_ORDERS_Q2": 398.9e6, "BLINKIT_STORES": 2751, "Q2_DAYS": 92, "CAPACITY_FACTOR": 1.5, "N_AREA": 10, "N_SLICE": 3,
        "PICK_AND_PACK": 3, "PROMISE": 10, "SCALE": 100, "SEED": 2026, "SOLVER_SEED": 1, "TIME_LIMIT": 60, "WORKERS": 8}
    assert {name: getattr(explore, name) for name in stage_1} == stage_1
    assert explore.ORDERS_PER_STORE_DAY == pytest.approx(1576.106712183712) and explore.CAPACITY == pytest.approx(2364.160068275568)
