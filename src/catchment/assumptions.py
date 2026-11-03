"""Every labelled assumption the model rests on, with source, date and status. Build code reads them from here."""
import pandas as pd

HOUSEHOLD_SIZE: float = 4.5             # persons per household, one value for every hex
M_LOW: float = 0.5                      # affluence multiplier bounds
M_HIGH: float = 1.5

# Capture-share calibration inputs
BLINKIT_ORDERS_Q2: float = 398.9e6      # Blinkit orders, Q2 FY27 (Jul-Sep 2026)
Q2_DAYS: int = 92
BLINKIT_STORES: int = 2751              # at quarter end
COMPETITOR_STORES: int = 1240           # next-largest brand (Instamart), active dark stores at the end of Q2 FY27
NCR_STORES: int = 400                   # dark stores, all brands, NCR
NCR_POPULATION: float = 30.2e6          # "New Delhi" Degree of Urbanisation city, WUP 2025, 2025 estimate

# Lever ranges, inclusive (decision log, 2026-11-01)
N_RANGE: tuple[int, int] = (1, 20)
PROMISE_RANGE: tuple[int, int] = (8, 16)                # minutes; narrowed from 8-20 by the 04-plan benchmark (#30)
MULTIPLIER_RANGE: tuple[float, float] = (1.0, 2.5)
CAPACITY_RANGE: tuple[float, float] = (0.5, 2.0)        # x the default capacity
CAPTURE_RANGE: tuple[float, float] = (0.5, 1.5)         # x the default capture share
COMPETITOR_DENSITY_RANGE: tuple[float, float] = (0.0, 2.0)   # x the default competitor store count
COMPETITOR_DENSITY_STEP: float = 0.25   # density moves in quarters

PICK_AND_PACK: int = 3                  # minutes, fixed
MAX_PROMISE: int = 20                   # longest promise the travel-time table keeps pairs for, minutes (the lever now stops at 16)
SLOW_TRAFFIC_FACTOR: float = 1.25       # slow-traffic coverage, x the scenario's congestion multiplier

# Plan: default scenario, capacity, synthetic network, solver
PROMISE: int = 10                       # default scenario
MULTIPLIER: float = 1.8                 # default scenario (the spot check, decision log 2026-11-01)
N_SLICE: int = 3                        # new stores: the slice
N_AREA: int = 10                        # new stores: the full area (default scenario)
CAPACITY_FACTOR: float = 1.5
SEED: int = 2026                        # network placement
SCALE: int = 100                        # shares and capacity are integers in hundredths of an order
TIME_LIMIT: int = 60
PLAN_BUDGET: float = 9.0                # seconds for everything in plan() before the metrics: the 10 s bar minus 1 s
# Measured on the full area (res 9, 30%), 8 GB Apple Silicon: build_model takes 21-23 us per capacity-bound (x) pair (14,256 pairs 0.4 s; 247,000 5.5 s;
# 264,753 5.7 s; 624,601 14.5 s). Above the cap the model is not built: 200,000 pairs is about 4.5 s, the most of the 9 s budget the build can take. Default scenario: 20 pairs.
MODEL_PAIR_CAP: int = 200_000
WORKERS: int = 8
SOLVER_SEED: int = 1

ORDERS_PER_STORE_DAY: float = BLINKIT_ORDERS_Q2 / Q2_DAYS / BLINKIT_STORES
OPERATOR_SHARE: float = BLINKIT_STORES / (BLINKIT_STORES + COMPETITOR_STORES)   # of the synthetic network's stores
AREA_NETWORK_SIZE: int = 57             # network_size on the full area; only for the table text, the planner computes it
NCR_HOUSEHOLDS: float = NCR_POPULATION / HOUSEHOLD_SIZE
# calibration target: all-brand orders per household per day
ORDERS_PER_HOUSEHOLD_DAY: float = NCR_STORES * ORDERS_PER_STORE_DAY / NCR_HOUSEHOLDS
SECOND_ROAD_MAX_M: int = 100            # a point's second road counts for snapping only within this distance
SECOND_ROAD_GAP_M: int = 5              # and only if it lies more than this across the first road
MAX_PAIR_MIN: int = MAX_PROMISE - PICK_AND_PACK   # free-flow minutes kept in the travel-time table
CAPACITY: float = CAPACITY_FACTOR * ORDERS_PER_STORE_DAY   # orders per store per day


