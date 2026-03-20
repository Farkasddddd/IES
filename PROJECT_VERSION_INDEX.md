# Project Version Index

## Purpose

This file summarizes the major experiment folders in the workspace so later work can stay organized.

## 1. `RL_test_fixed_config`

Path:

`C:\Users\27878\Desktop\IES\RL_test_fixed_config`

Role:

- earlier fixed-configuration RL experiments
- flat or semi-flat control structure
- used to debug PV parsing, model loading, DAC state transitions, and annual evaluation flow

Key artifacts:

- environment:
  `RL_test_fixed_config/env/ies_bilevel_env_fixed.py`
- training:
  `RL_test_fixed_config/train/train_sac_fixed.py`
- annual evaluation:
  `RL_test_fixed_config/train/evaluate_policy_8760.py`

Representative result:

- `sac_fixed_config_v3.zip`
- annual evaluation showed the policy could run for 8760 hours, but `CO2` inventory stayed too close to the lower boundary and `H2` overflow still appeared

Interpretation:

- useful as a debugging and transition version
- not ideal as the final dispatch structure

## 2. `RL_test_hierarchical_control`

Path:

`C:\Users\27878\Desktop\IES\RL_test_hierarchical_control`

Role:

- current structured dispatch version
- rule layer enforces physical safety
- RL only optimizes high-level operating preferences

Key artifacts:

- environment:
  `RL_test_hierarchical_control/env/ies_bilevel_env_hierarchical.py`
- training:
  `RL_test_hierarchical_control/train/train_sac_hierarchical.py`
- annual evaluation:
  `RL_test_hierarchical_control/train/evaluate_policy_8760.py`
- annual plots:
  `RL_test_hierarchical_control/results/figures/`
- explanatory note:
  `RL_test_hierarchical_control/README_hierarchical_model.md`

Representative result:

- `sac_hierarchical_v1.zip`
- annual methanol production about `147,427 kg`
- no `CO2` overflow
- no `H2` overflow
- `CO2` and `H2` tank ratios remained inside `20% ~ 80%`

Interpretation:

- this is the current dispatch baseline
- safer and more interpretable than the fixed flat-control version
- suitable as the reference policy for capacity optimization stage

## 3. `RL_capacity_optimization`

Path:

`C:\Users\27878\Desktop\IES\RL_capacity_optimization`

Role:

- upper-level capacity configuration optimization workspace
- uses the hierarchical dispatch policy as a fixed lower-level controller in the first stage
- intended for configuration ranking, screening, and later co-optimization

Key artifacts:

- copied reference environment:
  `RL_capacity_optimization/env/ies_capacity_env.py`
- editable economics:
  `RL_capacity_optimization/config/economic_params.py`
- methanol market scenarios:
  `RL_capacity_optimization/config/market_scenarios.py`
- capacity ranking logic:
  `RL_capacity_optimization/metrics/capacity_objectives.py`
- hierarchical dispatch reference note:
  `RL_capacity_optimization/docs/hierarchical_dispatch_reference.md`
- reference policy copy:
  `RL_capacity_optimization/results/models/sac_hierarchical_reference.zip`

Current objective:

- screen capacity combinations using a fixed dispatch policy
- reject infeasible combinations first
- rank feasible combinations by annual economics under methanol price scenarios

## Recommended Usage

- keep `RL_test_hierarchical_control` as the dispatch benchmark folder
- do not overwrite old results when testing new capacity-search logic
- keep all upper-level sizing scripts and outputs inside `RL_capacity_optimization`
