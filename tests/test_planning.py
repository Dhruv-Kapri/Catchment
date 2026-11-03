import dataclasses
import time
from itertools import chain
from pathlib import Path

import numpy as np
import pandas as pd
import pytest
from ortools.sat.python import cp_model

from catchment import planning
from catchment.assumptions import CAPACITY, ORDERS_PER_STORE_DAY, PICK_AND_PACK
from catchment.planning import (
    METHODS,
    Inputs,
    Method,
    Plan,
    Scenario,
    load_inputs,
    plan,
)

OPS: float = ORDERS_PER_STORE_DAY
Pairs = dict[tuple[str, str], float]   # (site, hex) -> free-flow minutes
CPSAT: list[Method] = ["cpsat", "cpsat-from-greedy"]


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
    zero = {"seconds": 0.0, "build_seconds": 0.0, "solve_seconds": 0.0}
    return dataclasses.replace(a, **zero) == dataclasses.replace(b, **zero)


def test_scenario_defaults_are_the_documented_ones() -> None:
    s = Scenario()
    assert (s.n_new, s.promise, s.multiplier, s.capacity, s.capture, s.competitor_density) == (10, 10, 1.8, 1.0, 1.0, 1.0)
    assert s.seed == 2026


LEVERS: list[tuple[str, float, float, str]] = [   # lever, below the range, above it, the range as the message states it
    ("n_new", 0, 21, "1-20"), ("promise", 7, 17, "8-16"), ("multiplier", 0.9, 2.6, "1-2.5"),
    ("capacity", 0.4, 2.1, "0.5-2"), ("capture", 0.4, 1.6, "0.5-1.5"), ("competitor_density", -0.25, 2.25, "0-2"),
]


@pytest.mark.parametrize("lever,low,high,span", LEVERS)
def test_an_out_of_range_lever_is_refused_naming_the_lever_and_its_range(lever: str, low: float, high: float, span: str) -> None:
    for bad in (low, high):
        with pytest.raises(ValueError, match=f"{lever} {bad:g} is outside the lever range {span}"):
            Scenario(**{lever: bad})


@pytest.mark.parametrize("lever,low,high,span", LEVERS)
def test_the_ends_of_a_lever_range_are_allowed(lever: str, low: float, high: float, span: str) -> None:
    lo, hi = (float(x) for x in span.split("-"))
    for end in (lo, hi):
        assert getattr(Scenario(**{lever: int(end) if lever in ("n_new", "promise") else end}), lever) == end


@pytest.mark.parametrize("lever, value", [("n_new", 2.5), ("n_new", True), ("promise", 8.5), ("promise", True)])
def test_the_number_of_new_stores_and_the_promise_must_be_whole_numbers(lever: str, value: float) -> None:
    with pytest.raises(TypeError, match=f"{lever} .* must be a whole number"):
        Scenario(**{lever: value})


def test_numpy_whole_numbers_are_accepted_and_stored_as_plain_ints() -> None:
    s = Scenario(n_new=np.int64(3), promise=np.int32(12))  # type: ignore[arg-type]
    assert (s.n_new, s.promise) == (3, 12) and type(s.n_new) is int and type(s.promise) is int
    for bad in (10.0, np.float64(10.0), np.bool_(True)):
        with pytest.raises(TypeError, match="must be a whole number"):
            Scenario(promise=bad)  # type: ignore[arg-type]


def test_inputs_hold_positional_arrays_with_the_sites_in_rank_order() -> None:
    demand = pd.DataFrame({"households": [10.0, 20.0], "demand": [1.0, 2.0]}, index=pd.Index(["h0", "h1"], name="h3"))
    candidates = pd.DataFrame({"rank": [1, 0]}, index=pd.Index(["h0", "h1"]))
    table = pd.DataFrame({"candidate": ["h1", "h0"], "hex": ["h0", "h1"], "minutes": [1.0, 2.0]})
    i = Inputs.from_frames(demand, candidates, table)
    assert list(i.site_ids) == ["h1", "h0"] and list(i.hex_ids) == ["h0", "h1"]
    assert list(i.demand) == [1.0, 2.0] and list(i.households) == [10.0, 20.0]
    assert list(i.pair_site) == [0, 1] and list(i.pair_hex) == [0, 1] and list(i.pair_min) == [1.0, 2.0]


def test_a_travel_time_table_naming_an_unknown_site_or_hex_is_refused() -> None:
    demand = pd.DataFrame({"households": [10.0], "demand": [1.0]}, index=pd.Index(["h0"]))
    candidates = pd.DataFrame({"rank": [0]}, index=pd.Index(["h0"]))
    for bad in (pd.DataFrame({"candidate": ["zz"], "hex": ["h0"], "minutes": [1.0]}), pd.DataFrame({"candidate": ["h0"], "hex": ["zz"], "minutes": [1.0]})):
        with pytest.raises(ValueError, match="missing from the candidates or the demand table"):
            Inputs.from_frames(demand, candidates, bad)


