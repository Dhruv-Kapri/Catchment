"""Plan new stores for a scenario: the synthetic network, a greedy plan and its metrics. `plan()` is the one entry point."""
import numbers
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Literal, get_args

import numpy as np
import numpy.typing as npt
import pandas as pd
from ortools.sat.python import cp_model

from catchment import assumptions
from catchment.build import demand_name, reach_names
from catchment.fetch import DATA

Method = Literal["greedy", "cpsat", "cpsat-from-greedy"]
METHODS: tuple[str, ...] = get_args(Method)
TOL: float = 1e-9   # reach tolerance, as in 02-plan
GAIN_DP: int = 6     # greedy compares gains to a millionth of an order, so the incremental update's rounding noise ties like a fresh sum


@dataclass(frozen=True, eq=False)
class Inputs:
    """The demand table, candidate sites and travel-time table as positional arrays, built once and reused across plans."""
    hex_ids: npt.NDArray[np.str_]
    demand: npt.NDArray[np.float64]        # orders a day at the default capture share, as stored
    households: npt.NDArray[np.float64]
    site_ids: npt.NDArray[np.str_]         # candidate sites in rank order
    pair_site: npt.NDArray[np.intp]        # position in site_ids
    pair_hex: npt.NDArray[np.intp]         # position in hex_ids
    pair_min: npt.NDArray[np.float64]      # free-flow minutes

    @classmethod
    def from_frames(cls, demand: pd.DataFrame, candidates: pd.DataFrame, table: pd.DataFrame) -> "Inputs":
        sites = candidates.sort_values("rank", kind="stable").index
        pair_site, pair_hex = sites.get_indexer(table["candidate"]), demand.index.get_indexer(table["hex"])
        if (pair_site < 0).any() or (pair_hex < 0).any():
            raise ValueError("the travel-time table names a candidate site or hex missing from the candidates or the demand table")
        return cls(demand.index.to_numpy(dtype=str), demand["demand"].to_numpy(float), demand["households"].to_numpy(float),
                   sites.to_numpy(dtype=str), pair_site, pair_hex, table["minutes"].to_numpy(float))


def load_inputs(res: int = 9, x_pct: float = 30, data_dir: Path = DATA) -> Inputs:
    """Read the tables `catchment-build` wrote."""
    candidates, table = reach_names(res, x_pct)
    return Inputs.from_frames(pd.read_parquet(data_dir / demand_name(res)), pd.read_parquet(data_dir / candidates), pd.read_parquet(data_dir / table))


LEVER_RANGES: dict[str, tuple[float, float]] = {
    "n_new": assumptions.N_RANGE, "promise": assumptions.PROMISE_RANGE, "multiplier": assumptions.MULTIPLIER_RANGE,
    "capacity": assumptions.CAPACITY_RANGE, "capture": assumptions.CAPTURE_RANGE, "competitor_density": assumptions.COMPETITOR_DENSITY_RANGE}


@dataclass(frozen=True)
class Scenario:
    """One set of lever values, plus the network seed."""
    n_new: int = assumptions.N_AREA
    promise: int = assumptions.PROMISE
    multiplier: float = assumptions.MULTIPLIER
    capacity: float = 1.0           # x the default capacity
    capture: float = 1.0            # x the default capture share
    competitor_density: float = 1.0
    seed: int = assumptions.SEED

    def __post_init__(self) -> None:
        for lever in ("n_new", "promise"):
            value = getattr(self, lever)
            if not isinstance(value, numbers.Integral) or isinstance(value, bool):
                raise TypeError(f"{lever} {value!r} must be a whole number")
            object.__setattr__(self, lever, int(value))   # np.int64 and the like become plain ints
        for lever, (low, high) in LEVER_RANGES.items():
            value = getattr(self, lever)
            if not low <= value <= high:
                raise ValueError(f"{lever} {value:g} is outside the lever range {low:g}-{high:g}")


@dataclass(frozen=True)
class NewStore:
    """What one new store serves, in the operator's orders a day. Fresh and cannibalised are judged against the base assignment
    (existing stores only). Orders an existing store wins back with capacity a new store freed belong to no new store, so the
    new stores' fresh orders can sum to less than the plan's gain over the existing network."""
    site: str
    orders: float          # the share of the hexes assigned to it
    fresh: float           # the part no existing operator store served in the base assignment
    cannibalised: float    # the part an existing operator store served


