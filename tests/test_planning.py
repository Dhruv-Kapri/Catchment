import dataclasses
from pathlib import Path

import pandas as pd
import pytest

from catchment.assumptions import CAPACITY, ORDERS_PER_STORE_DAY
from catchment.planning import Inputs, Plan, Scenario, load_inputs, plan

OPS: float = ORDERS_PER_STORE_DAY
Pairs = dict[tuple[str, str], float]   # (site, hex) -> free-flow minutes


def make_inputs(hexes: dict[str, float], pairs: Pairs, sites: list[str], stores: int = 1, households: dict[str, float] | None = None) -> Inputs:
    """In-memory inputs. `sites` are in rank order. A hex "far", which no site reaches, tops the demand up to `stores` stores' worth,
    so the synthetic network has `stores` stores. A site reaching nothing within 3.89 free-flow min (the default reach) never holds a store."""
    far = stores * OPS - sum(hexes.values())
    assert far > -1e-6, "fixture demand exceeds the network's"
    demand = pd.DataFrame({"households": households or {h: d for h, d in hexes.items()}, "demand": hexes})
    if far > 1e-9:
        demand.loc["far"] = [far, far]
    candidates = pd.DataFrame({"rank": range(len(sites))}, index=pd.Index(sites))
    table = pd.DataFrame([(s, h, m) for (s, h), m in pairs.items()], columns=["candidate", "hex", "minutes"])
    return Inputs.from_frames(demand, candidates, table)


def same(a: Plan, b: Plan) -> bool:
    return dataclasses.replace(a, seconds=0.0) == dataclasses.replace(b, seconds=0.0)


def test_scenario_defaults_are_the_documented_ones() -> None:
    s = Scenario()
    assert (s.n_new, s.promise, s.multiplier, s.capacity, s.capture, s.competitor_density) == (10, 10, 1.8, 1.0, 1.0, 1.0)
    assert s.seed == 2026


def test_plan_picks_exactly_n_new_sites_none_on_a_store() -> None:
    sites = [f"S{i}" for i in range(8)]
    pairs: Pairs = {("S0", "A"): 1.0, **{(s, "A"): 5.0 for s in sites[1:]}}   # only S0 reaches anything at the default reach
    inputs = make_inputs({"A": 100.0}, pairs, sites)
    p = plan(inputs, Scenario(n_new=3, promise=15))
    assert p.network == {"Operator": ["S0"], "Competitor": []}
    assert len(p.sites) == 3 and len(set(p.sites)) == 3 and "S0" not in p.sites
    assert p.scenario.n_new == 3 and p.method == "greedy"


def test_plan_with_no_scenario_uses_the_defaults() -> None:
    sites = [f"S{i}" for i in range(12)]
    inputs = make_inputs({"A": 100.0}, {("S0", "A"): 1.0}, sites)
    p = plan(inputs)
    assert p.scenario == Scenario() and len(p.sites) == 10


def test_load_inputs_reads_what_the_build_wrote(tmp_path: Path) -> None:
    demand = pd.DataFrame({"households": [10.0, 20.0], "demand": [1.0, 2.0]}, index=pd.Index(["h0", "h1"], name="h3"))
    candidates = pd.DataFrame({"lat": [0.0, 0.0], "lon": [0.0, 0.0], "places": [5, 9], "rank": [1, 0]}, index=pd.Index(["h0", "h1"]))
    table = pd.DataFrame({"candidate": ["h1", "h0"], "hex": ["h0", "h1"], "minutes": [1.0, 2.0]})
    demand.to_parquet(tmp_path / "demand-r9.parquet")
    candidates.to_parquet(tmp_path / "candidates-r9-x30.parquet")
    table.to_parquet(tmp_path / "table-r9-x30.parquet")
    p = plan(load_inputs(9, 30, tmp_path), Scenario(n_new=1))
    assert p.sites == ["h0"]   # h1 (rank 0) reaches h0 (1 orders) and h0 reaches h1 (2 orders)


def test_capacity_binds_and_the_excess_is_lost() -> None:
    # S0 holds the only store; S1 reaches A, B, C at 5 min (only at a longer promise). At capacity 0.5x a store serves 1,182 orders: two of three hexes of 500.
    hexes = {"T": 10.0, "A": 500.0, "B": 500.0, "C": 500.0}
    pairs: Pairs = {("S0", "T"): 1.0, ("S1", "A"): 5.0, ("S1", "B"): 5.0, ("S1", "C"): 5.0}
    p = plan(make_inputs(hexes, pairs, ["S0", "S1"]), Scenario(n_new=1, promise=15, capacity=0.5))
    store = p.new_stores[0]
    assert p.sites == ["S1"] and store.orders <= 0.5 * CAPACITY
    assert store.orders == pytest.approx(1000) and p.lost_to_capacity == pytest.approx(500)
    assert p.demand_covered == pytest.approx(1010)
    assert p.demand_covered + p.lost_to_capacity + p.unreached == pytest.approx(OPS)   # the operator's total
    assert p.unreached == pytest.approx(OPS - 1510)


