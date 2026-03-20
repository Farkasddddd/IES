# Capacity Combination Ranking Logic

## Recommended Evaluation Order

Each capacity combination should be judged in two stages.

### Stage 1: Feasibility screening

Reject any configuration that violates core operating constraints.

Current recommended hard constraints:

- `CO2` overflow total must be `0`
- `H2` overflow total must be `0`
- `CO2` tank ratio must stay within `20% ~ 80%`
- `H2` tank ratio must stay within `20% ~ 80%`
- battery `SOC` must stay within `20% ~ 80%`

Only feasible configurations should be compared economically.

## Safety and Transferability Indicators

Even among feasible configurations, we also record:

- `safety_margin`
  - the minimum remaining distance to the tighter `25% ~ 75%` operational comfort band
  - larger is better
- `hard_safety_margin`
  - the minimum remaining distance to the hard `20% ~ 80%` feasibility band
  - larger is better
- `transfer_distance`
  - a normalized distance from the hierarchical reference configuration
  - smaller is better
- `transfer_risk`
  - qualitative label: `low`, `medium`, or `high`

These are not yet used as hard rejection rules beyond feasibility, but they are part of the archive and should be checked before promoting a candidate to stage-2 re-training.

## Local Search Policy

After a broad random-search stage, the next recommended step is:

- select archived profitable candidates as anchors
- build a local neighborhood over adjacent discrete design choices
- rerun annual dispatch evaluation in that neighborhood

This keeps the search cost manageable while improving:

- candidate profitability
- safety robustness inside the comfort band
- transferability relative to the fixed hierarchical policy

### Stage 2: Economic ranking

For each feasible configuration, compute:

- annualized CAPEX
- annual grid electricity cost
- `LCOM`
- annual profit under multiple methanol price scenarios

## LCOM Definition

Current simplified form:

`LCOM = (Annualized CAPEX + Annual Grid Cost) / Annual Methanol Production`

This is intentionally a simplified first-stage indicator because the current model does not yet include:

- fixed O&M
- water cost
- catalyst replacement
- labor
- other non-electric variable costs

## Profit Definition

For each methanol price scenario:

`Annual Profit = Price * Annual Methanol Production - Annualized CAPEX - Annual Grid Cost`

This is equivalent to:

`Annual Profit = (Price - LCOM) * Annual Methanol Production`

when `LCOM` is defined using the same annualized costs.

## Recommended Paper Scenarios

Based on the current market background:

- conservative green methanol case: `4 yuan / kg`
- baseline green methanol case: `6 yuan / kg`
- aggressive green methanol case: `8 yuan / kg`

These are implemented in:

`RL_capacity_optimization/config/market_scenarios.py`

## Current Code Entry Point

The current objective logic is implemented in:

`RL_capacity_optimization/metrics/capacity_objectives.py`

Key functions:

- `is_feasible(...)`
- `estimate_lcom(...)`
- `evaluate_scenarios(...)`
- `evaluate_capacity_combination(...)`
