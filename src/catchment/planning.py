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
METHODS: tuple[Method, ...] = get_args(Method)
Status = Literal["OPTIMAL", "FEASIBLE", "HEURISTIC", "UNKNOWN"]   # CP-SAT's own plan, proven or stopped early; greedy's plan (also when CP-SAT from greedy keeps it); CP-SAT on its own found none
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
LEVER_STEPS: dict[str, float] = {
    "n_new": assumptions.N_STEP, "promise": assumptions.PROMISE_STEP, "multiplier": assumptions.MULTIPLIER_STEP,
    "capacity": assumptions.CAPACITY_STEP, "capture": assumptions.CAPTURE_STEP, "competitor_density": assumptions.COMPETITOR_DENSITY_STEP}
WHOLE_LEVERS: frozenset[str] = frozenset({"n_new", "promise"})   # levers that take whole numbers


def lever_value(lever: str, value: object, whole: bool) -> int | float:
    """A lever's value as a plain int (whole levers) or float, refusing bools and non-numbers; -0.0 becomes 0.0, so it prints as 0.0."""
    if not isinstance(value, numbers.Integral if whole else numbers.Real) or isinstance(value, bool | np.bool_):
        low, high = LEVER_RANGES[lever]
        raise TypeError(f"{lever} {value!r} must be a {'whole number' if whole else 'number'} (lever range {low:g}-{high:g})")
    return int(value) if whole else float(value) + 0.0   # type: ignore[call-overload]


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
        for lever in LEVER_RANGES:
            object.__setattr__(self, lever, lever_value(lever, getattr(self, lever), whole=lever in WHOLE_LEVERS))
        for lever, (low, high) in LEVER_RANGES.items():
            value = getattr(self, lever)
            if not low <= value <= high:
                raise ValueError(f"{lever} {value:g} is outside the lever range {low:g}-{high:g}")
            step = LEVER_STEPS[lever]
            if value != round(round(value / step) * step, 10):   # float-safe: 1.4 is a tenth step, 1.45 is not
                raise ValueError(f"{lever} {value!r} is not in steps of {step:g} (lever range {low:g}-{high:g})")


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
    A hinted plan that would fall below greedy keeps greedy's picks (status HEURISTIC, as it is greedy's plan), so it is never below greedy. A model over
    `assumptions.MODEL_PAIR_CAP` is not built, as the build is outside the solver's time limit: from greedy the plan is greedy's (HEURISTIC), on its own it
    is UNKNOWN. Whenever a CP-SAT method has an objective it states a bound: the solver's, or `capacity_bound` where that is lower or the solver has none."""
    scenario: Scenario
    method: Method
    sites: list[str]                 # the new sites, in pick order
    network: dict[str, list[str]]    # brand -> the sites of its existing stores
    demand_covered: float            # the operator's orders a day assigned to a store
    households_covered: float        # households of the assigned hexes, whole hexes
    lost_to_capacity: float          # reached by an open operator store but not assigned; on a FEASIBLE CP-SAT plan also the hexes the solver left unassigned
    unreached: float                 # reached by no open operator store
    slow_traffic_coverage: float     # demand covered by the same operator stores at SLOW_TRAFFIC_FACTOR x the multiplier, same shares; never above demand_covered: the nearest-first walk covers no more than greedy's or an OPTIMAL plan's assignment, and a FEASIBLE CP-SAT plan's is clamped to it (#33)
    new_stores: list[NewStore]       # in pick order
    service_areas: dict[str, list[str]]   # every operator store (existing, then new in pick order) -> the hex ids the plan assigns it; [] if none
    catchments: dict[str, list[str]]      # same keys -> the hex ids it reaches within the promise at the scenario's multiplier, pick-and-pack included
    greedy_demand_covered: float     # the greedy plan's demand_covered for the same scenario; the plan's own for method greedy, so the gain over greedy is demand_covered minus this
    status: Status                   # CP-SAT's own plan: "OPTIMAL", or "FEASIBLE" (stopped early); "HEURISTIC": greedy's plan, by method or kept by cpsat-from-greedy; "UNKNOWN": CP-SAT on its own found no plan, or the model was over the size cap, so no new sites and the metrics are the existing network's
    objective: float | None          # orders a day: what the method claims (CP-SAT: the solver's, greedy: demand_covered); None when UNKNOWN
    bound: float | None              # upper bound on the objective: the lower of CP-SAT's and `capacity_bound`'s, never under the objective (so on a kept greedy plan or an unbuilt model, the fallback alone); None for greedy and when UNKNOWN
    gap: float | None                # (bound - objective) / objective; 0.0 when OPTIMAL; None without a bound, and for a zero objective under a positive bound
    build_seconds: float             # everything before the search: network, shares, reach, greedy hint, model
    solve_seconds: float             # the greedy loop, or CP-SAT's Solve
    seconds: float                   # inside plan(), load_inputs excluded: build + solve + metrics