@dataclass(frozen=True)
class Plan:
    """The new sites for one scenario, and the network they were planned against.

    The metrics (`demand_covered` and the rest) always describe the plan's assignment of hexes to stores, whatever the method.
    `households_covered` counts whole hexes: a hex shared with the competitor counts all its households but half its orders.
    For CP-SAT, `objective` is the solver's own value, and `demand_covered` can exceed it on a FEASIBLE plan, because the
    assignment also gives a hex to an open store that cannot reach capacity even where the solver left it uncovered.
    A hinted plan that would fall below greedy keeps greedy's picks (status FEASIBLE; `bound` the solver's, or None if it found no solution), so it is never below greedy."""
    scenario: Scenario
    method: Method
    sites: list[str]                 # the new sites, in pick order
    network: dict[str, list[str]]    # brand -> the sites of its existing stores
    demand_covered: float            # the operator's orders a day assigned to a store
    households_covered: float        # households of the assigned hexes, whole hexes
    lost_to_capacity: float          # reached by an open operator store but not assigned
    unreached: float                 # reached by no open operator store
    new_stores: list[NewStore]       # in pick order
    status: str                      # "OPTIMAL" or "FEASIBLE" from CP-SAT; "HEURISTIC" for greedy
    objective: float                 # orders a day: what the method claims (CP-SAT: the solver's, greedy: demand_covered)
    bound: float | None              # CP-SAT's upper bound on the objective; None for greedy
    gap: float | None                # (bound - objective) / objective; 0.0 when OPTIMAL; None for greedy
    build_seconds: float             # everything before the search: network, shares, reach, greedy hint, model
    solve_seconds: float             # the greedy loop, or CP-SAT's Solve
    seconds: float                   # inside plan(), load_inputs excluded: build + solve + metrics


def reachable(inputs: Inputs, promise: float, multiplier: float) -> npt.NDArray[np.bool_]:
    return inputs.pair_min * multiplier + assumptions.PICK_AND_PACK <= promise + TOL


def place_network(inputs: Inputs, seed: int) -> dict[str, list[int]]:
    """The existing stores' site positions by brand: sized from the area's demand, weighted by the demand each site reaches at the default scenario."""
    split = assumptions.brand_split(assumptions.network_size(inputs.demand.sum()))
    ok = reachable(inputs, assumptions.PROMISE, assumptions.MULTIPLIER)
    weight = np.bincount(inputs.pair_site[ok], weights=inputs.demand[inputs.pair_hex[ok]], minlength=len(inputs.site_ids))
    rng = np.random.default_rng(seed)
    placed: dict[str, list[int]] = {}
    for brand, n in split.items():
        if (weight > 0).sum() < n:
            raise ValueError(f"the {brand}'s {n} stores need {n} candidate sites that reach some demand at the default scenario, only {(weight > 0).sum()} do")
        placed[brand] = sorted(rng.choice(len(weight), size=n, replace=False, p=weight / weight.sum()).tolist()) if n else []
        weight[placed[brand]] = 0.0
    return placed


@dataclass(frozen=True)
class Reach:
    """The reachable (site, hex) pairs in nearest-first order, sorted once per plan, with each hex's pairs indexed."""
    site: npt.NDArray[np.intp]       # per pair, nearest first (ties: site rank, then hex position)
    hex: npt.NDArray[np.intp]
    by_hex: npt.NDArray[np.intp]     # pair positions grouped by hex
    start: npt.NDArray[np.intp]      # hex h's pairs are by_hex[start[h]:start[h + 1]]

    @classmethod
    def build(cls, inputs: Inputs, ok: npt.NDArray[np.bool_]) -> "Reach":
        site, hex_, minutes = inputs.pair_site[ok], inputs.pair_hex[ok], inputs.pair_min[ok]
        order = np.lexsort((hex_, site, minutes))
        site, hex_ = site[order], hex_[order]
        by_hex = np.argsort(hex_, kind="stable")
        return cls(site, hex_, by_hex, np.searchsorted(hex_[by_hex], np.arange(len(inputs.hex_ids) + 1)))

    def assign(self, stores: list[int], share: npt.NDArray[np.float64], capacity: float, n_sites: int) -> npt.NDArray[np.intp]:
        """Owner site per hex (-1: none). Walk the open stores' pairs nearest first: a hex goes wholly to one store, a store takes only up to its capacity."""
        walk = np.flatnonzero(np.isin(self.site, stores))
        owner, load, shares = [-1] * len(share), [0.0] * n_sites, share.tolist()
        for s, h in zip(self.site[walk].tolist(), self.hex[walk].tolist()):
            if owner[h] < 0 and load[s] + shares[h] <= capacity + TOL:
                owner[h], load[s] = s, load[s] + shares[h]
        return np.array(owner, dtype=np.intp)

    def pairs_of(self, hexes: npt.NDArray[np.intp]) -> npt.NDArray[np.intp]:
        """Positions of the pairs of the given hexes."""
        first, length = self.start[hexes], self.start[hexes + 1] - self.start[hexes]
        return self.by_hex[np.repeat(first - (np.cumsum(length) - length), length) + np.arange(length.sum())]