def test_a_hex_the_competitor_reaches_gives_the_operator_half_its_demand() -> None:
    # S0 and S1 hold one store each (one operator, one competitor, whichever way the seed falls); both reach H.
    sites = ["S0", "S1", "S2"]
    p = plan(make_inputs({"H": 1000.0}, {("S0", "H"): 1.0, ("S1", "H"): 1.0}, sites, stores=2), Scenario(n_new=1))
    assert sorted(sum(p.network.values(), [])) == ["S0", "S1"] and len(p.network["Operator"]) == 1
    assert p.demand_covered == pytest.approx(500)
    assert p.demand_covered + p.lost_to_capacity + p.unreached == pytest.approx(2 * OPS - 500)   # the operator's total share


def test_a_new_store_beside_an_existing_operator_store_cannibalises() -> None:
    # S0 (the operator's) serves W and A (A at 5 min). S2 wins fresh F; S1 sits 4 min from A, nearer than S0, so A moves to it.
    hexes = {"W": 300.0, "A": 500.0, "F": 200.0}
    pairs: Pairs = {("S0", "W"): 1.0, ("S0", "A"): 5.0, ("S1", "A"): 4.0, ("S2", "F"): 4.0}
    p = plan(make_inputs(hexes, pairs, ["S0", "S1", "S2"]), Scenario(n_new=2, promise=15))
    by_site = {n.site: n for n in p.new_stores}
    assert p.network["Operator"] == ["S0"] and set(by_site) == {"S1", "S2"}
    assert by_site["S1"].cannibalised == pytest.approx(500) and by_site["S1"].fresh == pytest.approx(0)
    assert by_site["S2"].fresh == pytest.approx(200) and by_site["S2"].cannibalised == pytest.approx(0)
    assert p.demand_covered == pytest.approx(1000)
    assert [n.site for n in p.new_stores] == p.sites


def test_greedy_prefers_demand_no_open_store_already_serves() -> None:
    # S1 reaches A (500) but S0 already serves it; S2 reaches F (200), unserved.
    hexes = {"W": 300.0, "A": 500.0, "F": 200.0}
    pairs: Pairs = {("S0", "W"): 1.0, ("S0", "A"): 1.0, ("S1", "A"): 4.0, ("S2", "F"): 4.0}
    p = plan(make_inputs(hexes, pairs, ["S0", "S1", "S2"]), Scenario(n_new=1, promise=15))
    assert p.sites == ["S2"] and p.demand_covered == pytest.approx(1000)


def test_households_covered_is_the_households_of_the_assigned_hexes() -> None:
    # At capacity 0.5x (1,182 orders) S0 serves A and B; D is reached but over capacity, C is out of reach.
    hexes = {"A": 100.0, "B": 200.0, "D": 1000.0, "C": 50.0}
    hh = {"A": 30.0, "B": 60.0, "D": 400.0, "C": 800.0}
    pairs: Pairs = {("S0", "A"): 1.0, ("S0", "B"): 2.0, ("S0", "D"): 3.0}
    p = plan(make_inputs(hexes, pairs, ["S0", "S1"], households=hh), Scenario(n_new=1, capacity=0.5))
    assert p.households_covered == pytest.approx(90) and p.lost_to_capacity == pytest.approx(1000)
    assert p.demand_covered == pytest.approx(300) and p.unreached == pytest.approx(OPS - 1300)


def test_default_network_is_57_stores_split_39_18() -> None:
    sites = [f"S{i}" for i in range(100)]
    hexes = {f"H{i}": 57 * OPS / 100 for i in range(100)}
    p = plan(make_inputs(hexes, {(f"S{i}", f"H{i}"): 1.0 for i in range(100)}, sites, stores=57), Scenario())
    assert (len(p.network["Operator"]), len(p.network["Competitor"])) == (39, 18)
    stores = sum(p.network.values(), [])
    assert len(set(stores)) == 57 and len(p.sites) == 10 and not set(p.sites) & set(stores)


def test_same_seed_same_network_and_plan_other_seed_other_network() -> None:
    sites = [f"S{i}" for i in range(100)]
    inputs = make_inputs({f"H{i}": 57 * OPS / 100 for i in range(100)}, {(f"S{i}", f"H{i}"): 1.0 for i in range(100)}, sites, stores=57)
    a, b = plan(inputs, Scenario(seed=1)), plan(inputs, Scenario(seed=1))
    assert same(a, b)
    assert plan(inputs, Scenario(seed=2)).network != a.network


