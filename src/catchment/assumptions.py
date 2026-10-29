"""Every labelled assumption the model rests on, with source, date and status. Build code reads them from here."""
# Capture-share calibration inputs
BLINKIT_ORDERS_Q2 = 398.9e6   # Blinkit orders, Q2 FY27 (Jul-Sep 2026)
Q2_DAYS = 92
BLINKIT_STORES = 2751         # at quarter end

PICK_AND_PACK = 3             # minutes, fixed
MAX_PROMISE = 20              # longest promise lever, minutes

ORDERS_PER_STORE_DAY = BLINKIT_ORDERS_Q2 / Q2_DAYS / BLINKIT_STORES
MAX_PAIR_MIN = MAX_PROMISE - PICK_AND_PACK   # free-flow minutes kept in the travel-time table
ORDERS_PER_HOUSEHOLD_DAY = 0.0
CAPACITY = 0.0