def test_an_unknown_method_is_refused() -> None:
    with pytest.raises(ValueError, match="cp-sat"):
        plan(make_inputs({"A": 100.0}, {("S0", "A"): 1.0}, ["S0", "S1"]), Scenario(n_new=1), method="cp-sat")  # type: ignore[arg-type]


def test_plan_with_no_scenario_uses_the_defaults() -> None:
    sites = [f"S{i}" for i in range(12)]
    inputs = make_inputs({"A": 100.0}, {("S0", "A"): 1.0}, sites)
    p = plan(inputs)
    assert p.scenario == Scenario() and len(p.sites) == 10


def test_plan_picks_exactly_n_new_sites_none_on_a_store() -> None:
    sites = [f"S{i}" for i in range(8)]
    pairs: Pairs = {("S0", "A"): 1.0, **{(s, "A"): 5.0 for s in sites[1:]}}   # only S0 reaches anything at the default reach
    inputs = make_inputs({"A": 100.0}, pairs, sites)
    p = plan(inputs, Scenario(n_new=3, promise=15))
    assert p.network == {"Operator": ["S0"], "Competitor": []}
    assert len(p.sites) == 3 and len(set(p.sites)) == 3 and "S0" not in p.sites
    assert p.scenario.n_new == 3 and p.method == "greedy"


def test_greedy_prefers_demand_no_open_store_already_serves() -> None:
    # S1 reaches A (500) but S0 already serves it; S2 reaches F (200), unserved.
    hexes = {"W": 300.0, "A": 500.0, "F": 200.0}
    pairs: Pairs = {("S0", "W"): 1.0, ("S0", "A"): 1.0, ("S1", "A"): 4.0, ("S2", "F"): 4.0}
    p = plan(make_inputs(hexes, pairs, ["S0", "S1", "S2"]), Scenario(n_new=1, promise=15))
    assert p.sites == ["S2"] and p.demand_covered == pytest.approx(1000)


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


def test_a_hex_the_competitor_reaches_gives_the_operator_half_its_demand() -> None:
    # S0 and S1 hold one store each (one operator, one competitor, whichever way the seed falls); both reach H.
    sites = ["S0", "S1", "S2"]
    p = plan(make_inputs({"H": 1000.0}, {("S0", "H"): 1.0, ("S1", "H"): 1.0}, sites, stores=2), Scenario(n_new=1))
    assert sorted(chain.from_iterable(p.network.values())) == ["S0", "S1"] and len(p.network["Operator"]) == 1
    assert p.demand_covered == pytest.approx(500)
    assert p.demand_covered + p.lost_to_capacity + p.unreached == pytest.approx(2 * OPS - 500)   # the operator's total share


def test_capacity_binds_and_the_excess_is_lost() -> None:
    # S0 holds the only store; S1 reaches A, B, C at 5 min (only at a longer promise). At capacity 0.5x a store serves 1,182 orders: two of three hexes of 500.
    hexes = {"T": 10.0, "A": 500.0, "B": 500.0, "C": 500.0}
    pairs: Pairs = {("S0", "T"): 1.0, ("S1", "A"): 5.0, ("S1", "B"): 5.0, ("S1", "C"): 5.0}
    p = plan(make_inputs(hexes, pairs, ["S0", "S1"]), Scenario(n_new=1, promise=15, capacity=0.5))
    store = p.new_stores[0]
    assert p.sites == ["S1"] and store.orders <= 0.5 * CAPACITY
    assert store.orders == pytest.approx(1000)
    assert p.demand_covered == pytest.approx(1010)
    assert p.lost_to_capacity == pytest.approx(500)
    assert p.demand_covered + p.lost_to_capacity + p.unreached == pytest.approx(OPS)   # the operator's total
    assert p.unreached == pytest.approx(OPS - 1510)


def test_a_hex_that_fits_a_store_exactly_is_not_refused_for_float_noise() -> None:
    # 148.89 + 277.56 + 755.63003... is the capacity at 0.5x to the last digit, but summed in float it lands a hair above it.
    a, b = 148.89, 277.56
    c = 0.5 * CAPACITY - a - b
    assert (a + b) + c > 0.5 * CAPACITY
    p = plan(make_inputs({"A": a, "B": b, "C": c}, {("S0", "A"): 1.0, ("S0", "B"): 1.0, ("S0", "C"): 1.0}, ["S0", "S1"]), Scenario(n_new=1, capacity=0.5))
    assert p.lost_to_capacity == 0 and p.demand_covered == pytest.approx(a + b + c)


def test_greedy_values_a_site_at_no_more_than_one_store_can_serve() -> None:
    # S1 reaches A-E (1,250 orders) and S2 reaches A-F (1,500), both above the 1,182 a store serves at capacity 0.5x: tied, so the first, S1.
    hexes = {"T": 10.0, **{h: 250.0 for h in "ABCDEF"}}
    pairs: Pairs = {("S0", "T"): 1.0, **{("S1", h): 5.0 for h in "ABCDE"}, **{("S2", h): 5.0 for h in "ABCDEF"}}
    p = plan(make_inputs(hexes, pairs, ["S0", "S1", "S2"]), Scenario(n_new=1, promise=15, capacity=0.5))
    assert p.sites == ["S1"]