def reachable(inputs: Inputs, promise: float, multiplier: float) -> npt.NDArray[np.bool_]:
    return inputs.pair_min * multiplier + assumptions.PICK_AND_PACK <= promise + TOL


def place_network(inputs: Inputs, seed: int, density: float = 1.0) -> dict[str, list[int]]:
    """The existing stores' site positions by brand: sized from the area's demand, weighted by the demand each site reaches at the default scenario.
    The operator's stores are fixed. The competitor's are the first round(density x the default count) of one seeded ordering of the remaining sites."""
    split = assumptions.brand_split(assumptions.network_size(inputs.demand.sum()))
    ok = reachable(inputs, assumptions.PROMISE, assumptions.MULTIPLIER)
    weight = np.bincount(inputs.pair_site[ok], weights=inputs.demand[inputs.pair_hex[ok]], minlength=len(inputs.site_ids))
    rng = np.random.default_rng(seed)
    n_operator = split["Operator"]
    if (weight > 0).sum() < n_operator:
        raise ValueError(f"the Operator's {n_operator} stores need {n_operator} candidate sites that reach some demand at the default scenario, only {(weight > 0).sum()} do")
    operator = sorted(rng.choice(len(weight), size=n_operator, replace=False, p=weight / weight.sum()).tolist()) if n_operator else []
    weight[operator] = 0.0
    n_competitor = round(density * split["Competitor"])
    open_sites = int((weight > 0).sum())
    if open_sites < n_competitor:
        raise ValueError(f"at competitor density {density:g}x, the Competitor's {n_competitor} stores need {n_competitor} candidate sites that reach some demand at the default scenario, only {open_sites} do")
    order = rng.choice(len(weight), size=open_sites, replace=False, p=weight / weight.sum()).tolist() if open_sites else []
    return {"Operator": operator, "Competitor": sorted(order[:n_competitor])}


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


def cover_at_slow_traffic(inputs: Inputs, scenario: Scenario, stores: list[int], share: npt.NDArray[np.float64], capacity: float) -> float:
    """Demand the operator's stores still cover at SLOW_TRAFFIC_FACTOR x the scenario's multiplier. The shares are held (ADR 0001: k is fixed
    per scenario). The slow reach is a prefix of the nearest-first walk, so this is at most the nearest-first coverage of the same stores."""
    slow = Reach.build(inputs, reachable(inputs, scenario.promise, scenario.multiplier * assumptions.SLOW_TRAFFIC_FACTOR))
    return float(share[slow.assign(stores, share, capacity, len(inputs.site_ids)) >= 0].sum())


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
        network = place_network(inputs, scenario.seed, scenario.competitor_density)
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


@dataclass(frozen=True)
class ModelRows:
    """The open sites' pairs grouped by hex (nearest first within a hex) and what the model's loop reads from them, computed vectorised so the
    model's size is known before any Python loop runs."""
    pair_site: npt.NDArray[np.intp]        # per pair: site
    pair_hex: npt.NDArray[np.intp]         # per pair: hex
    pair_constrained: npt.NDArray[np.bool_]   # per pair: its site is constrained
    constrained: npt.NDArray[np.bool_]     # per site: can its catchment exceed capacity
    has_free_op: npt.NDArray[np.bool_]     # per hex: an existing store that cannot hit capacity covers it
    hex_start: npt.NDArray[np.intp]        # hex h's pairs are pair_site[hex_start[h]:hex_start[h + 1]]
    share_int: npt.NDArray[np.int64]
    cap_int: int
    is_new: npt.NDArray[np.bool_]

    @property
    def n_pairs(self) -> int:
        """The capacity-bound (x) pairs the model gets: constrained pairs in hexes with no free existing store, the loop's bulk."""
        return int((self.pair_constrained & ~self.has_free_op[self.pair_hex]).sum())


