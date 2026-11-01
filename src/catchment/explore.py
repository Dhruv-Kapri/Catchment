"""The exploration notebooks' placeholder plan model, shared by 01-reach, 02-plan and 03-area.

The stage 2 planning module is separate; this one keeps the stage 0.5 and 1 results reproducible as they were run.
"""
import time
from collections import defaultdict
from dataclasses import dataclass, replace

import numpy as np
import numpy.typing as npt
import pandas as pd
from ortools.sat.python import cp_model

from catchment.assumptions import (
    CAPACITY,
    PICK_AND_PACK,
    PROMISE,
    SCALE,
    SEED,
    SOLVER_SEED,
    TIME_LIMIT,
    WORKERS,
)

# Frozen at the values stages 0.5 and 1 ran with, on purpose not read from assumptions: stage 2 moves the
# default multiplier to 1.8 and replaces the placeholder network, and the notebooks must still reproduce.
MULTIPLIER: float = 1.4                 # the explore default scenario; stage 2 moves the default to 1.8
BRAND_COUNTS: dict[str, int] = {"Operator": 3, "Competitor A": 4, "Competitor B": 3}   # placeholder network, the slice
CAP_INT: int = round(CAPACITY * SCALE)  # capacity, hundredths of an order


def reachable(ff_min: float | npt.NDArray[np.float64] | pd.Series) -> bool | npt.NDArray[np.bool_] | pd.Series:
    """Hex reachable from a site: free-flow minutes x multiplier + pick-and-pack <= promise (default scenario)."""
    return ff_min * MULTIPLIER + PICK_AND_PACK <= PROMISE + 1e-9


@dataclass
class Case:
    res: int
    hexes: pd.Index
    demand: npt.NDArray[np.float64]       # orders per day per hex
    sites: pd.Index                       # candidate sites, in rank order
    rank: npt.NDArray[np.int64]           # places-count rank in the whole area, 0 = busiest
    ps: npt.NDArray[np.int64]             # reachable pairs: site position
    ph: npt.NDArray[np.int64]             # reachable pairs: hex position
    pm: npt.NDArray[np.float64]           # reachable pairs: free-flow minutes
    n_area_hexes: int                     # hexes in the whole area, to turn X% into a count
    stores: dict[str, list[int]]          # brand -> site positions
    k: npt.NDArray[np.int64]              # competitor brands reaching each hex
    share_int: npt.NDArray[np.int64]      # operator share of each hex if it serves it, hundredths of an order
    new_sites: npt.NDArray[np.int64]      # site positions open for a new store
    cap_int: int                          # capacity, hundredths of an order


@dataclass(frozen=True)
class SolveResult:
    status: str
    chosen: list[int]
    obj: float                            # the operator's orders a day
    bound: float                          # the solver's best proven upper bound on obj
    pairs: int                            # (site, hex) pairs in the model
    new_sites: int                        # sites the model may open
    hexes: int
    constrained_sites: int                # sites with W_s above capacity, which get x variables
    build_s: float
    solve_s: float
    total_s: float


def load_case(res: int, hexes: pd.DataFrame, candidates: pd.DataFrame, table: pd.DataFrame,
              n_area_hexes: int | None = None) -> Case:
    """Every hex of `hexes`, every candidate site in rank order, and the table's pairs reachable at the default
    scenario. n_area_hexes is the hex count of the whole area (default: len(hexes)); pass it when `hexes` is a slice."""
    cand = candidates.sort_values("rank")
    tab = table[reachable(table.minutes)]
    spos = pd.Series(np.arange(len(cand)), index=cand.index)
    hpos = pd.Series(np.arange(len(hexes)), index=hexes.index)
    d = hexes["demand"].to_numpy()
    return Case(res, hexes.index, d, cand.index, cand["rank"].to_numpy(), spos[tab.candidate].to_numpy(),
                hpos[tab.hex].to_numpy(), tab.minutes.to_numpy(), len(hexes) if n_area_hexes is None else n_area_hexes,
                {}, np.zeros(len(d), int), np.round(d * SCALE).astype(np.int64), np.arange(len(cand)), CAP_INT)