def test_households_covered_is_the_households_of_the_assigned_hexes() -> None:
    # At capacity 0.5x (1,182 orders) S0 serves A and B; D is reached but over capacity, C is out of reach.
    hexes = {"A": 100.0, "B": 200.0, "D": 1000.0, "C": 50.0}
    hh = {"A": 30.0, "B": 60.0, "D": 400.0, "C": 800.0}
    pairs: Pairs = {("S0", "A"): 1.0, ("S0", "B"): 2.0, ("S0", "D"): 3.0}
    p = plan(make_inputs(hexes, pairs, ["S0", "S1"], households=hh), Scenario(n_new=1, capacity=0.5))
    assert p.households_covered == pytest.approx(90) and p.lost_to_capacity == pytest.approx(1000)
    assert p.demand_covered == pytest.approx(300) and p.unreached == pytest.approx(OPS - 1300)


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


def test_default_network_is_57_stores_split_39_18() -> None:
    sites = [f"S{i}" for i in range(100)]
    hexes = {f"H{i}": 57 * OPS / 100 for i in range(100)}
    p = plan(make_inputs(hexes, {(f"S{i}", f"H{i}"): 1.0 for i in range(100)}, sites, stores=57), Scenario())
    assert (len(p.network["Operator"]), len(p.network["Competitor"])) == (39, 18)
    stores = list(chain.from_iterable(p.network.values()))
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
    assert plan(inputs, Scenario(promise=16, multiplier=1.0, capacity=2.0, capture=1.5, n_new=3)).network == base


def test_more_new_stores_than_open_sites_is_refused() -> None:
    inputs = make_inputs({"A": 100.0}, {("S0", "A"): 1.0}, ["S0", "S1", "S2"])
    with pytest.raises(ValueError, match="open candidate sites"):
        plan(inputs, Scenario(n_new=3))


def test_a_network_that_cannot_be_placed_is_refused() -> None:
    # Two stores' worth of demand, but only one site reaches any of it at the default scenario.
    inputs = make_inputs({"A": 100.0}, {("S0", "A"): 1.0, ("S1", "A"): 6.0}, ["S0", "S1", "S2"], stores=2)
    with pytest.raises(ValueError, match="candidate sites that reach"):
        plan(inputs, Scenario(n_new=1))


def test_load_inputs_reads_what_the_build_wrote(tmp_path: Path) -> None:
    demand = pd.DataFrame({"households": [10.0, 20.0], "demand": [1.0, 2.0]}, index=pd.Index(["h0", "h1"], name="h3"))
    candidates = pd.DataFrame({"lat": [0.0, 0.0], "lon": [0.0, 0.0], "places": [5, 9], "rank": [1, 0]}, index=pd.Index(["h0", "h1"]))
    table = pd.DataFrame({"candidate": ["h1", "h0"], "hex": ["h0", "h1"], "minutes": [1.0, 2.0]})
    demand.to_parquet(tmp_path / "demand-r9.parquet")
    candidates.to_parquet(tmp_path / "candidates-r9-x30.parquet")
    table.to_parquet(tmp_path / "table-r9-x30.parquet")
    p = plan(load_inputs(9, 30, tmp_path), Scenario(n_new=1))
    assert p.sites == ["h0"]   # h1 (rank 0) reaches h0 (1 orders) and h0 reaches h1 (2 orders)


def test_plan_without_inputs_loads_them_and_seconds_leave_the_load_out(monkeypatch: pytest.MonkeyPatch) -> None:
    inputs = make_inputs({"A": 100.0}, {("S0", "A"): 1.0}, [f"S{i}" for i in range(12)])

    def slow_load() -> Inputs:
        time.sleep(0.3)
        return inputs
    monkeypatch.setattr(planning, "load_inputs", slow_load)
    p = plan()
    assert same(p, plan(inputs)) and p.seconds < 0.3


def random_inputs(seed: int, n_sites: int = 30, n_hexes: int = 60) -> Inputs:
    """Whole-number demand (so every sum is exact), minutes in half-minute steps (so there are ties), a few reachable sites per hex."""
    rng = np.random.default_rng(seed)
    hexes = {f"H{i}": float(rng.integers(50, 300)) for i in range(n_hexes)}
    pairs: Pairs = {}
    for h in hexes:
        for s in rng.choice(n_sites, size=6, replace=False).tolist():
            pairs[(f"S{s}", h)] = float(rng.integers(1, 25)) / 2
    return make_inputs(hexes, pairs, [f"S{i}" for i in range(n_sites)], stores=9, households={h: d / 3 for h, d in hexes.items()})