def model_rows(p: Problem) -> ModelRows:
    """The open sites' pairs grouped by hex, with the per-site and per-hex flags the model reads, so its size is known before the build loop."""
    n_sites, n_hex, reach = len(p.inputs.site_ids), len(p.share), p.reach
    share_int, cap_int = int_shares(p), round(p.capacity * assumptions.SCALE)
    is_new, is_op = p.candidate, np.zeros(n_sites, bool)
    is_op[p.existing] = True
    pos = reach.by_hex[(is_new | is_op)[reach.site][reach.by_hex]]   # open sites' pairs, grouped by hex, nearest first within a hex
    pair_site, pair_hex = reach.site[pos], reach.hex[pos]
    constrained = np.bincount(pair_site, weights=share_int[pair_hex], minlength=n_sites) > cap_int   # W_s > capacity
    pair_constrained = constrained[pair_site]
    has_free_op = np.bincount(pair_hex, weights=(~pair_constrained & is_op[pair_site]).astype(float), minlength=n_hex) > 0
    return ModelRows(pair_site, pair_hex, pair_constrained, constrained, has_free_op, np.searchsorted(pair_hex, np.arange(n_hex + 1)), share_int, cap_int, is_new)


def build_model(p: Problem, rows: ModelRows) -> Model:
    """The tighter model of 03-area: x_{s,h} only at sites whose catchment can exceed capacity, a new site's capacity row tied to
    the site being chosen, and the existing operator stores in the same at-most-one row per hex."""
    has_free_op, hex_start, share_int, cap_int, is_new = rows.has_free_op, rows.hex_start, rows.share_int, rows.cap_int, rows.is_new
    model = cp_model.CpModel()
    y = {int(s): model.NewBoolVar(f"y{s}") for s in np.flatnonzero(is_new)}
    model.Add(sum(y.values()) == p.scenario.n_new)
    terms: list[cp_model.IntVar] = []
    coeffs: list[int] = []
    x: list[tuple[int, int, cp_model.IntVar]] = []
    covered: list[tuple[int, cp_model.IntVar]] = []
    row_of: dict[int, list[tuple[cp_model.IntVar, int]]] = {}
    site_l, constrained_l, share_l = rows.pair_site.tolist(), rows.pair_constrained.tolist(), share_int.tolist()
    const = int(share_int[np.unique(rows.pair_hex[has_free_op[rows.pair_hex]])].sum())
    for h in np.flatnonzero(np.diff(hex_start) > 0).tolist():
        if has_free_op[h]:
            continue
        w, row = share_l[h], []
        lo, hi = hex_start[h], hex_start[h + 1]
        free = [s for s, c in zip(site_l[lo:hi], constrained_l[lo:hi]) if not c]
        if free:
            cover = model.NewBoolVar("")
            model.AddBoolOr([y[s] for s in free]).OnlyEnforceIf(cover)
            covered.append((h, cover))
            row.append(cover)
        for s, c in zip(site_l[lo:hi], constrained_l[lo:hi]):
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
    return Model(model, y, x, covered, rows.constrained, share_int)


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
    status: Status
    objective: float | None          # orders a day; None when CP-SAT found no plan
    solver_bound: float | None       # the solver's own bound, None when it has none
    search_start: float              # perf_counter when the search began
    greedy_owner: npt.NDArray[np.intp] | None = None   # the greedy plan's owner per hex when the method computed one (greedy, CP-SAT from greedy)


def kept_greedy(start: tuple[list[int], npt.NDArray[np.intp]], share_int: npt.NDArray[np.int64], bound: float | None, search_start: float) -> Solved:
    """Greedy's plan kept by CP-SAT from greedy: status HEURISTIC, objective greedy's orders on the solver's integer scale."""
    return Solved(picked=start[0], owner=start[1], status="HEURISTIC", objective=int(share_int[start[1] >= 0].sum()) / assumptions.SCALE,
                  solver_bound=bound, search_start=search_start, greedy_owner=start[1])


