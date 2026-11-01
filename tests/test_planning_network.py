"""Characterisation tests for the synthetic network in `planning.py` (#26): placement order and weighting, one store per site, and the competitor split."""
import numpy as np
import pytest
from test_planning import Pairs, make_inputs

from catchment import assumptions
from catchment.planning import Inputs, Scenario, place_network, plan

SEEDS: list[int] = list(range(40))
SITES: list[str] = [f"S{i}" for i in range(10)]


def ladder(stores: int) -> Inputs:
    """Ten sites, each reaching its own hex (demand 100, 200, ... 1000) at 1 min, well inside the default reach."""
    hexes = {f"H{i}": 100.0 * (i + 1) for i in range(10)}
    return make_inputs(hexes, {(f"S{i}", f"H{i}"): 1.0 for i in range(10)}, SITES, stores=stores)


def test_the_operators_stores_are_placed_before_the_competitors() -> None:
    inputs = ladder(stores=6)   # 4 operator stores, 2 competitor stores
    assert assumptions.brand_split(6) == {"Operator": 4, "Competitor": 2}
    weight = np.arange(1, 11) * 100.0
    for seed in SEEDS:
        rng = np.random.default_rng(seed)
        operator = sorted(rng.choice(10, size=4, replace=False, p=weight / weight.sum()).tolist())
        weight[operator] = 0.0
        competitor = sorted(rng.choice(10, size=2, replace=False, p=weight / weight.sum()).tolist())
        assert place_network(inputs, seed) == {"Operator": operator, "Competitor": competitor}
        weight = np.arange(1, 11) * 100.0


def test_a_site_reaching_nothing_at_the_default_never_holds_a_store_whatever_the_scenario() -> None:
    # S6 reaches a hex only at 4.5 free-flow min: 4.5 x 1.8 + 3 = 11.1 min, past the default promise but inside 15. S7 reaches nothing.
    hexes = {f"H{i}": 100.0 for i in range(6)} | {"L": 100.0}
    pairs: Pairs = {(f"S{i}", f"H{i}"): 1.0 for i in range(6)} | {("S6", "L"): 4.5}
    inputs = make_inputs(hexes, pairs, SITES[:8], stores=3)
    for seed in SEEDS:
        default_net = plan(inputs, Scenario(n_new=1, seed=seed)).network
        assert plan(inputs, Scenario(n_new=1, seed=seed, promise=20, multiplier=1.0)).network == default_net
        held = {s for sites in default_net.values() for s in sites}
        assert held and held <= {f"S{i}" for i in range(6)}


def test_sites_are_drawn_in_proportion_to_the_demand_they_reach() -> None:
    hexes = {"H0": 900.0} | {f"H{i}": 10.0 for i in range(1, 6)}
    inputs = make_inputs(hexes, {(f"S{i}", f"H{i}"): 1.0 for i in range(6)}, SITES[:6], stores=2)
    assert assumptions.brand_split(2) == {"Operator": 1, "Competitor": 1}
    heavy = sum(0 in place_network(inputs, seed)["Operator"] for seed in SEEDS)   # expected about 38 of 40
    assert heavy >= 30


def test_no_site_holds_two_stores() -> None:
    inputs = ladder(stores=6)
    for seed in SEEDS:
        held = [s for sites in place_network(inputs, seed).values() for s in sites]
        assert len(held) == 6 and len(set(held)) == 6


def competitor_fixture() -> tuple[Inputs, int]:
    """Operator at S0, competitor at S1 (a seed that puts them there). Hex A is reached by S0 at 1 min and by S1 only at 4.5 min,
    so the competitor reaches A at promise 15 (4.5 x 1.8 + 3 = 11.1) or at multiplier 1.0 (7.5), not at the default (11.1 > 10)."""
    hexes = {"P0": 500.0, "P1": 500.0, "A": 400.0}
    pairs: Pairs = {("S0", "P0"): 1.0, ("S1", "P1"): 1.0, ("S0", "A"): 1.0, ("S1", "A"): 4.5}
    inputs = make_inputs(hexes, pairs, ["S0", "S1", "S2", "S3"], stores=2)
    seed = next(s for s in range(200) if place_network(inputs, s) == {"Operator": [0], "Competitor": [1]})
    return inputs, seed


@pytest.mark.parametrize("promise, multiplier, covered", [(10, 1.8, 900.0), (15, 1.8, 700.0), (10, 1.0, 700.0)])
def test_the_competitor_reaches_what_the_scenario_lets_it_reach(promise: int, multiplier: float, covered: float) -> None:
    inputs, seed = competitor_fixture()
    p = plan(inputs, Scenario(n_new=1, promise=promise, multiplier=multiplier, seed=seed))
    assert p.network == {"Operator": ["S0"], "Competitor": ["S1"]}
    assert p.demand_covered == pytest.approx(covered)   # P0 whole, A whole unless the competitor reaches it, then half (1/(1+1))


def test_capture_applies_before_the_split() -> None:
    inputs, seed = competitor_fixture()
    p = plan(inputs, Scenario(n_new=1, promise=15, capture=1.5, seed=seed))
    assert p.demand_covered == pytest.approx(1.5 * 500.0 + 400.0 * 1.5 / 2)   # demand x capture / 2 on the shared hex