def reference_greedy(inputs: Inputs, scenario: Scenario, network: dict[str, list[str]]) -> tuple[list[str], float, list[float]]:
    """The greedy written the slow, obvious way: every step re-assigns every hex and recomputes every candidate's gain from scratch.
    Returns the picked sites, the demand covered and the orders of each new store."""
    position: dict[str, int] = {str(s): i for i, s in enumerate(inputs.site_ids)}
    reach: list[tuple[int, int, float]] = [(s, h, m) for s, h, m in zip(inputs.pair_site.tolist(), inputs.pair_hex.tolist(), inputs.pair_min.tolist())
                                           if m * scenario.multiplier + PICK_AND_PACK <= scenario.promise + planning.TOL]
    operator, competitor = ({position[s] for s in network[b]} for b in ("Operator", "Competitor"))
    rival: set[int] = {h for s, h, _ in reach if s in competitor}
    share: list[float] = [d * scenario.capture / (2 if h in rival else 1) for h, d in enumerate(inputs.demand.tolist())]
    capacity: float = scenario.capacity * CAPACITY

    def assigned(stores: set[int]) -> dict[int, int]:
        owner: dict[int, int] = {}
        load: dict[int, float] = {}
        for s, h, _ in sorted((p for p in reach if p[0] in stores), key=lambda p: (p[2], p[0], p[1])):
            if h not in owner and load.get(s, 0.0) + share[h] <= capacity + planning.TOL:
                owner[h], load[s] = s, load.get(s, 0.0) + share[h]
        return owner

    stores: set[int] = set(operator)
    picked: list[int] = []
    for _ in range(scenario.n_new):
        owner = assigned(stores)
        gain = {s: min(sum(share[h] for s2, h, _ in reach if s2 == s and h not in owner), capacity) for s in range(len(inputs.site_ids))}
        best = max((s for s in gain if s not in operator | competitor | set(picked)), key=lambda s: gain[s])   # first on ties
        picked.append(best)
        stores.add(best)
    owner = assigned(stores)
    return ([str(inputs.site_ids[s]) for s in picked], sum(share[h] for h in owner), [sum(share[h] for h, s in owner.items() if s == p) for p in picked])


@pytest.mark.parametrize("seed", [0, 1, 2, 3, 4, 15])   # 4 and 15 at capacity 0.5x have a hex losing its store when another opens
@pytest.mark.parametrize("promise", [12, 16])   # the top of the range
@pytest.mark.parametrize("capacity", [0.5, 1.0, 2.0])
def test_the_greedy_matches_a_from_scratch_reference(seed: int, promise: int, capacity: float) -> None:
    inputs = random_inputs(seed)
    scenario = Scenario(n_new=15, promise=promise, capacity=capacity, seed=seed)
    p = plan(inputs, scenario)
    sites, covered, orders = reference_greedy(inputs, scenario, p.network)
    assert p.sites == sites and p.demand_covered == pytest.approx(covered)
    assert [n.orders for n in p.new_stores] == pytest.approx(orders)


def test_the_reference_fixtures_do_bind_capacity() -> None:
    plans = [plan(random_inputs(seed), Scenario(n_new=15, promise=12, capacity=0.5, seed=seed)) for seed in range(5)]
    assert any(p.lost_to_capacity > 0 for p in plans)


def twin_inputs(seed: int, n_twins: int = 15, n_hexes: int = 60) -> Inputs:
    """Fractional demand, and sites in twins (S{i} and T{i}) that reach the same hexes in the same minutes, so a from-scratch gain ties
    them exactly and only the lower rank (S{i}) may be picked; a gain updated by float deltas must not break those ties by rounding noise."""
    rng = np.random.default_rng(seed)
    hexes = {f"H{i}": float(rng.uniform(50, 300)) for i in range(n_hexes)}
    pairs: Pairs = {}
    for h in hexes:
        for i in rng.choice(n_twins, size=4, replace=False).tolist():
            m = float(rng.integers(1, 25)) / 2
            pairs[(f"S{i}", h)], pairs[(f"T{i}", h)] = m, m
    return make_inputs(hexes, pairs, [f"S{i}" for i in range(n_twins)] + [f"T{i}" for i in range(n_twins)], stores=9)


@pytest.mark.parametrize("seed", range(12))
@pytest.mark.parametrize("capacity", [0.5, 1.0])
def test_the_greedy_breaks_exact_ties_by_rank_on_fractional_demand(seed: int, capacity: float) -> None:
    inputs = twin_inputs(seed)
    scenario = Scenario(n_new=12, promise=12, capacity=capacity, seed=seed)
    p = plan(inputs, scenario)
    sites, covered, _ = reference_greedy(inputs, scenario, p.network)
    assert p.sites == sites and p.demand_covered == pytest.approx(covered)


# CP-SAT: both variants, and the metrics every method reports


@pytest.mark.parametrize("method", CPSAT)
def test_cpsat_finds_the_optimum_where_greedy_does_not(method: Method) -> None:
    # G reaches b, c and g (700), the biggest site, so greedy takes it first; P reaches a, b and Q reaches c, d (600 each).
    # Two stores: P + Q cover a-d (1,200); G + either covers 1,000. Unique optimum. S0 holds the one existing store (T, 10 orders).
    hexes = {"T": 10.0, "a": 300.0, "b": 300.0, "c": 300.0, "d": 300.0, "g": 100.0}
    pairs: Pairs = {("S0", "T"): 1.0, ("G", "b"): 5.0, ("G", "c"): 5.0, ("G", "g"): 5.0,
                    ("P", "a"): 5.0, ("P", "b"): 5.0, ("Q", "c"): 5.0, ("Q", "d"): 5.0}
    inputs, scenario = make_inputs(hexes, pairs, ["S0", "G", "P", "Q"]), Scenario(n_new=2, promise=15)
    assert sorted(plan(inputs, scenario).sites) == ["G", "P"] and plan(inputs, scenario).demand_covered == pytest.approx(1010)
    p = plan(inputs, scenario, method)
    assert sorted(p.sites) == ["P", "Q"] and p.method == method
    assert p.demand_covered == pytest.approx(1210) and p.objective == pytest.approx(1210)
    assert p.status == "OPTIMAL" and p.gap == 0 and p.bound == pytest.approx(p.objective)