def test_the_network_does_not_depend_on_the_other_levers() -> None:
    sites = [f"S{i}" for i in range(100)]
    inputs = make_inputs({f"H{i}": 57 * OPS / 100 for i in range(100)}, {(f"S{i}", f"H{i}"): 1.0 for i in range(100)}, sites, stores=57)
    base = plan(inputs, Scenario()).network
    assert plan(inputs, Scenario(promise=20, multiplier=1.0, capacity=2.0, capture=1.5, n_new=3)).network == base


def test_capture_scales_the_demand_covered_but_not_the_network() -> None:
    inputs = make_inputs({"A": 500.0}, {("S0", "A"): 1.0}, ["S0", "S1"])
    covered = {c: plan(inputs, Scenario(n_new=1, capture=c)).demand_covered for c in (0.5, 1.0, 1.5)}
    assert covered == pytest.approx({0.5: 250, 1.0: 500, 1.5: 750})


def test_promise_and_multiplier_decide_reach_inclusive_of_the_limit() -> None:
    # S0 reaches W at 1 min (so it holds the store) and A at 5 min: 5 x 1.0 + 3 = 8 is within an 8 min promise, 5 x 1.1 + 3 is not.
    inputs = make_inputs({"W": 100.0, "A": 200.0}, {("S0", "W"): 1.0, ("S0", "A"): 5.0}, ["S0", "S1"])
    assert plan(inputs, Scenario(n_new=1, promise=8, multiplier=1.0)).demand_covered == pytest.approx(300)
    assert plan(inputs, Scenario(n_new=1, promise=8, multiplier=1.1)).demand_covered == pytest.approx(100)
    assert plan(inputs, Scenario(n_new=1, promise=15, multiplier=2.5)).demand_covered == pytest.approx(100)   # 5 x 2.5 + 3 = 15.5 > 15: only W


LEVERS: list[tuple[str, float, float, str]] = [   # lever, below the range, above it, the range as the message states it
    ("n_new", 0, 21, "1-20"), ("promise", 7, 21, "8-20"), ("multiplier", 0.9, 2.6, "1-2.5"),
    ("capacity", 0.4, 2.1, "0.5-2"), ("capture", 0.4, 1.6, "0.5-1.5"), ("competitor_density", 0.9, 1.1, "1-1"),
]


@pytest.mark.parametrize("lever,low,high,span", LEVERS)
def test_an_out_of_range_lever_is_refused_naming_the_lever_and_its_range(lever: str, low: float, high: float, span: str) -> None:
    inputs = make_inputs({"A": 100.0}, {("S0", "A"): 1.0}, ["S0", "S1"])
    for bad in (low, high):
        with pytest.raises(ValueError, match=f"{lever} {bad:g} is outside the lever range {span}"):
            plan(inputs, Scenario(**{lever: bad}))


@pytest.mark.parametrize("lever,low,high,span", LEVERS)
def test_the_ends_of_a_lever_range_are_allowed(lever: str, low: float, high: float, span: str) -> None:
    lo, hi = (float(x) for x in span.split("-"))
    for end in (lo, hi):
        assert getattr(Scenario(**{lever: int(end) if lever in ("n_new", "promise") else end}), lever) == end


def test_the_number_of_new_stores_must_be_an_integer() -> None:
    with pytest.raises(ValueError, match="n_new"):
        Scenario(n_new=2.5)  # type: ignore[arg-type]


def test_an_unknown_method_is_refused() -> None:
    with pytest.raises(ValueError, match="cp-sat"):
        plan(make_inputs({"A": 100.0}, {("S0", "A"): 1.0}, ["S0", "S1"]), Scenario(n_new=1), method="cp-sat")  # type: ignore[arg-type]


def test_more_new_stores_than_open_sites_is_refused() -> None:
    inputs = make_inputs({"A": 100.0}, {("S0", "A"): 1.0}, ["S0", "S1", "S2"])
    with pytest.raises(ValueError, match="open candidate sites"):
        plan(inputs, Scenario(n_new=3))


def test_a_network_that_cannot_be_placed_is_refused() -> None:
    # Two stores' worth of demand, but only one site reaches any of it at the default scenario.
    inputs = make_inputs({"A": 100.0}, {("S0", "A"): 1.0, ("S1", "A"): 6.0}, ["S0", "S1", "S2"], stores=2)
    with pytest.raises(ValueError, match="candidate sites that reach"):
        plan(inputs, Scenario(n_new=1))