def cpsat(p: Problem, t0: float, from_greedy: bool) -> Solved:
    start = greedy(p) if from_greedy else None
    rows = model_rows(p)
    if rows.n_pairs > assumptions.MODEL_PAIR_CAP:   # the build loop is outside the solver's time limit: a model this big would overrun the budget (#33)
        search_start = time.perf_counter()
        if start is None:
            return Solved([], p.base, "UNKNOWN", None, None, search_start)
        return kept_greedy(start, rows.share_int, None, search_start)
    m = build_model(p, rows)
    if start is not None:
        hint(m, *start)
    search_start = time.perf_counter()
    solver = cp_model.CpSolver()
    solver.parameters.max_time_in_seconds = max(assumptions.PLAN_BUDGET - (search_start - t0), 0.1)
    solver.parameters.num_workers = assumptions.WORKERS
    solver.parameters.random_seed = assumptions.SOLVER_SEED
    status = solver.Solve(m.model)
    found = status in (cp_model.OPTIMAL, cp_model.FEASIBLE)
    if start is None and not found:   # no new sites: the plan reports the existing network alone (#27, #33)
        return Solved([], p.base, "UNKNOWN", None, None, search_start)
    if start is not None:
        floor = int(m.share_int[start[1] >= 0].sum())   # greedy's orders, on the solver's integer scale
        if not found or round(solver.ObjectiveValue()) < floor:   # never below greedy (even under an OPTIMAL status: greedy checks capacity in floats, the model in hundredths, so a rounding edge can favour greedy); with no solution the bound says nothing
            return kept_greedy(start, m.share_int, solver.BestObjectiveBound() / assumptions.SCALE if found else None, search_start)
    picked = sorted(s for s, v in m.y.items() if solver.Value(v))
    proven: Status = "OPTIMAL" if status == cp_model.OPTIMAL else "FEASIBLE"
    return Solved(picked=picked, owner=assignment(p, m, picked, solver), status=proven, objective=solver.ObjectiveValue() / assumptions.SCALE,
                  solver_bound=solver.BestObjectiveBound() / assumptions.SCALE, search_start=search_start, greedy_owner=None if start is None else start[1])


def capacity_bound(p: Problem) -> float:
    """A cheap upper bound on the orders a day any choice of the scenario's new sites can cover: the lower of (a) the share of every hex some
    open site reaches, and (b) what the existing stores and the n_new best candidate sites can serve at most, a site serving no more than
    min(capacity, the share it reaches). It ignores which hexes the stores share, so it is loose, but it exists when CP-SAT has no bound."""
    reach, n_sites = p.reach, len(p.inputs.site_ids)
    is_open = p.candidate.copy()
    is_open[p.existing] = True
    reached = np.zeros(len(p.share), bool)
    reached[reach.hex[is_open[reach.site]]] = True
    served_if_open = np.minimum(np.bincount(reach.site, weights=p.share[reach.hex], minlength=n_sites), p.capacity)
    best_new = np.sort(served_if_open[p.candidate])[::-1][:p.scenario.n_new]
    return float(min(p.share[reached].sum(), served_if_open[p.existing].sum() + best_new.sum()))


def stated_bound(p: Problem, method: Method, solved: Solved) -> float | None:
    """The bound a plan states: None for greedy and when there is no objective. CP-SAT's plans always state one: the lower of the solver's bound and
    `capacity_bound` (the fallback alone where the solver has none), and never under the objective: it is on the solver's integer scale, the fallback
    in float shares, so rounding must not put the bound under the plan's own claim."""
    if method == "greedy" or solved.objective is None:
        return None
    fallback = capacity_bound(p)
    bound = fallback if solved.solver_bound is None else min(solved.solver_bound, fallback)
    return max(bound, solved.objective)


def relative_gap(objective: float, bound: float, status: Status) -> float | None:
    """(bound - objective) / objective, as 03-area defined it: 0 when proven optimal or the bound is no higher; None for a zero objective under a positive bound
    (no finite ratio, and JSON has no infinity). Never negative: a greedy plan kept in place of the solver's can sit a rounding hair above the integer-scale bound."""
    if status == "OPTIMAL" or bound <= objective:
        return 0.0
    return None if objective <= 0 else (bound - objective) / objective


