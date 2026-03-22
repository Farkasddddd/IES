# MATLAB YALMIP System Model

This folder is a new standalone direction for the integrated energy system model using MATLAB + YALMIP.

It reuses existing project assets from this repository:

- PV profile: `data/pvwatts_hourly_shanghai.csv`
- Methanol data source: `data/Methanol_IES_AutoSave_Updated.xlsx`
- Economic parameters: `RL_capacity_optimization/config/economic_params.py`

## Scope

The current implementation provides:

- capacity decision variables for DAC, PEM, battery, CO2 tank, and H2 tank
- hourly operational variables for DAC state flow, PEM dispatch, methanol feed, storage, battery, grid, and curtailment
- fixed-cycle DAC occupancy model based on integer start variables
- linear PEM hydrogen production baseline
- methanol surrogate integration through a fixed-ratio lookup plus YALMIP `interp1(...,'sos2')`
- default single-objective methanol maximization, with alternative objective modes
- minimum methanol feed constraint for continuous operation
- default PV-only operation with no grid purchase
- cyclic battery and tank constraints to avoid free initial energy/material
- economic objective support using repository CAPEX/OPEX assumptions and methanol price scenarios

## Important modeling choices

To keep the optimization tractable in YALMIP, two choices are applied in this first version:

1. PEM is modeled with a linear hydrogen yield per kW.
2. Methanol surrogate is reduced to a 1D lookup by fixing the H2/CO2 ratio to a chosen value and fitting a piecewise-linear curve from the Excel dataset.
3. Continuous methanol operation is enforced by a minimum CO2 feed constraint. The default minimum CO2 feed is set to `0.01 mol/s`.

This matches the modeling strategy you described: preserve the surrogate interface while using a solver-friendly approximation first.

## Folder structure

- `run_system_optimization.m`
  Main entry point.
- `run_balance_diagnostic_case.m`
  Runs a positive-production reference case and checks material and energy balances.
- `run_economic_scenario_scan.m`
  Solves the model across repository methanol-price scenarios and reports profit/LCOM.
- `config/default_model_params.m`
  Default paths, capacities, solver, and objective settings.
- `core/`
  Constraint builders and objective builder.
- `diagnostics/`
  Balance checking utilities for CO2, H2, battery, and electric power.
- `io/`
  Data loading, economic parameter parsing, and result export.
- `surrogate/`
  Methanol lookup construction and YALMIP surrogate constraints.
- `results/`
  Export target for optimization outputs.

## How to run

In MATLAB:

```matlab
cd('C:\Users\Farkas\Desktop\IES\MATLAB_YALMIP_SYSTEM_MODEL');
setup_matlab_paths;
results = run_system_optimization();
```

## Solver setup

- YALMIP is required.
- Gurobi is optional for the first version.
- The default solver is now MATLAB `intlinprog`, which is easier to use for the first MILP version once YALMIP is installed.
- `setup_matlab_paths` now also auto-detects the default Windows Gurobi install at `C:\gurobi1301\win64`.
- If Gurobi is installed but not licensed yet, MATLAB/YALMIP should still run with `intlinprog`.

## Notes

- This code assumes YALMIP is installed.
- The code was created in this repository but was not executed here, because MATLAB/YALMIP is not available in the current terminal environment.
- If you want the methanol section upgraded later from fixed-ratio lookup to 2D ratio-flow approximation or explicit neural-network reformulation, the existing `surrogate/` interface is the place to extend.
- Economic inputs are read from:
  - `RL_capacity_optimization/config/economic_params.py`
  - `RL_capacity_optimization/config/market_scenarios.py`
