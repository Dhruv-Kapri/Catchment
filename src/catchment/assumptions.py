"""Every labelled assumption the model rests on, with source, date and status. Build code reads them from here."""
import pandas as pd

HOUSEHOLD_SIZE = 4.5          # persons per household, one value for every hex
M_LOW, M_HIGH = 0.5, 1.5      # affluence multiplier bounds

# Capture-share calibration inputs
BLINKIT_ORDERS_Q2 = 398.9e6   # Blinkit orders, Q2 FY27 (Jul-Sep 2026)
Q2_DAYS = 92
BLINKIT_STORES = 2751         # at quarter end
NCR_STORES = 400              # dark stores, all brands, NCR
NCR_POPULATION = 30.2e6       # "New Delhi" Degree of Urbanisation city, WUP 2025, 2025 estimate

PICK_AND_PACK = 3             # minutes, fixed
MAX_PROMISE = 20              # longest promise lever, minutes

# Plan (02-plan): default scenario, capacity, placeholder network, solver
PROMISE, MULTIPLIER = 10, 1.4           # default scenario
N_SLICE, N_AREA = 3, 10                 # new stores: the slice, the full area (default scenario)
CAPACITY_FACTOR = 1.5
BRAND_COUNTS = {"Operator": 3, "Competitor A": 4, "Competitor B": 3}   # placeholder, the slice
SEED = 2026                             # network placement
SCALE = 100                             # shares and capacity are integers in hundredths of an order
TIME_LIMIT, WORKERS, SOLVER_SEED = 60, 8, 1

ORDERS_PER_STORE_DAY = BLINKIT_ORDERS_Q2 / Q2_DAYS / BLINKIT_STORES
NCR_HOUSEHOLDS = NCR_POPULATION / HOUSEHOLD_SIZE
# calibration target: all-brand orders per household per day
ORDERS_PER_HOUSEHOLD_DAY = NCR_STORES * ORDERS_PER_STORE_DAY / NCR_HOUSEHOLDS
SECOND_ROAD_MAX_M = 100   # a point's second road counts for snapping only within this distance
SECOND_ROAD_GAP_M = 5     # and only if it lies more than this across the first road (a parallel carriageway, not its next segment)
MAX_PAIR_MIN = MAX_PROMISE - PICK_AND_PACK   # free-flow minutes kept in the travel-time table
CAPACITY = CAPACITY_FACTOR * ORDERS_PER_STORE_DAY   # orders per store per day


