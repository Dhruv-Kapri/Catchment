"""Small synthetic `Inputs` on real H3 res-9 cells near the area's centre, so the web map can draw them."""
import h3
import numpy as np
import pandas as pd

from catchment.assumptions import ORDERS_PER_STORE_DAY
from catchment.planning import Inputs

CENTRE: str = h3.latlng_to_cell(28.48, 77.10, 9)
STORES: int = 12   # the synthetic network's size: 8 Operator, 4 Competitor


def service_inputs() -> Inputs:
    """61 cells (a disk of radius 4), each a candidate site and a hex. A site reaches only its own hex, and every hex has its own demand,
    so the best plan is the one set of the richest open hexes, and CP-SAT cannot return another optimum between calls."""
    cells = sorted(h3.grid_disk(CENTRE, 4))
    weight = np.array([1 + (7 * i % 61) / 100 for i in range(len(cells))])
    demand = pd.DataFrame({"households": 100.0, "demand": STORES * ORDERS_PER_STORE_DAY * weight / weight.sum()}, index=pd.Index(cells))
    candidates = pd.DataFrame({"rank": range(len(cells))}, index=pd.Index(cells))
    table = pd.DataFrame({"candidate": cells, "hex": cells, "minutes": 0.5})
    return Inputs.from_frames(demand, candidates, table)
