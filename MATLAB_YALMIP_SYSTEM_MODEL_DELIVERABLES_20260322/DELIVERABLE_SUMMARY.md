# Annual Profit Scan Deliverables

Date: 2026-03-22

## Contents

This deliverable folder contains:

- `annual_scenario_summary.csv`
  Annual result table for the completed methanol-price scenarios.
- `strategy_tables/`
  Hourly strategy tables for each completed scenario.

Completed scenario strategy files:

- `strategy_price_2_yuan_per_kg.csv`
- `strategy_price_3_yuan_per_kg.csv`
- `strategy_price_4_yuan_per_kg.csv`
- `strategy_price_6_yuan_per_kg.csv`

## Does the result include step-by-step control strategy?

Yes.

Each strategy table contains hourly operational decisions and states, including:

- PV power
- DAC power
- PEM power
- Methanol-side power
- Grid purchase
- Curtailment
- Battery charge power
- Battery discharge power
- Battery mode
- CO2 production
- H2 production
- Methanol feed CO2
- Methanol feed H2
- Methanol production
- CO2 tank inventory
- H2 tank inventory
- Battery energy state
- DAC state occupancy

## Current model and constraint summary

The current runs in this deliverable reflect the following model formulation.

### Objective

- Objective: maximize profit over the solved horizon
- Profit = methanol revenue - annualized CAPEX - grid electricity cost - curtailment penalty
- In the current runs:
  - grid purchase is allowed
  - grid purchase is charged
  - curtailment penalty is set to `0`

### Main decision variables

Capacity variables:

- `Ndac`
- `C_PEM`
- `C_batE`
- `C_batP`
- `C_CO2`
- `C_H2`

Hourly operating variables:

- DAC state counts and state transitions
- `P_DAC`
- `P_PEM`
- `F_CO2`
- `F_H2`
- `P_MeOH`
- `M`
- `P_ch`
- `P_dis`
- `z_bat`
- `S_CO2`
- `S_H2`
- `E_bat`
- `P_grid`
- `P_curt`

### DAC constraints

- DAC starts from all units in ready state
- Fixed-cycle occupancy is used:
  - adsorption = `2 h`
  - desorption = `1 h`
  - cooling = `1 h`
- DAC power and CO2 production are tied to the number of active adsorbing/desorbing units

### PEM constraints

- PEM hydrogen production is linear in `P_PEM`
- PEM power is bounded by installed PEM capacity and max load factor

### Methanol constraints

- Methanol block is forced on in all hours in the current runs
- CO2 feed range is constrained to:
  - `0.01 <= F_CO2 <= 0.15 mol/s`
- H2 feed ratio is fixed:
  - `F_H2 = 3 * F_CO2`
- Methanol output and methanol-side power are generated from the surrogate lookup

### Storage constraints

- CO2 and H2 tank initial inventories are both set to `50%` of their optimized capacities
- Storage balances are enforced hourly
- Storage upper bounds are the optimized storage capacities
- Terminal cyclic tank constraints are currently off

### Battery constraints

- Battery initial SOC is `50%`
- SOC operating range is `10%` to `90%`
- Battery charge and discharge are mutually exclusive through `z_bat`
- Battery capacity cost is included in the economic objective
- Battery power and state are exported in the hourly strategy tables

### Power balance

Hourly electric balance is enforced:

- `PV + Grid + Battery discharge = DAC + PEM + Methanol + Battery charge + Curtailment`

## Economic parameters

Economic inputs are read from the existing repository configuration:

- `RL_capacity_optimization/config/economic_params.py`
- `RL_capacity_optimization/config/market_scenarios.py`

Core values used:

- PV CAPEX = `2700 yuan/kW`
- DAC CAPEX = `8000 yuan/unit`
- PEM CAPEX = `5000 yuan/kW`
- Battery CAPEX = `1500 yuan/kWh`
- CO2 tank CAPEX = `0.1 yuan/mol`
- H2 tank CAPEX = `8.0 yuan/mol`
- Grid electricity price = `0.65 yuan/kWh`
- Discount rate = `5%`
- Project lifetime = `20 years`

## Completed annual scenario results

| Methanol price (yuan/kg) | Annual methanol (kg) | Annual profit (yuan) | LCOM (yuan/kg) | Annual grid (kWh) | Ndac | C_PEM | C_batE (kWh) | C_batP (kW) | C_CO2 (mol) | C_H2 (mol) |
|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| 2 | 33858.47 | -179793.14 | 7.3101 | 634.01 | 10 | 100.00 | 2.20 | 1.85 | 2326096.82 | 1685.30 |
| 3 | 61353.83 | -129352.97 | 5.1083 | 210.95 | 10 | 219.32 | 2.41 | 2.03 | 4215044.41 | 6549.41 |
| 4 | 81644.28 | -55530.79 | 4.6802 | 1439.40 | 10 | 342.66 | 6.41 | 5.50 | 5609010.23 | 17053.50 |
| 6 | 90793.52 | 119968.74 | 4.6787 | 2696.02 | 10 | 425.97 | 4.49 | 3.95 | 6237568.62 | 22709.57 |

## Interpretation

- The break-even region is between `4` and `6 yuan/kg`
- In the currently completed cases, `6 yuan/kg` is profitable while `4 yuan/kg` is still negative
- PEM and CO2 storage capacities increase with methanol price
- Battery remains active in the optimized solutions, although the optimized size is small in the currently completed cases

## Note

- The `8 yuan/kg` annual scenario was not completed before the background run was stopped, so it is not included here.