def place_network(C: Case, counts: dict[str, int] = BRAND_COUNTS, seed: int = SEED) -> dict[str, list[int]]:
    rng = np.random.default_rng(seed)
    reached = np.bincount(C.ps, weights=C.demand[C.ph], minlength=len(C.sites))
    chosen = rng.choice(len(C.sites), size=sum(counts.values()), replace=False, p=reached / reached.sum())
    labels = rng.permutation(np.repeat(list(counts), list(counts.values())))
    return {b: sorted(chosen[labels == b].tolist()) for b in counts}


def with_network(C: Case, stores: dict[str, list[int]], cap_int: int | None = None) -> Case:
    comp = [b for b in stores if b != "Operator"]
    hit = np.zeros((len(comp), len(C.hexes)), bool)
    for i, b in enumerate(comp):
        hit[i, C.ph[np.isin(C.ps, stores[b])]] = True
    k = hit.sum(axis=0)
    occupied = np.array(sorted(s for ss in stores.values() for s in ss))
    assert len(occupied) == len(set(occupied)), "two stores on one site"
    return replace(C, stores=stores, k=k, share_int=np.round(C.demand / (1 + k) * SCALE).astype(np.int64),
                   new_sites=np.setdiff1d(np.arange(len(C.sites)), occupied), cap_int=cap_int or C.cap_int)


def solve_plan(C: Case, N: int, new_sites: npt.NDArray[np.int64] | None = None, pair_model: bool = False,
               time_limit: float = TIME_LIMIT) -> SolveResult:
    """Choose N new sites from new_sites (default: all open ones) to maximise the operator's orders.
    pair_model=True builds the plain model (x for every pair); otherwise only sites with W_s > capacity get x."""
    t0 = time.perf_counter()
    new = C.new_sites if new_sites is None else new_sites
    op = np.array(C.stores["Operator"])
    is_new, is_op = np.zeros(len(C.sites), bool), np.zeros(len(C.sites), bool)
    is_new[new], is_op[op] = True, True
    keep = (is_new | is_op)[C.ps]
    ps, ph = C.ps[keep], C.ph[keep]
    reach_w = np.bincount(ps, weights=C.share_int[ph], minlength=len(C.sites))      # W_s
    constrained = np.ones(len(C.sites), bool) if pair_model else reach_w > C.cap_int
    model = cp_model.CpModel()
    y = {int(s): model.NewBoolVar(f"y{s}") for s in new}
    model.Add(sum(y.values()) == N)
    terms: list[cp_model.IntVar] = []
    coeffs: list[int] = []
    const = 0
    x_at: defaultdict[int, list[tuple[cp_model.IntVar, int]]] = defaultdict(list)
    for h, sites_h in pd.Series(ps).groupby(ph):
        sites_h = sites_h.to_numpy()
        w = int(C.share_int[h])
        free = sites_h[~constrained[sites_h]]
        if is_op[free].any():               # an existing store that cannot hit capacity covers this hex
            const += w
            continue
        row: list[cp_model.IntVar] = []
        if len(free):
            covered = model.NewBoolVar("")
            model.AddBoolOr([y[int(s)] for s in free]).OnlyEnforceIf(covered)
            row.append(covered)
        for s in sites_h[constrained[sites_h]]:
            xv = model.NewBoolVar("")
            if is_new[s]:
                model.AddImplication(xv, y[int(s)])
            x_at[int(s)].append((xv, w))
            row.append(xv)
        if len(row) > 1:
            model.AddAtMostOne(row)
        terms += row
        coeffs += [w] * len(row)
    for lst in x_at.values():
        model.Add(cp_model.LinearExpr.WeightedSum([v for v, _ in lst], [w for _, w in lst]) <= C.cap_int)
    model.Maximize(cp_model.LinearExpr.WeightedSum(terms, coeffs) + const)
    t1 = time.perf_counter()
    solver = cp_model.CpSolver()
    solver.parameters.max_time_in_seconds = time_limit
    solver.parameters.num_workers = WORKERS
    solver.parameters.random_seed = SOLVER_SEED
    status = solver.Solve(model)
    t2 = time.perf_counter()
    ok = status in (cp_model.OPTIMAL, cp_model.FEASIBLE)
    return SolveResult(status=solver.StatusName(status),
                       chosen=sorted(s for s in y if solver.Value(y[s])) if ok else [],
                       obj=solver.ObjectiveValue() / SCALE, bound=solver.BestObjectiveBound() / SCALE,
                       pairs=len(ps), new_sites=len(new), hexes=len(np.unique(ph)),
                       constrained_sites=int(constrained[np.unique(ps)].sum()),
                       build_s=t1 - t0, solve_s=t2 - t1, total_s=t2 - t0)