def test_greedy_reports_a_heuristic_status_and_no_bound() -> None:
    p = plan(make_inputs({"A": 500.0}, {("S0", "A"): 1.0}, ["S0", "S1"]), Scenario(n_new=1))
    assert p.status == "HEURISTIC" and p.bound is None and p.gap is None
    assert p.objective == p.demand_covered == pytest.approx(500)


@pytest.mark.parametrize("method", [*CPSAT, "greedy"])
def test_the_times_are_reported_and_add_up(method: Method) -> None:
    p = plan(random_inputs(0), Scenario(n_new=4, promise=12, seed=0), method)
    assert p.build_seconds > 0 and p.solve_seconds > 0   # both phases do real work
    assert p.seconds >= p.build_seconds + p.solve_seconds - 1e-6   # the metrics come on top


@pytest.mark.parametrize("seed", [0, 1, 2, 3, 4, 15])
@pytest.mark.parametrize("promise", [12, 16])   # the top of the range
@pytest.mark.parametrize("capacity", [0.5, 1.0, 2.0])
def test_cpsat_is_never_below_greedy(seed: int, promise: int, capacity: float) -> None:
    inputs, scenario = random_inputs(seed), Scenario(n_new=5, promise=promise, capacity=capacity, seed=seed)
    greedy = plan(inputs, scenario)
    hinted = plan(inputs, scenario, "cpsat-from-greedy")
    assert hinted.demand_covered >= greedy.demand_covered - 1e-6 and hinted.objective >= greedy.objective - 1e-6
    alone = plan(inputs, scenario, "cpsat")
    assert alone.status in ("OPTIMAL", "FEASIBLE")
    if alone.status == "OPTIMAL":
        assert alone.demand_covered >= greedy.demand_covered - 1e-6
        assert hinted.status == "OPTIMAL" and hinted.objective == pytest.approx(alone.objective)


def max_served(inputs: Inputs, scenario: Scenario, network: dict[str, list[str]], stores: list[str]) -> float:
    """The most orders the operator's `stores` can serve within capacity, from a plain pair model: one boolean per (store, hex) pair,
    each hex at most once, each store at most its capacity. Written apart from planning's model, on the same shares (ADR 0001)."""
    site = {str(s): i for i, s in enumerate(inputs.site_ids)}
    scale = 100
    pairs = [(s, h) for s, h, m in zip(inputs.pair_site.tolist(), inputs.pair_hex.tolist(), inputs.pair_min.tolist())
             if m * scenario.multiplier + PICK_AND_PACK <= scenario.promise + planning.TOL]
    rival = {h for s, h in pairs if s in {site[c] for c in network["Competitor"]}}
    share = [round(d * scenario.capture / (2 if h in rival else 1) * scale) for h, d in enumerate(inputs.demand.tolist())]
    mine = {site[s] for s in stores}
    model = cp_model.CpModel()
    x = {(s, h): model.NewBoolVar(f"x{s}_{h}") for s, h in pairs if s in mine}
    for h in {h for _, h in x}:
        model.AddAtMostOne([v for (_, h2), v in x.items() if h2 == h])
    for s in mine:
        model.Add(sum(share[h] * v for (s2, h), v in x.items() if s2 == s) <= round(scenario.capacity * CAPACITY * scale))
    model.Maximize(sum(share[h] * v for (_, h), v in x.items()))
    solver = cp_model.CpSolver()
    assert solver.Solve(model) == cp_model.OPTIMAL
    return solver.ObjectiveValue() / scale


@pytest.mark.parametrize("method", CPSAT)
@pytest.mark.parametrize("seed", [0, 1, 2, 3, 4, 15])
@pytest.mark.parametrize("capacity", [0.5, 1.0])
def test_the_metrics_match_an_independent_evaluation_of_the_same_stores(method: Method, seed: int, capacity: float) -> None:
    inputs, scenario = random_inputs(seed), Scenario(n_new=4, promise=12, capacity=capacity, seed=seed)
    p = plan(inputs, scenario, method)
    assert p.status == "OPTIMAL"
    assert p.demand_covered == pytest.approx(max_served(inputs, scenario, p.network, [*p.network["Operator"], *p.sites]), abs=0.01)
    assert p.objective == pytest.approx(p.demand_covered, abs=0.01)
    assert sum(n.orders for n in p.new_stores) <= p.demand_covered + 1e-6


