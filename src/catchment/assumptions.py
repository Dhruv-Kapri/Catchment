"""Every labelled assumption the model rests on, with source, date and status. Build code reads them from here."""
import pandas as pd

HOUSEHOLD_SIZE = 4.5          # persons per household, one value for every hex

# Capture-share calibration inputs
BLINKIT_ORDERS_Q2 = 398.9e6   # Blinkit orders, Q2 FY27 (Jul-Sep 2026)
Q2_DAYS = 92
BLINKIT_STORES = 2751         # at quarter end
NCR_STORES = 400              # dark stores, all brands, NCR
NCR_POPULATION = 34.7e6       # Delhi urban agglomeration, 2025 projection

PICK_AND_PACK = 3             # minutes, fixed
MAX_PROMISE = 20              # longest promise lever, minutes

CAPACITY_FACTOR = 1.5

ORDERS_PER_STORE_DAY = BLINKIT_ORDERS_Q2 / Q2_DAYS / BLINKIT_STORES
NCR_HOUSEHOLDS = NCR_POPULATION / HOUSEHOLD_SIZE
# calibration target: all-brand orders per household per day
ORDERS_PER_HOUSEHOLD_DAY = NCR_STORES * ORDERS_PER_STORE_DAY / NCR_HOUSEHOLDS
MAX_PAIR_MIN = MAX_PROMISE - PICK_AND_PACK   # free-flow minutes kept in the travel-time table
CAPACITY = CAPACITY_FACTOR * ORDERS_PER_STORE_DAY   # orders per store per day


def table():
    """The assumptions as a table: Input, Value, Source, Date, Status."""
    return pd.DataFrame([], columns=["Input", "Value", "Source", "Date", "Status"])