def table():
    """The assumptions as a table: Input, Value, Source, Date, Status."""
    return pd.DataFrame(
        [
            ("Household size", f"{HOUSEHOLD_SIZE} persons", "NFHS-5 (2019-21) Haryana state report, IIPS/MoHFW, Table 4 (urban mean household size). https://dhsprogram.com/pubs/pdf/FR374/FR374_Haryana.pdf", "2026-10-29", "Verified"),
            ("Multiplier bounds", f"{M_LOW} to {M_HIGH}", "No external source; a labelled assumption (decision log, 2026-10-29)", "-", "Assumption"),
            ("Blinkit orders, Q2 FY27", f"{BLINKIT_ORDERS_Q2/1e6:.1f} M over {Q2_DAYS} days", "Eternal Ltd shareholders' letter, 21 Oct 2026 (BSE filing), https://www.bseindia.com/xml-data/corpfiling/AttachLive/cbfbd146-6a68-43d6-9cbc-dfb7d0f50fd0.pdf, p. 13, Quick commerce operating metrics, row Orders (398.9 million). The 92 days are ours; the letter does not state them", "2026-10-29", "Verified"),
            ("Blinkit stores", f"{BLINKIT_STORES:,} at quarter end", "Eternal Ltd shareholders' letter, 21 Oct 2026 (BSE filing), https://www.bseindia.com/xml-data/corpfiling/AttachLive/cbfbd146-6a68-43d6-9cbc-dfb7d0f50fd0.pdf, p. 13, Quick commerce operating metrics, row Stores at the end of the period (#); also p. 6", "2026-10-29", "Verified"),
            ("NCR dark stores (all brands)", f"~{NCR_STORES}", "Savills India Research, Q-Commerce Growth: Dark Stores Shaping the Future of Retail, Dec 2025, https://pdf.savills.asia/asia-pacific-research/india-research/q-commerce-growth---dark-stores-shaping-the-future-of-retail.pdf, p. 8, Delhi-NCR 400. Best-effort estimate as of Oct 2025; not broken down by brand (all brands is our reading)", "2026-10-29", "Verified"),
            ("NCR population", f"{NCR_POPULATION/1e6:.1f} M", "UN DESA World Urbanization Prospects: The 2025 Revision, File 21 (WUP2025-F21-DEGURBA-Cities_Pop.xlsx, POP/DB/WUP/Rev.2025/F21), India, City_Code 8364 \"New Delhi\", 2025 column: 30,222.405 thousand. https://population.un.org/wup/assets/Download/Cities/WUP2025-F21-DEGURBA-Cities_Pop.xlsx. A Degree of Urbanisation city (contiguous 1 km2 cells of at least 1,500 people per km2), not an agglomeration; Gurgaon, Faridabad, Ghaziabad and Noida have no separate entry, so they fall inside it (inference). See decision log, 2026-10-29", "2026-10-29", "Verified"),
            ("Pick-and-pack allowance", f"{PICK_AND_PACK} min, fixed", "Decision log, 2026-10-29 (Explore)", "2026-10-29", "Assumption"),
            ("Pairs kept in the table", f"Free-flow ≤ {MAX_PAIR_MIN} min (longest promise {MAX_PROMISE} − {PICK_AND_PACK} at multiplier 1.0)", "Decision log, 2026-10-29 (Explore)", "2026-10-29", "Assumption"),
            ("Second road for snapping", f"Each point snaps to its nearest road and a second road, and a pair keeps the fastest of the four times. The second road is the nearest hit within {SECOND_ROAD_MAX_M} m that lies more than {SECOND_ROAD_GAP_M} m from the first across the road (a parallel carriageway, not the next segment of the same one); none, then the nearest road repeats", "No external source; 01-reach found about one short pair in seven running out and back at an endpoint (issue #14)", "-", "Assumption"),
            ("Default scenario", f"Promise {PROMISE} min, congestion multiplier {MULTIPLIER}, pick-and-pack {PICK_AND_PACK} min: a hex is reachable if free-flow min × {MULTIPLIER} + {PICK_AND_PACK} ≤ {PROMISE}, that is free-flow ≤ {(PROMISE - PICK_AND_PACK) / MULTIPLIER:.1f} min", "Decision log, 2026-10-29 (Explore)", "2026-10-29", "Assumption"),
            ("New stores, N", f"{N_SLICE} on the slice; {N_AREA} on the full area (the default scenario for the 10 s bar)", "Decision log, 2026-10-29 (Explore)", "2026-10-29", "Assumption"),
            ("Orders per store per day", f"{BLINKIT_ORDERS_Q2/1e6:.1f} M orders ÷ {Q2_DAYS} days ÷ {BLINKIT_STORES:,} stores = {ORDERS_PER_STORE_DAY:,.0f}", "00-demand: Eternal Ltd shareholders' letter, 21 Oct 2026, p. 13 (orders and stores)", "2026-10-29", "Verified"),
            ("Capacity per store", f"{CAPACITY_FACTOR} × {ORDERS_PER_STORE_DAY:,.0f} = {CAPACITY:,.0f} orders per day, the same for every store of the operator. Adopted here as 00-demand and the decision log said; the 1.5 has no source (headroom over the average)", "Decision log, 2026-10-29 (Explore); issue #5. Rests on the Verified orders per store per day", "2026-10-29", "Assumption"),
            ("Brands and store counts", f"{', '.join(f'{b} {n}' for b, n in BRAND_COUNTS.items())}: {sum(BRAND_COUNTS.values())} stores in the slice. PLACEHOLDER counts, not reported figures", "Slice demand ÷ orders per store per day = 10.5 stores' worth (00-demand), rounded to 10 and split with no market-share source. The generator with sourced counts is stage 2", "2026-10-29", "Assumption"),
            ("Store placement", f"Sampled without replacement from the slice's candidate sites, probability ∝ the demand the site reaches at the default scenario; seed {SEED}; at most one store per site, whatever the brand", "No external source", "-", "Assumption"),
            ("Competitor reach", "A competitor store at a site reaches the same hexes as an operator store there (same promise, multiplier and travel times)", "No external source", "-", "Assumption"),
            ("Demand split", "A hex reached by the operator and k competitor brands gives the operator demand ÷ (1 + k); k is fixed in a scenario", "ADR 0001", "2026-10-29", "Assumption"),
            ("Sites for new stores", "Any slice candidate site with no store on it, of any brand", "No external source", "-", "Assumption"),
            ("Assignment tie-break", "Among assignments that serve the same orders, the one with the shortest total travel time (decides new against cannibalised demand)", "No external source", "-", "Assumption"),
            ("Integer scale", f"Shares and capacity in hundredths of an order (round(orders × {SCALE})), because CP-SAT needs integers. Every metric is computed from these rounded shares", "Modelling choice", "-", "Assumption"),
            ("Solver", f"OR-tools CP-SAT, time limit {TIME_LIMIT} s, {WORKERS} workers, random_seed {SOLVER_SEED}", "Modelling choice", "-", "Assumption"),
        ],
        columns=["Input", "Value", "Source", "Date", "Status"],
    )
