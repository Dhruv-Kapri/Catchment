"""Every labelled assumption the model rests on, with source, date and status. Build code reads them from here."""
PICK_AND_PACK = 3             # minutes, fixed
MAX_PROMISE = 20              # longest promise lever, minutes

MAX_PAIR_MIN = MAX_PROMISE - PICK_AND_PACK   # free-flow minutes kept in the travel-time table
ORDERS_PER_HOUSEHOLD_DAY = 0.0
ORDERS_PER_STORE_DAY = 0.0
CAPACITY = 0.0
