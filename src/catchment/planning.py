"""Plan new stores for a scenario: the synthetic network, a greedy plan and its metrics. `plan()` is the one entry point."""
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Literal

import numpy as np
import numpy.typing as npt
import pandas as pd

from catchment import assumptions
from catchment.build import demand_name, reach_names
from catchment.fetch import DATA

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
            if not isinstance(value, int) or isinstance(value, bool):
                raise TypeError(f"{lever} {value!r} must be a whole number")
        if isinstance(self.competitor_density, bool):
            raise TypeError(f"competitor_density {self.competitor_density!r} must be a number")
        for lever, (low, high) in LEVER_RANGES.items():
            value = getattr(self, lever)
            if not low <= value <= high:
                raise ValueError(f"{lever} {value:g} is outside the lever range {low:g}-{high:g}")
        if self.competitor_density % assumptions.COMPETITOR_DENSITY_STEP:
            raise ValueError(f"competitor_density {self.competitor_density:g} is not in steps of {assumptions.COMPETITOR_DENSITY_STEP:g}")


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
    """The new sites for one scenario, and the network they were planned against."""
    scenario: Scenario
    method: str
    sites: list[str]                 # the new sites, in pick order
    network: dict[str, list[str]]    # brand -> the sites of its existing stores
    demand_covered: float            # the operator's orders a day assigned to a store
    households_covered: float        # households of the assigned hexes, whole hexes
    lost_to_capacity: float          # reached by an open operator store but not assigned
    unreached: float                 # reached by no open operator store
    new_stores: list[NewStore]       # in pick order
    seconds: float                   # inside plan(), load_inputs excluded


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
            if owner[h] < 0 and load[s] + shares[h] <= capacity:
                owner[h], load[s] = s, load[s] + shares[h]
        return np.array(owner, dtype=np.intp)

    def pairs_of(self, hexes: npt.NDArray[np.intp]) -> npt.NDArray[np.intp]:
        """Positions of the pairs of the given hexes."""
        first, length = self.start[hexes], self.start[hexes + 1] - self.start[hexes]
        return self.by_hex[np.repeat(first - (np.cumsum(length) - length), length) + np.arange(length.sum())]


def plan(inputs: Inputs | None = None, scenario: Scenario | None = None, method: Literal["greedy"] = "greedy") -> Plan:
    if method != "greedy":
        raise ValueError(f"unknown method {method!r}")
    inputs = load_inputs() if inputs is None else inputs
    t0 = time.perf_counter()
    scenario = Scenario() if scenario is None else scenario
    network = place_network(inputs, scenario.seed, scenario.competitor_density)
    n_sites, capacity = len(inputs.site_ids), scenario.capacity * assumptions.CAPACITY
    ok = reachable(inputs, scenario.promise, scenario.multiplier)
    rival = np.zeros(len(inputs.demand), bool)
    rival[inputs.pair_hex[ok & np.isin(inputs.pair_site, network["Competitor"])]] = True
    share = inputs.demand * scenario.capture / (1 + rival)   # ADR 0001
    existing = network["Operator"]
    candidate = np.ones(n_sites, bool)
    candidate[[s for ss in network.values() for s in ss]] = False
    if scenario.n_new > candidate.sum():
        raise ValueError(f"{scenario.n_new} new stores asked for, only {candidate.sum()} open candidate sites hold no store")
    reach = Reach.build(inputs, ok)
    picked: list[int] = []
    base = owner = reach.assign(existing, share, capacity, n_sites)
    gain = np.bincount(reach.site, weights=np.where(owner < 0, share, 0.0)[reach.hex], minlength=n_sites)   # unassigned share each site reaches, before the cap
    for _ in range(scenario.n_new):
        best = int(np.argmax(np.where(candidate, np.minimum(gain, capacity).round(GAIN_DP), -1.0)))   # rounded: float deltas must not break exact ties
        picked.append(best)
        candidate[best] = False
        now = reach.assign(existing + picked, share, capacity, n_sites)
        flipped = np.flatnonzero((now < 0) != (owner < 0))   # only these hexes change the gain: +share if newly unassigned, -share if newly assigned
        delta = np.zeros(len(share))
        delta[flipped] = np.where(now[flipped] < 0, share[flipped], -share[flipped])
        pairs = reach.pairs_of(flipped)
        gain += np.bincount(reach.site[pairs], weights=delta[reach.hex[pairs]], minlength=n_sites)
        owner = now
    got = owner >= 0
    reached = np.zeros(len(share), bool)
    reached[reach.hex[np.isin(reach.site, existing + picked)]] = True
    new_stores: list[NewStore] = []
    for s in picked:
        mine = owner == s
        orders, moved = float(share[mine].sum()), float(share[mine & (base >= 0)].sum())
        new_stores.append(NewStore(str(inputs.site_ids[s]), orders, orders - moved, moved))
    return Plan(scenario, method, [str(inputs.site_ids[s]) for s in picked],
                {b: [str(inputs.site_ids[s]) for s in ss] for b, ss in network.items()},
                float(share[got].sum()), float(inputs.households[got].sum()), float(share[reached & ~got].sum()), float(share[~reached].sum()), new_stores, time.perf_counter() - t0)