def evaluate(C: Case, open_sites: list[int], time_limit: float = 30) -> tuple[npt.NDArray[np.int64], int]:
    """Best assignment of hexes to the operator's open stores within capacity. Returns (owner per hex, orders x 100)."""
    keep = np.isin(C.ps, list(open_sites))
    ps, ph, pm = C.ps[keep], C.ph[keep], C.pm[keep]
    w = C.share_int[ph]
    model = cp_model.CpModel()
    x = [model.NewBoolVar("") for _ in range(len(ps))]
    for _, js in pd.Series(np.arange(len(ps))).groupby(ph):
        if len(js) > 1:
            model.AddAtMostOne([x[j] for j in js])
    for _, js in pd.Series(np.arange(len(ps))).groupby(ps):
        js = js.to_numpy()
        model.Add(cp_model.LinearExpr.WeightedSum([x[j] for j in js], [int(w[j]) for j in js]) <= C.cap_int)
    served = cp_model.LinearExpr.WeightedSum(x, [int(v) for v in w])
    model.Maximize(served)                      # stage 1: orders served; always solved to optimality
    solver = cp_model.CpSolver()
    solver.parameters.num_workers = 1
    solver.parameters.random_seed = SOLVER_SEED
    solver.parameters.max_time_in_seconds = time_limit
    status = solver.Solve(model)
    assert status == cp_model.OPTIMAL, solver.StatusName(status)
    best = round(solver.ObjectiveValue())
    for v in x:
        model.AddHint(v, solver.Value(v))
    model.Add(served == best)                   # stage 2: the same orders, the least total travel time (hundredths of a minute)
    model.Minimize(cp_model.LinearExpr.WeightedSum(x, [round(float(m) * 100) for m in pm]))
    solver.parameters.max_time_in_seconds = 5   # best effort: stage 1 fixes the orders, this only picks among ties
    status = solver.Solve(model)
    assert status in (cp_model.OPTIMAL, cp_model.FEASIBLE), solver.StatusName(status)
    owner = np.full(len(C.hexes), -1)
    for j in np.flatnonzero([solver.Value(v) for v in x]):
        owner[ph[j]] = ps[j]
    assert int(C.share_int[owner >= 0].sum()) == best
    return owner, best


def greedy_plan(C: Case, N: int) -> list[int]:
    opened: list[int] = list(C.stores["Operator"])
    picked: list[int] = []
    cands = C.new_sites.copy()
    for _ in range(N):
        owner, _ = evaluate(C, opened)
        unserved = np.where(owner < 0, C.share_int, 0)
        value = np.minimum(np.bincount(C.ps, weights=unserved[C.ph], minlength=len(C.sites))[cands], C.cap_int)
        s = int(cands[np.argmax(value)])      # first maximum: the lowest rank
        picked.append(s)
        opened.append(s)
        cands = cands[cands != s]
    return picked
