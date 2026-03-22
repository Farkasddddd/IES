# MATLAB YALMIP System Model

Date: 2026-03-22

## What the solver output contains

Yes. The solver result includes hourly optimal control and state trajectories, not just aggregate annual indicators.

The current result structure exports these time-series fields:

- `pv_kw`
- `P_DAC`
- `P_PEM`
- `P_MeOH`
- `P_grid`
- `P_curt`
- `P_ch`
- `P_dis`
- `z_bat`
- `CO2_prod_mol_s`
- `H2_prod_mol_s`
- `F_CO2_mol_s`
- `F_H2_mol_s`
- `MeOH_kg_h`
- `z_MeOH_on`
- `CO2_storage_mol`
- `H2_storage_mol`
- `Battery_energy_kWh`
- `n_ready`
- `n_sat`
- `n_ads`
- `n_des`
- `n_cool`

So the result does include step-by-step dispatch decisions and operating states.

## Current model scope

This document reflects the current configuration used in the latest Gurobi-based runs.

### Objective

- Objective mode: `max_profit`
- Meaning: maximize horizon profit
- Profit expression:
  - methanol revenue
  - minus annualized CAPEX scaled to the solved horizon
  - minus grid electricity purchase cost
  - minus curtailment penalty

For the current full-year runs:

- horizon = `8760 h`
- horizon fraction = `1.0`
- methanol price is scanned by scenario

### Solver

- Solver: `gurobi`
- YALMIP model solved successfully on the completed cases

## Current default physical/economic settings

### Time and boundary settings

- Time step: `1 h`
- Horizon: `8760 h`
- Grid purchase: allowed
- Curtailment penalty: `0 yuan/kWh`

### DAC

- `Ndac` bounds: `10` to `500`
- Initial DAC state:
  - ready fraction = `1.0`
  - saturated fraction = `0.0`
- Adsorption duration: `2 h`
- Desorption duration: `1 h`
- Cooling duration: `1 h`
- Fan power per unit: `0.05 kW`
- Heating power per unit: `1.0 kW`
- CO2 production per desorbing unit: `0.0367/60 mol/s`

### PEM

- `C_PEM` bounds: `100` to `3000`
- Max load factor: `1.20`
- H2 production: linear in PEM power

### Battery

- `C_batE` bounds: `0` to `10000 kWh`
- `C_batP` bounds: `0` to `5000 kW`
- Initial SOC: `50%`
- SOC bounds: `10%` to `90%`
- Battery is enabled
- Charge/discharge exclusivity is enabled through `z_bat`
- Terminal cyclic battery constraint is currently off

### CO2/H2 storage

- `C_CO2` bounds: `0` to `5e7 mol`
- `C_H2` bounds: `0` to `5e7 mol`
- Initial CO2 inventory: `50% * C_CO2`
- Initial H2 inventory: `50% * C_H2`
- Storage lower bound in operation: `0`
- Terminal cyclic storage constraint is currently off

### Methanol block

- Methanol is modeled by fixed-ratio lookup + `sos2`
- Fixed H2/CO2 ratio: `3.0`
- CO2 feed lower bound: `0.01 mol/s`
- CO2 feed upper bound: `0.15 mol/s`
- Methanol block is currently always on:
  - `z_MeOH_on = 1` for all time steps

### Integer relaxation

- DAC count/state variables are currently relaxed to continuous variables
- Battery exclusivity still uses binary `z_bat`

## Constraint summary

### 1. Capacity bounds

- `Ndac`, `C_PEM`, `C_batE`, `C_batP`, `C_CO2`, `C_H2` all have explicit bounds
- Battery power is also limited by:
  - `C_batP <= max_c_rate * C_batE`

### 2. DAC state flow

For each hour:

- active adsorption units come from recent `u_ads`
- active desorption units come from recent `u_des`
- active cooling units come from previous desorption starts
- unit conservation is enforced:
  - `n_ready + n_sat + n_ads + n_des + n_cool = Ndac`
- start limits:
  - `u_ads <= n_ready`
  - `u_des <= n_sat`

DAC output equations:

- `P_DAC = p_fan * n_ads + p_heat * n_des`
- `m_CO2_prod = r_CO2 * n_des`

### 3. PEM hydrogen production

- `0 <= P_PEM <= 1.2 * C_PEM`
- `m_H2_prod = k_PEM * P_PEM`