@pytest.mark.parametrize("method", CPSAT)
def test_cpsat_capacity_binds_and_the_excess_is_lost(method: Method) -> None:
    hexes = {"T": 10.0, "A": 500.0, "B": 500.0, "C": 500.0}
    pairs: Pairs = {("S0", "T"): 1.0, ("S1", "A"): 5.0, ("S1", "B"): 5.0, ("S1", "C"): 5.0}
    p = plan(make_inputs(hexes, pairs, ["S0", "S1"]), Scenario(n_new=1, promise=15, capacity=0.5), method)
    assert p.sites == ["S1"] and p.new_stores[0].orders == pytest.approx(1000) and p.new_stores[0].orders <= 0.5 * CAPACITY
    assert p.demand_covered == pytest.approx(1010) and p.objective == pytest.approx(1010) and p.lost_to_capacity == pytest.approx(500)
    assert p.demand_covered + p.lost_to_capacity + p.unreached == pytest.approx(OPS)


@pytest.mark.parametrize("method", CPSAT)
def test_cpsat_serves_the_best_hexes_within_capacity_not_the_nearest_first(method: Method) -> None:
    # S0 (capacity 1,182 at 0.5x) reaches A (100), B (200) and D (1,000), nearest first. Greedy's walk takes A and B and loses D;
    # the best within capacity is A + D (1,100), losing B.
    hexes = {"A": 100.0, "B": 200.0, "D": 1000.0, "C": 50.0}
    hh = {"A": 30.0, "B": 60.0, "D": 400.0, "C": 800.0}
    pairs: Pairs = {("S0", "A"): 1.0, ("S0", "B"): 2.0, ("S0", "D"): 3.0}
    p = plan(make_inputs(hexes, pairs, ["S0", "S1"], households=hh), Scenario(n_new=1, capacity=0.5), method)
    assert p.demand_covered == pytest.approx(1100) and p.lost_to_capacity == pytest.approx(200) and p.unreached == pytest.approx(OPS - 1300)
    assert p.households_covered == pytest.approx(430) and p.status == "OPTIMAL"


@pytest.mark.parametrize("method", CPSAT)
def test_cpsat_a_new_store_beside_an_existing_operator_store_cannibalises(method: Method) -> None:
    hexes = {"W": 300.0, "A": 500.0, "F": 200.0}
    pairs: Pairs = {("S0", "W"): 1.0, ("S0", "A"): 5.0, ("S1", "A"): 4.0, ("S2", "F"): 4.0}
    p = plan(make_inputs(hexes, pairs, ["S0", "S1", "S2"]), Scenario(n_new=2, promise=15), method)
    by_site = {n.site: n for n in p.new_stores}
    assert set(by_site) == {"S1", "S2"} and [n.site for n in p.new_stores] == p.sites
    assert by_site["S1"].cannibalised == pytest.approx(500) and by_site["S1"].fresh == pytest.approx(0)
    assert by_site["S2"].fresh == pytest.approx(200) and by_site["S2"].cannibalised == pytest.approx(0)
    assert p.demand_covered == pytest.approx(1000)


@pytest.mark.parametrize("method", CPSAT)
def test_cpsat_a_hex_the_competitor_reaches_gives_the_operator_half_its_demand(method: Method) -> None:
    sites = ["S0", "S1", "S2"]
    p = plan(make_inputs({"H": 1000.0}, {("S0", "H"): 1.0, ("S1", "H"): 1.0}, sites, stores=2), Scenario(n_new=1), method)
    assert p.demand_covered == pytest.approx(500)
    assert p.demand_covered + p.lost_to_capacity + p.unreached == pytest.approx(2 * OPS - 500)


@pytest.mark.parametrize("method", CPSAT)
def test_cpsat_picks_exactly_n_new_sites_none_on_a_store_in_rank_order(method: Method) -> None:
    sites = [f"S{i}" for i in range(8)]
    pairs: Pairs = {("S0", "A"): 1.0, **{(s, "A"): 5.0 for s in sites[1:]}}
    p = plan(make_inputs({"A": 100.0}, pairs, sites), Scenario(n_new=3, promise=15), method)
    assert len(p.sites) == 3 and len(set(p.sites)) == 3 and "S0" not in p.sites and p.sites == sorted(p.sites)


def test_unchosen_free_sites_still_serve_what_they_reach_in_the_assignment() -> None:
    # N = 1 and S1 reaches A, S2 reaches B; one store must be built, but the model's objective alone would not decide which hexes
    # a chosen site serves: whatever it reaches, within capacity, is assigned to it.
    hexes = {"T": 10.0, "A": 300.0, "B": 200.0}
    pairs: Pairs = {("S0", "T"): 1.0, ("S1", "A"): 5.0, ("S2", "B"): 5.0}
    p = plan(make_inputs(hexes, pairs, ["S0", "S1", "S2"]), Scenario(n_new=1, promise=15), "cpsat")
    assert p.sites == ["S1"] and p.new_stores[0].orders == pytest.approx(300) and p.demand_covered == pytest.approx(310)


