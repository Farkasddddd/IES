# New Machine Setup

## Recommended Python

- current verified interpreter on the source machine: `Python 3.13.9`
- recommended setup on a new machine: create a fresh conda or venv environment first, then install from `requirements.txt`

## What To Copy

Copy the whole project folder, not just one subfolder:

- `RL_test_fixed_config/`
- `RL_test_hierarchical_control/`
- `RL_capacity_optimization/`
- `requirements.txt`
- `PROJECT_VERSION_INDEX.md`
- `SETUP_NEW_MACHINE.md`

This keeps:

- all source code
- all trained models
- all archived search runs
- all annual evaluation results

## Suggested Steps

### Option A: Conda

```powershell
conda create -n ies python=3.13 -y
conda activate ies
python -m pip install --upgrade pip
pip install -r requirements.txt
```

### Option B: venv

```powershell
python -m venv .venv
.venv\Scripts\Activate.ps1
python -m pip install --upgrade pip
pip install -r requirements.txt
```

## Quick Verification

After installation, run one of these checks from the project root:

```powershell
python -m py_compile RL_test_hierarchical_control\train\train_sac_hierarchical.py
python -m py_compile RL_capacity_optimization\train\finetune_stage2_candidate.py
```

## Common Run Commands

### Hierarchical dispatch training

```powershell
python RL_test_hierarchical_control\train\train_sac_hierarchical.py
```

### Capacity stage-1 search

```powershell
python RL_capacity_optimization\train\search_capacity_random.py --n-trials 60 --seed 20260319
python RL_capacity_optimization\train\search_capacity_local.py --n-trials 60 --seed 20260319 --radius 1
```

### Capacity stage-2 fine-tuning

```powershell
python RL_capacity_optimization\train\finetune_stage2_candidate.py --candidate-id m1_profit_medium --timesteps 60000 --seed 20260319 --episode-horizon 168
python RL_capacity_optimization\train\evaluate_stage2_candidate.py --candidate-id m1_profit_medium
```

### Stage-2 batch run

```powershell
python RL_capacity_optimization\train\run_stage2_batch.py --timesteps 60000 --seed 20260319 --episode-horizon 168 --skip-completed
```

## Important Notes

- all project scripts already use relative project paths, so you do not need to keep the exact same absolute path as the old machine
- the `data/` folders and `results/` folders must be copied together with the code
- if you want to continue from existing trained policies, make sure the corresponding `.zip` model files are copied too
- if a new machine uses a different Python major version and package compatibility becomes a problem, prefer matching `Python 3.13.x` first
