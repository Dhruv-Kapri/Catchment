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
                raise ValueError(f"{lever} {value!r} must be a whole number")
        for lever, (low, high) in LEVER_RANGES.items():
            value = getattr(self, lever)
            if not low <= value <= high:
                raise ValueError(f"{lever} {value:g} is outside the lever range {low:g}-{high:g}")


@dataclass(frozen=True)
class NewStore:
    """What one new store serves, in the operator's orders a day."""
    site: str
    orders: float          # the share of the hexes assigned to it
    fresh: float           # the part no existing operator store served in the base assignment
    cannibalised: float    # the part an existing operator store served


@dataclass(frozen=True)
class Plan:
    """The new sites for one scenario, the network they were planned against, and the metrics."""
    scenario: Scenario
    method: str
    sites: list[str]                 # the new sites, in pick order
    network: dict[str, list[str]]    # brand -> the sites of its existing stores
    demand_covered: float            # the operator's orders a day assigned to a store
    households_covered: float        # households of the assigned hexes, whole hexes
    new_stores: list[NewStore]       # in pick order
    lost_to_capacity: float          # reached by an open operator store but not assigned
    unreached: float                 # reached by no open operator store
    seconds: float                   # inside plan(), load_inputs excluded


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


def assign(inputs: Inputs, ok: npt.NDArray[np.bool_], stores: list[int], share: npt.NDArray[np.float64], capacity: float) -> npt.NDArray[np.intp]:
    """Owner site per hex (-1: none). Nearest store first, a hex wholly to one store, a store only up to its capacity."""
    keep = ok & np.isin(inputs.pair_site, stores)
    site, hex_, minutes = inputs.pair_site[keep], inputs.pair_hex[keep], inputs.pair_min[keep]
    owner, load = np.full(len(share), -1, dtype=np.intp), np.zeros(len(inputs.site_ids))
    for j in np.lexsort((hex_, site, minutes)).tolist():
        s, h = site[j], hex_[j]
        if owner[h] < 0 and load[s] + share[h] <= capacity:
            owner[h], load[s] = s, load[s] + share[h]
    return owner


def plan(inputs: Inputs | None = None, scenario: Scenario | None = None, method: Literal["greedy"] = "greedy") -> Plan:
    if method != "greedy":
        raise ValueError(f"unknown method {method!r}")
    inputs = load_inputs() if inputs is None else inputs
    t0 = time.perf_counter()
    scenario = Scenario() if scenario is None else scenario
    network = place_network(inputs, scenario.seed)
    n_sites, capacity = len(inputs.site_ids), scenario.capacity * assumptions.CAPACITY
    ok = reachable(inputs, scenario.promise, scenario.multiplier)
    demand = inputs.demand * scenario.capture
    rival = np.zeros(len(demand), bool)
    rival[inputs.pair_hex[ok & np.isin(inputs.pair_site, network["Competitor"])]] = True
    share = demand / (1 + rival)                                   # ADR 0001
    existing = network["Operator"]
    base = assign(inputs, ok, existing, share, capacity)
    candidate = np.ones(n_sites, bool)
    candidate[[s for ss in network.values() for s in ss]] = False
    if scenario.n_new > candidate.sum():
        raise ValueError(f"{scenario.n_new} new stores asked for, only {candidate.sum()} open candidate sites hold no store")
    picked: list[int] = []
    owner = base
    for _ in range(scenario.n_new):
        gain = np.minimum(np.bincount(inputs.pair_site[ok], weights=np.where(owner < 0, share, 0.0)[inputs.pair_hex[ok]], minlength=n_sites), capacity)
        best = int(np.argmax(np.where(candidate, gain, -1.0)))
        picked.append(best)
        candidate[best] = False
        owner = assign(inputs, ok, existing + picked, share, capacity)
    got = owner >= 0
    reached = np.zeros(len(demand), bool)
    reached[inputs.pair_hex[ok & np.isin(inputs.pair_site, existing + picked)]] = True
    new_stores: list[NewStore] = []
    for s in picked:
        mine = owner == s
        orders, moved = float(share[mine].sum()), float(share[mine & (base >= 0)].sum())
        new_stores.append(NewStore(str(inputs.site_ids[s]), orders, orders - moved, moved))
    return Plan(scenario, method, [str(inputs.site_ids[s]) for s in picked], {b: [str(inputs.site_ids[s]) for s in ss] for b, ss in network.items()},
                float(share[got].sum()), float(inputs.households[got].sum()), new_stores,
                float(share[reached & ~got].sum()), float(share[~reached].sum()), time.perf_counter() - t0)