def no_solution(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(cp_model.CpSolver, "Solve", lambda self, model: cp_model.UNKNOWN)


def test_cpsat_that_finds_no_solution_returns_an_unknown_plan_of_the_existing_network(monkeypatch: pytest.MonkeyPatch) -> None:
    # #27/#33: every method returns a Plan. No new sites; the metrics are the existing operator stores' alone: greedy's coverage less
    # what its new stores won fresh (their cannibalised orders were the existing stores' already).
    inputs, scenario = random_inputs(0), Scenario(n_new=4, promise=12, seed=0)
    greedy = plan(inputs, scenario)
    no_solution(monkeypatch)
    p = plan(inputs, scenario, "cpsat")
    assert p.status == "UNKNOWN" and p.sites == [] and p.new_stores == [] and p.network == greedy.network
    assert p.objective is None and p.bound is None and p.gap is None
    assert p.demand_covered == pytest.approx(greedy.demand_covered - sum(s.fresh for s in greedy.new_stores))
    assert 0 < p.slow_traffic_coverage <= p.demand_covered < greedy.demand_covered


def test_cpsat_from_greedy_with_no_solution_keeps_greedys_plan(monkeypatch: pytest.MonkeyPatch) -> None:
    inputs, scenario = random_inputs(0), Scenario(n_new=4, promise=12, seed=0)
    greedy = plan(inputs, scenario)
    no_solution(monkeypatch)
    p = plan(inputs, scenario, "cpsat-from-greedy")
    assert p.sites == greedy.sites and p.demand_covered == pytest.approx(greedy.demand_covered)
    assert p.method == "cpsat-from-greedy" and p.status == "HEURISTIC"   # greedy's plan, not CP-SAT's stopped early
    assert p.objective == pytest.approx(greedy.objective, abs=0.05) and p.bound is None and p.gap is None


def test_slow_traffic_coverage_equals_the_demand_covered_when_nothing_is_near_the_promise() -> None:
    # Promise 15, multiplier 1.0: reach is <= 12 min, at 1.25x <= 9.6 min. Every reachable pair is within 4 min.
    hexes = {"W": 100.0, "A": 200.0, "F": 300.0}
    pairs: Pairs = {("S0", "W"): 1.0, ("S0", "A"): 4.0, ("S1", "F"): 3.0}
    p = plan(make_inputs(hexes, pairs, ["S0", "S1"]), Scenario(n_new=1, promise=15, multiplier=1.0))
    assert p.demand_covered == pytest.approx(600) and p.slow_traffic_coverage == pytest.approx(600)


def test_slow_traffic_coverage_holds_the_competitor_split_of_a_hex() -> None:
    # S0 and S1 hold one store each; both reach H (1 min), so the operator's share is half of 1,000 at either multiplier.
    sites = ["S0", "S1", "S2"]
    p = plan(make_inputs({"H": 1000.0}, {("S0", "H"): 1.0, ("S1", "H"): 1.0}, sites, stores=2), Scenario(n_new=1))
    assert p.demand_covered == pytest.approx(500) and p.slow_traffic_coverage == pytest.approx(500)


@pytest.mark.parametrize("seed", range(5))
@pytest.mark.parametrize("capacity", [0.5, 1.0])   # seed 1 at 0.5x, promise 12, loses orders to capacity
def test_slow_traffic_coverage_is_never_more_than_the_demand_covered_across_promises_and_capacities(seed: int, capacity: float) -> None:
    plans = [plan(random_inputs(seed), Scenario(n_new=15, promise=promise, capacity=capacity, seed=seed)) for promise in (8, 12, 16)]
    assert all(p.slow_traffic_coverage <= p.demand_covered + 1e-6 for p in plans)
    assert any(p.slow_traffic_coverage < p.demand_covered for p in plans)


@pytest.mark.parametrize("method", METHODS)
def test_every_method_loses_a_hex_whose_only_reach_is_near_the_promise_in_slow_traffic(method: Method) -> None:
    # S0 reaches W (1 min) and A (5 min); at promise 8, multiplier 1.0, A drops out at 1.25x.
    inputs = make_inputs({"W": 100.0, "A": 200.0}, {("S0", "W"): 1.0, ("S0", "A"): 5.0}, ["S0", "S1"])
    p = plan(inputs, Scenario(n_new=1, promise=8, multiplier=1.0), method)
    assert p.method == method and p.demand_covered == pytest.approx(300) and p.slow_traffic_coverage == pytest.approx(100)


def test_slow_traffic_coverage_never_exceeds_the_demand_covered_of_a_poor_assignment() -> None:
    # S reaches A (500) and B (300) at 1 min and C (700) at 6 min; at multiplier 1.0, promise 10, C is reachable but not at 1.25x.
    # Hand metrics an assignment that gives S only C (a time-limited CP-SAT plan can): covered 700, while the slow-traffic walk alone would take A + B = 800.
    inputs = make_inputs({"A": 500.0, "B": 300.0, "C": 700.0}, {("S", "A"): 1.0, ("S", "B"): 1.0, ("S", "C"): 6.0}, ["S", "N"])
    p = planning.Problem.build(inputs, Scenario(n_new=1, promise=10, multiplier=1.0, capacity=0.5))
    assert p.existing == [0]
    owner = np.full(len(inputs.hex_ids), -1, dtype=np.intp)
    owner[list(inputs.hex_ids).index("C")] = 0
    covered, _, _, _, slow, _ = planning.metrics(p, [], owner)
    assert covered == pytest.approx(700) and slow == pytest.approx(700)


def test_the_gap_is_none_not_infinite_for_a_zero_objective_under_a_positive_bound() -> None:
    # JSON has no infinity (the stage 3 service); a ratio of nothing served to a positive bound has no finite value.
    assert planning.relative_gap(0.0, 5.0, "FEASIBLE") is None


@pytest.mark.parametrize("seed", [0, 1, 4])
@pytest.mark.parametrize("capacity", [0.5, 1.0])
def test_the_model_size_count_is_the_number_of_capacity_bound_pairs_the_build_creates(seed: int, capacity: float) -> None:
    p = planning.Problem.build(random_inputs(seed), Scenario(n_new=5, promise=12, capacity=capacity, seed=seed))
    rows = planning.model_rows(p)
    assert rows.n_pairs == len(planning.build_model(p, rows).x)
    assert capacity != 0.5 or rows.n_pairs > 0   # the 0.5x fixtures do bind capacity


def test_a_model_over_the_size_cap_is_not_built(monkeypatch: pytest.MonkeyPatch) -> None:
    # #33: the build is an uninterruptible Python loop outside the solver's time limit, so a model that would overrun the budget is not built.
    inputs, scenario = random_inputs(0), Scenario(n_new=4, promise=12, capacity=0.5, seed=0)
    greedy = plan(inputs, scenario)

    def refuse(*args: object) -> None:
        raise AssertionError("the model was built")
    monkeypatch.setattr(planning, "build_model", refuse)
    monkeypatch.setattr(planning.assumptions, "MODEL_PAIR_CAP", 0)
    hinted = plan(inputs, scenario, "cpsat-from-greedy")
    assert hinted.method == "cpsat-from-greedy" and hinted.status == "HEURISTIC" and hinted.sites == greedy.sites
    assert hinted.objective == pytest.approx(greedy.objective) and hinted.bound is None and hinted.gap is None
    assert hinted.demand_covered == pytest.approx(greedy.demand_covered)
    alone = plan(inputs, scenario, "cpsat")
    assert alone.status == "UNKNOWN" and alone.sites == [] and alone.objective is None and alone.bound is None and alone.gap is None


def test_a_model_at_the_size_cap_is_built(monkeypatch: pytest.MonkeyPatch) -> None:
    inputs, scenario = random_inputs(0), Scenario(n_new=4, promise=12, capacity=0.5, seed=0)
    n = planning.model_rows(planning.Problem.build(inputs, scenario)).n_pairs
    monkeypatch.setattr(planning.assumptions, "MODEL_PAIR_CAP", n)
    assert plan(inputs, scenario, "cpsat").status == "OPTIMAL"


def test_cpsat_from_greedy_keeps_greedys_plan_as_heuristic_when_the_solver_does_worse(monkeypatch: pytest.MonkeyPatch) -> None:
    # The solver's solution is below greedy's: greedy's plan stands, and the solver's bound is reported with it.
    inputs, scenario = random_inputs(0), Scenario(n_new=4, promise=12, seed=0)
    greedy = plan(inputs, scenario)
    monkeypatch.setattr(cp_model.CpSolver, "Solve", lambda self, model: cp_model.FEASIBLE)
    monkeypatch.setattr(cp_model.CpSolver, "ObjectiveValue", lambda self: 0.0)
    monkeypatch.setattr(cp_model.CpSolver, "BestObjectiveBound", lambda self: 1e9)
    p = plan(inputs, scenario, "cpsat-from-greedy")
    assert p.status == "HEURISTIC" and p.sites == greedy.sites and p.bound == pytest.approx(1e7)
    assert p.gap is not None and p.gap > 0


def test_a_feasible_cpsat_plan_keeps_the_invariants_of_a_plan_the_solver_stopped_early(monkeypatch: pytest.MonkeyPatch) -> None:
    # Stopping at the first solution on one worker is deterministic and, here, short of the optimum (seed 0, capacity 0.5x, 5 new stores).
    class FirstSolution(cp_model.CpSolver):
        def Solve(self, model: cp_model.CpModel, solution_callback: cp_model.CpSolverSolutionCallback | None = None) -> int:
            self.parameters.stop_after_first_solution, self.parameters.num_workers = True, 1
            return super().Solve(model, solution_callback)
    monkeypatch.setattr(cp_model, "CpSolver", FirstSolution)
    p = plan(random_inputs(0), Scenario(n_new=5, promise=12, capacity=0.5, seed=0), "cpsat")
    assert p.status == "FEASIBLE" and p.method == "cpsat"
    assert p.objective is not None and p.bound is not None and p.objective <= p.bound
    assert p.gap is not None and 0 < p.gap and p.gap == pytest.approx((p.bound - p.objective) / p.objective)
    assert 0 < p.slow_traffic_coverage <= p.demand_covered