### 4. Methanol operation and feed bounds

- Methanol block is on at all times
- CO2 feed range:
  - `0.01 <= F_CO2 <= 0.15 mol/s`
- H2 feed is fixed by ratio:
  - `F_H2 = 3.0 * F_CO2`
- Methanol production and methanol-side power are obtained by piecewise linear lookup on the surrogate data

### 5. CO2/H2 storage balances

For each hour:

- `S_CO2(t+1) = S_CO2(t) + CO2_prod - CO2_feed`
- `S_H2(t+1) = S_H2(t) + H2_prod - H2_feed`
- storage-feasible feeding is enforced:
  - feed over the hour cannot exceed current inventory plus current-hour production
- bounds:
  - `0 <= S_CO2 <= C_CO2`
  - `0 <= S_H2 <= C_H2`

### 6. Battery

For each hour:

- `0 <= P_ch <= C_batP`
- `0 <= P_dis <= C_batP`
- exclusivity:
  - `P_ch <= M * z_bat`
  - `P_dis <= M * (1 - z_bat)`
- SOC/energy balance:
  - `E_bat(t+1) = E_bat(t) + eta_ch * P_ch - P_dis / eta_dis`
- energy bounds:
  - `0.1 * C_batE <= E_bat <= 0.9 * C_batE`

### 7. Power balance

For each hour:

- `PV + Grid + Battery discharge = DAC + PEM + Methanol + Battery charge + Curtailment`

## Economic parameters currently used

Loaded from:

- `RL_capacity_optimization/config/economic_params.py`
- `RL_capacity_optimization/config/market_scenarios.py`

Current core cost parameters:

- PV CAPEX: `2700 yuan/kW`
- DAC CAPEX: `8000 yuan/unit`
- PEM CAPEX: `5000 yuan/kW`
- Battery CAPEX: `1500 yuan/kWh`
- CO2 tank CAPEX: `0.1 yuan/mol`
- H2 tank CAPEX: `8.0 yuan/mol`
- Grid electricity price: `0.65 yuan/kWh`
- Discount rate: `5%`
- Project lifetime: `20 years`

## Completed full-year scenario results

The full-year Gurobi scan currently completed these 4 price cases:

| Methanol price (yuan/kg) | Annual methanol (kg) | Annual profit (yuan) | LCOM (yuan/kg) | Annual grid (kWh) | Ndac | C_PEM | C_batE (kWh) | C_batP (kW) | C_CO2 (mol) | C_H2 (mol) |
|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| 2 | 33858.47 | -179793.14 | 7.3101 | 634.01 | 10 | 100.00 | 2.20 | 1.85 | 2326096.82 | 1685.30 |
| 3 | 61353.83 | -129352.97 | 5.1083 | 210.95 | 10 | 219.32 | 2.41 | 2.03 | 4215044.41 | 6549.41 |
| 4 | 81644.28 | -55530.79 | 4.6802 | 1439.40 | 10 | 342.66 | 6.41 | 5.50 | 5609010.23 | 17053.50 |
| 6 | 90793.52 | 119968.74 | 4.6787 | 2696.02 | 10 | 425.97 | 4.49 | 3.95 | 6237568.62 | 22709.57 |

## Interpretation of the current results

- The break-even region lies between `4` and `6 yuan/kg`
- At `6 yuan/kg`, the current formulation gives positive annual profit
- In all completed cases so far:
  - `Ndac` stays at its lower bound `10`
  - PEM capacity grows as methanol price rises
  - battery capacity is positive but small
  - CO2 tank capacity increases strongly with methanol price

## Important caution

These results reflect the current model formulation, not a final validated plant design.

Key current modeling choices that strongly affect interpretation:

- methanol block is forced on at all hours
- methanol feed ratio is fixed at `H2/CO2 = 3`
- DAC state counts are relaxed to continuous values
- storage terminal cyclic constraints are off
- initial CO2/H2 inventory is `50%` of optimized storage capacity

Because of these choices, the results are useful for current model tracking and comparison across price scenarios, but they should not yet be treated as a final physical-design conclusion.

## Result files used in this summary

- `optimization_result_20260322_201307.mat`
- `optimization_result_20260322_203308.mat`
- `optimization_result_20260322_205948.mat`
- `optimization_result_20260322_195830.mat`

## Pending item

- The `8 yuan/kg` full-year case was still incomplete when the background run was stopped, so it is not included in this table.