@dataclass(frozen=True)
class Problem:
    """What every method plans against: the network, the shares, the reach and the base assignment."""
    inputs: Inputs
    scenario: Scenario
    network: dict[str, list[int]]    # brand -> site positions
    capacity: float
    share: npt.NDArray[np.float64]   # the operator's share of each hex (ADR 0001)
    existing: list[int]              # the operator's stores
    candidate: npt.NDArray[np.bool_] # open sites a new store may take
    reach: Reach
    base: npt.NDArray[np.intp]       # owner per hex with the existing operator stores only

    @classmethod
    def build(cls, inputs: Inputs, scenario: Scenario) -> "Problem":
        network = place_network(inputs, scenario.seed)
        n_sites, capacity = len(inputs.site_ids), scenario.capacity * assumptions.CAPACITY
        ok = reachable(inputs, scenario.promise, scenario.multiplier)
        rival = np.zeros(len(inputs.demand), bool)
        rival[inputs.pair_hex[ok & np.isin(inputs.pair_site, network["Competitor"])]] = True
        share = inputs.demand * scenario.capture / (1 + rival)   # ADR 0001
        candidate = np.ones(n_sites, bool)
        candidate[[s for ss in network.values() for s in ss]] = False
        if scenario.n_new > candidate.sum():
            raise ValueError(f"{scenario.n_new} new stores asked for, only {candidate.sum()} open candidate sites hold no store")
        reach = Reach.build(inputs, ok)
        existing = network["Operator"]
        return cls(inputs, scenario, network, capacity, share, existing, candidate, reach, reach.assign(existing, share, capacity, n_sites))


def greedy(p: Problem) -> tuple[list[int], npt.NDArray[np.intp]]:
    """The picked sites in pick order, and the owner per hex.

    Each step takes the open site with the largest gain, ties to the lowest rank. A site's gain is the approximation
    `min(unassigned share it reaches, capacity)`: it ignores that the site's nearest-first pairs may include hexes an existing
    store already serves, which use up its capacity, so a site that mostly cannibalises is overvalued."""
    n_sites, reach, share, capacity = len(p.inputs.site_ids), p.reach, p.share, p.capacity
    candidate, picked, owner = p.candidate.copy(), [], p.base
    gain = np.bincount(reach.site, weights=np.where(owner < 0, share, 0.0)[reach.hex], minlength=n_sites)   # unassigned share each site reaches, before the cap
    for _ in range(p.scenario.n_new):
        best = int(np.argmax(np.where(candidate, np.minimum(gain, capacity).round(GAIN_DP), -1.0)))   # rounded: float deltas must not break exact ties
        picked.append(best)
        candidate[best] = False
        now = reach.assign(p.existing + picked, share, capacity, n_sites)
        flipped = np.flatnonzero((now < 0) != (owner < 0))   # only these hexes change the gain: +share if newly unassigned, -share if newly assigned
        delta = np.zeros(len(share))
        delta[flipped] = np.where(now[flipped] < 0, share[flipped], -share[flipped])
        pairs = reach.pairs_of(flipped)
        gain += np.bincount(reach.site[pairs], weights=delta[reach.hex[pairs]], minlength=n_sites)
        owner = now
    return picked, owner


@dataclass
class Model:
    """The CP-SAT model and the variables the assignment is read from."""
    model: cp_model.CpModel
    y: dict[int, cp_model.IntVar]                  # per open candidate site
    x: list[tuple[int, int, cp_model.IntVar]]      # (site, hex, var) for sites that can exceed capacity
    covered: list[tuple[int, cp_model.IntVar]]     # (hex, var): some free new site reaches it
    constrained: npt.NDArray[np.bool_]             # per site: can its catchment exceed capacity
    share_int: npt.NDArray[np.int64]


def int_shares(p: Problem) -> npt.NDArray[np.int64]:
    return np.round(p.share * assumptions.SCALE).astype(np.int64)


