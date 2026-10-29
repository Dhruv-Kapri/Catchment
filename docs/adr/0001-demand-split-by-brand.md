# Shared-catchment demand splits equally by brand

A hex reached by several brands has its demand split equally between those brands, not between the
stores that reach it: a customer chooses an app, not a store. Within the operator, the solver assigns
each hex to one of its own stores that reaches it, within capacity, and cannibalisation is a hex
moving from an existing own store to a new one. Because the number of competitor brands reaching each
hex is fixed in a scenario, the operator's share is a constant per hex and the CP-SAT model stays
linear.

## Considered Options

- **Equal split by store:** the share depends on how many chosen stores reach a hex, which makes the
  objective nonlinear in the choices and rewards stacking own stores to "win" a hex.
- **Nearest store takes all:** simplest, but ignores that brands compete for the same customer.