def network_size(area_demand: float) -> int:
    """Stores in the synthetic network: the area's demand over the orders per store per day."""
    return round(area_demand / ORDERS_PER_STORE_DAY)


def brand_split(n_stores: int) -> dict[str, int]:
    """The network's stores by brand, split by the reported store counts."""
    operator = round(n_stores * OPERATOR_SHARE)
    return {"Operator": operator, "Competitor": n_stores - operator}


def table() -> pd.DataFrame:
    """The assumptions as a table: Input, Value, Source, Date, Status."""
    return pd.DataFrame(
        [
            ("Household size", f"{HOUSEHOLD_SIZE} persons", "NFHS-5 (2019-21) Haryana state report, IIPS/MoHFW, Table 4 (urban mean household size). https://dhsprogram.com/pubs/pdf/FR374/FR374_Haryana.pdf", "2026-10-29", "Verified"),
            ("Multiplier bounds", f"{M_LOW} to {M_HIGH}", "No external source; a labelled assumption (decision log, 2026-10-29)", "-", "Assumption"),
            ("Blinkit orders, Q2 FY27", f"{BLINKIT_ORDERS_Q2/1e6:.1f} M over {Q2_DAYS} days", "Eternal Ltd shareholders' letter, 21 Oct 2026 (BSE filing), https://www.bseindia.com/xml-data/corpfiling/AttachLive/cbfbd146-6a68-43d6-9cbc-dfb7d0f50fd0.pdf, p. 13, Quick commerce operating metrics, row Orders (398.9 million). The 92 days are ours; the letter does not state them", "2026-10-29", "Verified"),
            ("Blinkit stores", f"{BLINKIT_STORES:,} at quarter end", "Eternal Ltd shareholders' letter, 21 Oct 2026 (BSE filing), https://www.bseindia.com/xml-data/corpfiling/AttachLive/cbfbd146-6a68-43d6-9cbc-dfb7d0f50fd0.pdf, p. 13, Quick commerce operating metrics, row Stores at the end of the period (#); also p. 6", "2026-10-29", "Verified"),
            ("Competitor stores (next-largest brand)", f"{COMPETITOR_STORES:,} at quarter end", "Swiggy Ltd Q2 FY27 shareholders' letter, 22 Oct 2026, https://www.swiggy.com/corporate/wp-content/uploads/2026/10/Q2-FY2027-Shareholder-letter.pdf, p. 7, Quick commerce operating metrics, row Active Dark Stores (Exit) (1,240 at 30 Sep 2026; also pp. 2 and 4; definition p. 19: dark stores with at least one completed order on the last day of the period). Next-largest brand because Zepto reported 1,139 dark stores at 31 Mar 2026 (updated DRHP, June 2026, as reported by the press; not checked at primary source) and Instamart's count is larger and more recent (no later Zepto count is reported). Eternal gives no definition of its store count, so the two counts may not be defined alike", "2026-11-01", "Verified"),
            ("NCR dark stores (all brands)", f"~{NCR_STORES}", "Savills India Research, Q-Commerce Growth: Dark Stores Shaping the Future of Retail, Dec 2025, https://pdf.savills.asia/asia-pacific-research/india-research/q-commerce-growth---dark-stores-shaping-the-future-of-retail.pdf, p. 8, Delhi-NCR 400. Best-effort estimate as of Oct 2025; not broken down by brand (all brands is our reading)", "2026-10-29", "Verified"),
            ("NCR population", f"{NCR_POPULATION/1e6:.1f} M", "UN DESA World Urbanization Prospects: The 2025 Revision, File 21 (WUP2025-F21-DEGURBA-Cities_Pop.xlsx, POP/DB/WUP/Rev.2025/F21), India, City_Code 8364 \"New Delhi\", 2025 column: 30,222.405 thousand. https://population.un.org/wup/assets/Download/Cities/WUP2025-F21-DEGURBA-Cities_Pop.xlsx. A Degree of Urbanisation city (contiguous 1 km2 cells of at least 1,500 people per km2), not an agglomeration; Gurgaon, Faridabad, Ghaziabad and Noida have no separate entry, so they fall inside it (inference). See decision log, 2026-10-29", "2026-10-29", "Verified"),
            ("Pick-and-pack allowance", f"{PICK_AND_PACK} min, fixed", "Decision log, 2026-10-29 (Explore)", "2026-10-29", "Assumption"),
            ("Pairs kept in the table", f"Free-flow ≤ {MAX_PAIR_MIN} min (longest promise {MAX_PROMISE} − {PICK_AND_PACK} at multiplier 1.0)", "Decision log, 2026-10-29 (Explore)", "2026-10-29", "Assumption"),
            ("Second road for snapping", f"Each point snaps to its nearest road and a second road, and a pair keeps the fastest of the four times. The second road is the nearest hit within {SECOND_ROAD_MAX_M} m that lies more than {SECOND_ROAD_GAP_M} m from the first across the road (a parallel carriageway, not the next segment of the same one); none, then the nearest road repeats", "No external source; 01-reach found about one short pair in seven running out and back at an endpoint. Decision log, 2026-10-29 (fastest-of-four snapping, measured)", "-", "Assumption"),
            ("Default scenario", f"Promise {PROMISE} min, congestion multiplier {MULTIPLIER}, pick-and-pack {PICK_AND_PACK} min: a hex is reachable if free-flow min × {MULTIPLIER} + {PICK_AND_PACK} ≤ {PROMISE}, that is free-flow ≤ {(PROMISE - PICK_AND_PACK) / MULTIPLIER:.1f} min", "Spot check (docs/spot-check.csv): implied median multiplier 1.79 over 20 routes, Google Maps two-wheeler, Fri 30 Oct 2026 19:00-19:07, one evening's live estimates; decision log, 2026-11-01 (Plan scope). Was 1.4, an unmeasured guess: 02-plan and 03-area ran at 1.4", "2026-11-01", "Assumption"),
            ("Lever ranges", f"N {N_RANGE[0]}-{N_RANGE[1]}; promise {PROMISE_RANGE[0]}-{PROMISE_RANGE[1]} min; congestion multiplier {MULTIPLIER_RANGE[0]}-{MULTIPLIER_RANGE[1]}; capacity {CAPACITY_RANGE[0]}×-{CAPACITY_RANGE[1]}× the default; capture share {CAPTURE_RANGE[0]}×-{CAPTURE_RANGE[1]}× the default; competitor density {COMPETITOR_DENSITY_RANGE[0]:g}×-{COMPETITOR_DENSITY_RANGE[1]:g}× the default, in steps of {COMPETITOR_DENSITY_STEP:g}, default 1×. All inclusive", "Decision log, 2026-11-01 (Plan scope); promise narrowed from 8-20 to 8-16, decision log 2026-11-03 (benchmark, #30)", "2026-11-03", "Assumption"),
            ("Slow-traffic factor", f"{SLOW_TRAFFIC_FACTOR}× the scenario's congestion multiplier: slow-traffic coverage is the demand the plan's stores (existing and new) still cover then, with each hex's competitor split held at the scenario's", "Decision log, 2026-11-01 (Plan scope); no external source", "2026-11-01", "Assumption"),
            ("New stores, N", f"{N_SLICE} on the slice; {N_AREA} on the full area (the default scenario)", "Decision log, 2026-10-29 (Explore)", "2026-10-29", "Assumption"),
            ("Orders per store per day", f"{BLINKIT_ORDERS_Q2/1e6:.1f} M orders ÷ {Q2_DAYS} days ÷ {BLINKIT_STORES:,} stores = {ORDERS_PER_STORE_DAY:,.0f}", "00-demand: Eternal Ltd shareholders' letter, 21 Oct 2026, p. 13 (orders and stores)", "2026-10-29", "Verified"),
            ("Capacity per store", f"{CAPACITY_FACTOR} × {ORDERS_PER_STORE_DAY:,.0f} = {CAPACITY:,.0f} orders per day, the same for every store of the operator. Adopted here as 00-demand and the decision log said; the 1.5 has no source (headroom over the average)", "Decision log, 2026-10-29 (Explore); issue #5. Rests on the Verified orders per store per day", "2026-10-29", "Assumption"),
            ("Network size", f"Area demand ÷ orders per store per day = {ORDERS_PER_STORE_DAY:,.0f}, rounded: about {AREA_NETWORK_SIZE} stores on the full area. Equals the NCR store count × the area's population share, because the capture share is calibrated on the same figures", "Decision log, 2026-11-01 (Plan scope); rests on the Verified orders per store per day", "2026-11-01", "Assumption"),
            ("Operator/competitor split", f"Operator {OPERATOR_SHARE:.1%}, competitor {1 - OPERATOR_SHARE:.1%} of the stores (Blinkit {BLINKIT_STORES:,}, competitor {COMPETITOR_STORES:,}); at {AREA_NETWORK_SIZE} stores, {brand_split(AREA_NETWORK_SIZE)['Operator']} and {brand_split(AREA_NETWORK_SIZE)['Competitor']}", "Decision log, 2026-11-01 (Plan scope); rests on the two reported store counts, both Verified", "2026-11-01", "Assumption"),
            ("Store placement", f"Sampled without replacement from the area's candidate sites, probability ∝ the demand the site reaches at the default promise and multiplier; the operator's stores placed first and fixed, then one seeded ordering of the remaining sites, of which the competitor's stores at density d are the first round(d × the default count), so a denser network contains a sparser one; seed {SEED}; at most one store per site, whatever the brand", "No external source", "-", "Assumption"),
            ("Competitor reach", "A competitor store at a site reaches the same hexes as an operator store there (same promise, multiplier and travel times)", "No external source", "-", "Assumption"),
            ("Demand split", "A hex reached by the operator and k competitor brands gives the operator demand ÷ (1 + k); k is fixed in a scenario", "ADR 0001", "2026-10-29", "Assumption"),
            ("Sites for new stores", "Any candidate site with no store on it, of any brand", "No external source", "-", "Assumption"),
            ("Assignment tie-break", "Greedy assigns each hex to its nearest open store with capacity left (nearest-first walk), which decides new against cannibalised demand. CP-SAT maximises orders only: a hex no capacity-bound store takes goes to its nearest open store, but among capacity-bound stores serving the same orders the solver's assignment stands, so its fresh/cannibalised split can differ from greedy's. Fresh and cannibalised are judged against the existing stores' nearest-first walk, for every method", "No external source", "-", "Assumption"),
            ("Integer scale", f"Shares and capacity in hundredths of an order (round(orders × {SCALE})), because CP-SAT needs integers. CP-SAT's objective and bound use these rounded shares; the plan's metrics use the unrounded ones, so they can differ from the objective by rounding", "Modelling choice", "-", "Assumption"),
            ("Plan budget", f"{PLAN_BUDGET:g} s for everything before the metrics (network, reach, greedy, model, solve): the 10 s bar minus 1 s for the metrics. The solver gets what the build left of it. The build is outside the solver's time limit, so a CP-SAT model with more than {MODEL_PAIR_CAP:,} capacity-bound (x) pairs (about {MODEL_PAIR_CAP * 22e-6:.1f} s to build) is not built: from greedy, greedy's plan (its bound the cheap capacity bound); on its own, no plan", "Decision log, 2026-10-30: Full-area solve time measured (#15), the tighter model's 9 s build-plus-solve budget; 2026-11-02 for the size cap (#33)", "2026-10-30", "Assumption"),
            ("Solver", f"OR-tools CP-SAT, time limit {TIME_LIMIT} s, {WORKERS} workers, random_seed {SOLVER_SEED}", "Modelling choice", "-", "Assumption"),
        ],
        columns=["Input", "Value", "Source", "Date", "Status"],
    )
