"""Characterisation tests for the synthetic network in `planning.py` (#26): placement order and weighting, one store per site, and the competitor split."""
from itertools import pairwise

import numpy as np
import pytest
from test_planning import OPS, Pairs, make_inputs, random_inputs

from catchment import assumptions
from catchment.planning import METHODS, Inputs, Method, Scenario, place_network, plan

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
        order = rng.choice(10, size=int((weight > 0).sum()), replace=False, p=weight / weight.sum()).tolist()   # one ordering of every remaining site
        assert place_network(inputs, seed) == {"Operator": operator, "Competitor": sorted(order[:2])}
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


DENSITIES: list[float] = [0.25 * i for i in range(9)]


def hundred_sites() -> Inputs:
    """100 sites, 57 stores (39 operator, 18 competitor at the default), every site reaching its own hex."""
    return make_inputs({f"H{i}": 57 * OPS / 100 for i in range(100)}, {(f"S{i}", f"H{i}"): 1.0 for i in range(100)}, [f"S{i}" for i in range(100)], stores=57)


@pytest.mark.parametrize("density", DENSITIES)
def test_every_density_step_is_accepted(density: float) -> None:
    assert Scenario(competitor_density=density).competitor_density == density


@pytest.mark.parametrize("density", [0.3, 1.1, 0.01])
def test_an_off_step_density_is_refused_naming_the_lever_and_the_step(density: float) -> None:
    with pytest.raises(ValueError, match=f"competitor_density {density:g} is not in steps of 0.25"):
        Scenario(competitor_density=density)


@pytest.mark.parametrize("lever", ["multiplier", "capacity", "capture", "competitor_density"])
@pytest.mark.parametrize("value", [True, np.bool_(True), "1.0"])
def test_a_float_lever_must_be_a_real_number_not_a_bool(lever: str, value: object) -> None:
    with pytest.raises(TypeError, match=f"{lever} .* must be a number"):
        Scenario(**{lever: value})


@pytest.mark.parametrize("lever", ["multiplier", "capacity", "capture", "competitor_density"])
def test_a_float_lever_is_stored_as_a_plain_float(lever: str) -> None:
    s = Scenario(**{lever: np.float64(1.5) if lever != "competitor_density" else np.float32(1.5)})
    assert type(getattr(s, lever)) is float and getattr(s, lever) == 1.5


def test_a_negative_zero_density_is_stored_and_printed_as_zero() -> None:
    s = Scenario(competitor_density=-0.0)
    assert str(s.competitor_density) == "0.0" and "competitor_density=0.0," in repr(s)


def test_an_off_step_density_by_float_noise_shows_the_value_it_got() -> None:
    with pytest.raises(ValueError, match=r"competitor_density 0\.75000000000\d+ is not in steps of 0\.25"):
        Scenario(competitor_density=0.75 + 1e-12)


def test_density_zero_has_no_competitor_stores() -> None:
    for seed in SEEDS[:5]:
        assert plan(hundred_sites(), Scenario(competitor_density=0.0, seed=seed)).network["Competitor"] == []


def test_the_operators_stores_are_the_same_at_every_density() -> None:
    inputs = hundred_sites()
    for seed in SEEDS[:5]:
        operators = {tuple(plan(inputs, Scenario(competitor_density=d, seed=seed)).network["Operator"]) for d in DENSITIES}
        assert len(operators) == 1


def test_a_denser_network_contains_a_sparser_one_and_the_count_is_the_rounded_multiple_of_the_default() -> None:
    inputs = hundred_sites()
    for seed in SEEDS[:5]:
        nets = [plan(inputs, Scenario(competitor_density=d, seed=seed)).network["Competitor"] for d in DENSITIES]
        assert [len(n) for n in nets] == [0, 4, 9, 14, 18, 22, 27, 32, 36]   # round(d x 18), halves to even
        for sparse, dense in pairwise(nets):
            assert set(sparse) <= set(dense)


@pytest.mark.parametrize("method", METHODS)
def test_demand_covered_does_not_rise_with_competitor_density_while_capacity_is_slack(method: Method) -> None:
    for seed in range(8):
        inputs = random_inputs(seed)
        plans = [plan(inputs, Scenario(n_new=3, promise=12, capacity=2.0, competitor_density=d, seed=seed), method) for d in DENSITIES]
        covered = [p.demand_covered for p in plans]
        assert all(p.lost_to_capacity == 0 for p in plans)   # capacity is slack here (see the next test for when it binds)
        assert all(b <= a + 1e-6 for a, b in pairwise(covered)), (seed, covered)
        assert covered[-1] < covered[0], (seed, covered)   # the competitor does take demand here, so the check is not vacuous


def test_when_capacity_binds_a_competitor_can_raise_demand_covered() -> None:
    # A known property of whole-hex assignment with a split demand (ADR 0001; decision log 2026-11-01, #29). At 0.5x a store serves
    # 1,182 orders. The operator at S0 reaches A and B (700 each): alone, only one fits. The competitor at S1 also reaches B, halving it
    # to 350, and 700 + 350 fits. The one new store goes to S2 (C, 1,000) at both densities, ahead of an empty S1 (B, 700) at density 0:
    # demand covered rises from 1,700 to 2,050 as density goes from 0 to 1.
    hexes = {"A": 700.0, "B": 700.0, "C": 1000.0}
    inputs = make_inputs(hexes, {("S0", "A"): 1.0, ("S0", "B"): 1.0, ("S1", "B"): 1.0, ("S2", "C"): 1.0}, ["S0", "S1", "S2", "S3"], stores=2)
    seed = next(s for s in range(200) if place_network(inputs, s) == {"Operator": [0], "Competitor": [1]})
    plans = {d: plan(inputs, Scenario(n_new=1, capacity=0.5, competitor_density=d, seed=seed)) for d in (0.0, 1.0)}
    assert [p.sites for p in plans.values()] == [["S2"], ["S2"]]
    assert {d: p.demand_covered for d, p in plans.items()} == pytest.approx({0.0: 1700.0, 1.0: 2050.0})


def test_a_density_whose_competitor_stores_cannot_be_placed_is_refused_only_at_that_density() -> None:
    # 6 sites reach demand and the network is 6 stores: 4 operator, then 2 competitor at the default, which takes the last 2 sites.
    inputs = make_inputs({f"H{i}": 100.0 for i in range(6)}, {(f"S{i}", f"H{i}"): 1.0 for i in range(6)}, SITES[:8], stores=6)
    split = assumptions.brand_split(6)
    assert split == {"Operator": 4, "Competitor": 2}   # 2 sites remain after the operator: the default fits, 2x (4 stores) does not
    assert len(plan(inputs, Scenario(n_new=1, competitor_density=1.0)).network["Competitor"]) == 2
    with pytest.raises(ValueError, match="at competitor density 2x, the Competitor's 4 stores need 4 candidate sites that reach some demand at the default scenario"):
        plan(inputs, Scenario(n_new=1, competitor_density=2.0))