def plan(inputs: Inputs | None = None, scenario: Scenario | None = None, method: Method = "greedy") -> Plan:
    """Plan the scenario's new stores with `method`: the greedy, CP-SAT on its own, or CP-SAT started from the greedy plan.
    The whole call, `load_inputs` excluded, aims at `assumptions.PLAN_BUDGET` plus the metrics."""
    if method not in METHODS:
        raise ValueError(f"unknown method {method!r}")
    inputs = load_inputs() if inputs is None else inputs
    t0 = time.perf_counter()
    p = Problem.build(inputs, Scenario() if scenario is None else scenario)
    if method == "greedy":
        search_start = time.perf_counter()
        picked, owner = greedy(p)
        solved = Solved(picked=picked, owner=owner, status="HEURISTIC", objective=float(p.share[owner >= 0].sum()), solver_bound=None,
                        search_start=search_start, greedy_owner=owner)
    else:
        solved = cpsat(p, t0, method == "cpsat-from-greedy")
    searched = time.perf_counter()
    bound = stated_bound(p, method, solved)
    gap = None if bound is None or solved.objective is None else relative_gap(solved.objective, bound, solved.status)
    covered, households, lost, unreached, slow, new_stores = metrics(p, solved.picked, solved.owner)
    greedy_owner = solved.greedy_owner if solved.greedy_owner is not None else greedy(p)[1]   # CP-SAT on its own: greedy runs here, after the search, so the solver's budget and search are unchanged
    return Plan(p.scenario, method, [str(inputs.site_ids[s]) for s in solved.picked],
                {b: [str(inputs.site_ids[s]) for s in ss] for b, ss in p.network.items()},
                covered, households, lost, unreached, slow, new_stores, service_areas(p, p.existing + solved.picked, solved.owner),
                catchments(p, p.existing + solved.picked), float(p.share[greedy_owner >= 0].sum()), solved.status, solved.objective, bound, gap,
                solved.search_start - t0, searched - solved.search_start, time.perf_counter() - t0)


def hex_ids_by_store(p: Problem, stores: list[int], site: npt.NDArray[np.intp], hexes: npt.NDArray[np.intp]) -> dict[str, list[str]]:
    """Each store's hex ids, in hex position order, from (site, hex) position pairs."""
    order = np.lexsort((hexes, site))
    site, hexes = site[order], hexes[order]
    return {str(p.inputs.site_ids[s]): p.inputs.hex_ids[hexes[np.searchsorted(site, s):np.searchsorted(site, s, "right")]].tolist() for s in stores}


def service_areas(p: Problem, stores: list[int], owner: npt.NDArray[np.intp]) -> dict[str, list[str]]:
    """Each store's service area: the hexes `owner` (the store's site position per hex, -1 for none) assigns it."""
    assigned = np.flatnonzero(owner >= 0)
    return hex_ids_by_store(p, stores, owner[assigned], assigned)


def catchments(p: Problem, stores: list[int]) -> dict[str, list[str]]:
    """Each store's catchment: the pairs already in `p.reach`, within the promise at the multiplier, pick-and-pack included."""
    keep = np.isin(p.reach.site, stores)
    return hex_ids_by_store(p, stores, p.reach.site[keep], p.reach.hex[keep])


def metrics(p: Problem, picked: list[int], owner: npt.NDArray[np.intp]) -> tuple[float, float, float, float, float, list[NewStore]]:
    """demand_covered, households_covered, lost_to_capacity, unreached, slow_traffic_coverage and the new stores, for any method's picks and assignment."""
    inputs, share, reach = p.inputs, p.share, p.reach
    got = owner >= 0
    reached = np.zeros(len(share), bool)
    reached[reach.hex[np.isin(reach.site, p.existing + picked)]] = True
    new_stores: list[NewStore] = []
    for s in picked:
        mine = owner == s
        orders, moved = float(share[mine].sum()), float(share[mine & (p.base >= 0)].sum())
        new_stores.append(NewStore(str(inputs.site_ids[s]), orders, orders - moved, moved))
    covered = float(share[got].sum())
    slow = min(cover_at_slow_traffic(inputs, p.scenario, p.existing + picked, share, p.capacity), covered)   # a time-limited CP-SAT assignment can cover less than the walk does (#33)
    return covered, float(inputs.households[got].sum()), float(share[reached & ~got].sum()), float(share[~reached].sum()), slow, new_stores
