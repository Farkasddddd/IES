# Stage-1 Standardization

## Goal

This stage keeps the existing hierarchical-control paradigm but upgrades it to:

- a `1 MW` Shanghai PV reference base
- ratio-based capacity configuration
- relative high-level actions
- observation vectors that include configuration state
- richer annual evaluation outputs

## New Shared Core

The standardized environment and evaluation logic now live in:

- `ies_shared/stage1_config.py`
- `ies_shared/stage1_env.py`
- `ies_shared/stage1_eval.py`

The original environment entry files remain import-compatible and now forward to the shared implementation:

- `RL_test_hierarchical_control/env/ies_bilevel_env_hierarchical.py`
- `RL_capacity_optimization/env/ies_capacity_env.py`

## Interface Modes

Two interface modes are now supported:

- `legacy`
  Keeps the previous action and observation interface so old scripts and old trained policies do not break immediately.
- `stage1`
  Uses:
  - action space in `[0, 1]^4`
  - observation with running state, time state, configuration state, and mode flags
  - extra reward breakdown and physics diagnostics in `info`

## Config Management

Project-local presets are exposed through:

- `RL_test_hierarchical_control/config/stage1_presets.py`
- `RL_test_hierarchical_control/config/baseline_stage1_shanghai.json`

The baseline Shanghai standardized config is:

- `pv_ref_kw = 1000`
- `pv_scale = 1.0`
- `r_dac = 600`
- `r_pem = 0.4`
- `r_bat_e = 2.0`
- `r_bat_p = 1.0`
- `r_h2 = 45.8`
- `r_co2 = 92.6`
- `r_meoh = 1.0`
- `mode = grid`

## New Commands

### Train a stage-1 standardized policy

```powershell
E:\anaconda\python.exe RL_test_hierarchical_control\train\train_sac_stage1_standardized.py --config-name shanghai_baseline --timesteps 60000 --episode-horizon 168
```

### Evaluate a stage-1 standardized policy for 8760 h

```powershell
E:\anaconda\python.exe RL_test_hierarchical_control\train\evaluate_stage1_standardized.py --config-name shanghai_baseline --episode-horizon 8760
```

### Run baseline + single-factor + small-grid scans

```powershell
E:\anaconda\python.exe RL_test_hierarchical_control\train\run_stage1_sensitivity.py --episode-horizon 8760
```

## Output Coverage

The new evaluation summary includes:

- performance metrics
- strategy metrics
- physics feasibility metrics
- reward breakdown

The hourly rollout export now also includes:

- `pv_abs_kw`, `pv_norm`
- target action ratios
- load ratios
- battery charge/discharge
- reward component terms
- energy and material balance residuals
- violation and limit-hit counters