def build_model(p: Problem) -> Model:
    """The tighter model of 03-area: x_{s,h} only at sites whose catchment can exceed capacity, a new site's capacity row tied to
    the site being chosen, and the existing operator stores in the same at-most-one row per hex."""
    n_sites, n_hex, reach = len(p.inputs.site_ids), len(p.share), p.reach
    share_int, cap_int = int_shares(p), round(p.capacity * assumptions.SCALE)
    is_new, is_op = p.candidate, np.zeros(n_sites, bool)
    is_op[p.existing] = True
    pos = reach.by_hex[(is_new | is_op)[reach.site][reach.by_hex]]   # open sites' pairs, grouped by hex, nearest first within a hex
    ps, ph = reach.site[pos], reach.hex[pos]
    constrained = np.bincount(ps, weights=share_int[ph], minlength=n_sites) > cap_int   # W_s > capacity
    con = constrained[ps]
    has_free_op = np.bincount(ph, weights=(~con & is_op[ps]).astype(float), minlength=n_hex) > 0   # an existing store that cannot hit capacity covers it
    start = np.searchsorted(ph, np.arange(n_hex + 1))
    model = cp_model.CpModel()
    y = {int(s): model.NewBoolVar(f"y{s}") for s in np.flatnonzero(is_new)}
    model.Add(sum(y.values()) == p.scenario.n_new)
    terms: list[cp_model.IntVar] = []
    coeffs: list[int] = []
    x: list[tuple[int, int, cp_model.IntVar]] = []
    covered: list[tuple[int, cp_model.IntVar]] = []
    row_of: dict[int, list[tuple[cp_model.IntVar, int]]] = {}
    ps_l, con_l, share_l = ps.tolist(), con.tolist(), share_int.tolist()
    const = int(share_int[np.unique(ph[has_free_op[ph]])].sum())
    for h in np.flatnonzero(np.diff(start) > 0).tolist():
        if has_free_op[h]:
            continue
        w, row = share_l[h], []
        free = [s for s, c in zip(ps_l[start[h]:start[h + 1]], con_l[start[h]:start[h + 1]]) if not c]
        if free:
            cover = model.NewBoolVar("")
            model.AddBoolOr([y[s] for s in free]).OnlyEnforceIf(cover)
            covered.append((h, cover))
            row.append(cover)
        for s, c in zip(ps_l[start[h]:start[h + 1]], con_l[start[h]:start[h + 1]]):
            if c:
                xv = model.NewBoolVar("")
                if is_new[s]:
                    model.AddImplication(xv, y[s])
                x.append((s, h, xv))
                row_of.setdefault(s, []).append((xv, w))
                row.append(xv)
        if len(row) > 1:
            model.AddAtMostOne(row)
        terms += row
        coeffs += [w] * len(row)
    for s, lst in row_of.items():
        load = cp_model.LinearExpr.WeightedSum([v for v, _ in lst], [w for _, w in lst])
        model.Add(load <= cap_int * y[s] if is_new[s] else load <= cap_int)
    model.Maximize(cp_model.LinearExpr.WeightedSum(terms, coeffs) + const)
    return Model(model, y, x, covered, constrained, share_int)


def hint(m: Model, picked: list[int], owner: npt.NDArray[np.intp]) -> None:
    """Hand CP-SAT a plan to start from: greedy's picks and its assignment."""
    chosen = set(picked)
    for s, v in m.y.items():
        m.model.AddHint(v, int(s in chosen))
    for s, h, v in m.x:
        m.model.AddHint(v, int(owner[h] == s))
    for h, v in m.covered:
        m.model.AddHint(v, int(owner[h] >= 0 and not m.constrained[owner[h]]))


def assignment(p: Problem, m: Model, picked: list[int], solver: cp_model.CpSolver) -> npt.NDArray[np.intp]:
    """Owner per hex from the solver's x variables; a hex it left to the free sites goes to the nearest open one."""
    reach, owner = p.reach, np.full(len(p.share), -1, dtype=np.intp)
    for s, h, v in m.x:
        if solver.Value(v):
            owner[h] = s
    open_free = np.zeros(len(p.inputs.site_ids), bool)
    open_free[[*p.existing, *picked]] = True
    open_free &= ~m.constrained
    near = np.flatnonzero(open_free[reach.site])   # pairs in nearest-first order, so a hex's first pair is its nearest free site
    hexes, first = np.unique(reach.hex[near], return_index=True)
    left = owner[hexes] < 0
    owner[hexes[left]] = reach.site[near][first[left]]
    return owner


@dataclass(frozen=True)
class Solved:
    """What a method hands to the metrics: the picks (greedy: pick order; CP-SAT: by rank), the owner per hex and the claim."""
    picked: list[int]
    owner: npt.NDArray[np.intp]
    status: str
    objective: float                 # orders a day
    bound: float | None
    built: float                     # perf_counter when the search began


def cpsat(p: Problem, t0: float, from_greedy: bool) -> Solved:
    start = greedy(p) if from_greedy else None
    m = build_model(p)
    if start is not None:
        hint(m, *start)
    built = time.perf_counter()
    solver = cp_model.CpSolver()
    solver.parameters.max_time_in_seconds = max(assumptions.PLAN_BUDGET - (built - t0), 0.1)
    solver.parameters.num_workers = assumptions.WORKERS
    solver.parameters.random_seed = assumptions.SOLVER_SEED
    status = solver.Solve(m.model)
    name, found = solver.StatusName(status), status in (cp_model.OPTIMAL, cp_model.FEASIBLE)
    if start is None and not found:
        raise RuntimeError(f"CP-SAT found no plan within {assumptions.PLAN_BUDGET:g} s: status {name}")
    if start is not None:
        floor = int(m.share_int[start[1] >= 0].sum())   # greedy's orders, on the solver's integer scale
        if not found or round(solver.ObjectiveValue()) < floor:   # never below greedy; with no solution the solver's bound says nothing
            return Solved(start[0], start[1], "FEASIBLE", floor / assumptions.SCALE, solver.BestObjectiveBound() / assumptions.SCALE if found else None, built)
    picked = sorted(s for s, v in m.y.items() if solver.Value(v))
    return Solved(picked, assignment(p, m, picked, solver), name, solver.ObjectiveValue() / assumptions.SCALE, solver.BestObjectiveBound() / assumptions.SCALE, built)


def relative_gap(objective: float, bound: float, status: str) -> float:
    """(bound - objective) / objective, as 03-area defined it: 0 when proven optimal or both are 0. Never negative: a greedy plan kept
    in place of the solver's can sit a rounding hair above the integer-scale bound."""
    return 0.0 if status == "OPTIMAL" or objective <= 0 else max(bound - objective, 0.0) / objective


def plan(inputs: Inputs | None = None, scenario: Scenario | None = None, method: Method = "greedy") -> Plan:
    """Plan the scenario's new stores with `method`: the greedy, CP-SAT on its own, or CP-SAT started from the greedy plan.
    The whole call, `load_inputs` excluded, aims at `assumptions.PLAN_BUDGET` plus the metrics."""
    if method not in METHODS:
        raise ValueError(f"unknown method {method!r}")
    inputs = load_inputs() if inputs is None else inputs
    t0 = time.perf_counter()
    p = Problem.build(inputs, Scenario() if scenario is None else scenario)
    if method == "greedy":
        built = time.perf_counter()
        picked, owner = greedy(p)
        solved = Solved(picked, owner, "HEURISTIC", float(p.share[owner >= 0].sum()), None, built)
    else:
        solved = cpsat(p, t0, method == "cpsat-from-greedy")
    searched = time.perf_counter()
    gap = None if solved.bound is None else relative_gap(solved.objective, solved.bound, solved.status)
    covered, households, lost, unreached, new_stores = metrics(p, solved.picked, solved.owner)
    return Plan(p.scenario, method, [str(inputs.site_ids[s]) for s in solved.picked],
                {b: [str(inputs.site_ids[s]) for s in ss] for b, ss in p.network.items()},
                covered, households, lost, unreached, new_stores, solved.status, solved.objective, solved.bound, gap,
                solved.built - t0, searched - solved.built, time.perf_counter() - t0)


def metrics(p: Problem, picked: list[int], owner: npt.NDArray[np.intp]) -> tuple[float, float, float, float, list[NewStore]]:
    """demand_covered, households_covered, lost_to_capacity, unreached and the new stores, for any method's picks and assignment."""
    inputs, share, reach = p.inputs, p.share, p.reach
    got = owner >= 0
    reached = np.zeros(len(share), bool)
    reached[reach.hex[np.isin(reach.site, p.existing + picked)]] = True
    new_stores: list[NewStore] = []
    for s in picked:
        mine = owner == s
        orders, moved = float(share[mine].sum()), float(share[mine & (p.base >= 0)].sum())
        new_stores.append(NewStore(str(inputs.site_ids[s]), orders, orders - moved, moved))
    return float(share[got].sum()), float(inputs.households[got].sum()), float(share[reached & ~got].sum()), float(share[~reached].sum()), new_stores
