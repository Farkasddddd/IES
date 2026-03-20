# Capacity Optimization Workspace

## Purpose

This folder is reserved for the next stage of the project:

- capacity configuration optimization
- coupling upper-level sizing decisions with lower-level dispatch logic
- comparing PV-region differences under a shared hierarchical control framework

## Relation To Other Folders

- `RL_test_fixed_config/`
  stores the earlier flat-control RL experiments
- `RL_test_hierarchical_control/`
  stores the current hierarchical dispatch version and its training/evaluation outputs
- `RL_capacity_optimization/`
  is the new workspace for capacity-search and co-optimization studies

The previous work is intentionally preserved and should not be modified unless explicitly needed.

## Current Starting Point

This folder currently contains:

- copied data files
- a copy of the hierarchical dispatch environment as a reference baseline
- a reference note explaining the hierarchical dispatch logic
- an editable economic parameter entry file at `config/economic_params.py`
- methanol market scenario definitions at `config/market_scenarios.py`
- objective/ranking logic at `metrics/capacity_objectives.py`

The next step in this folder is not immediate training.
It is to define:

- which capacities are decision variables
- which objectives matter most
- how to evaluate a candidate configuration
- whether to use nested RL, random search, Bayesian optimization, or another outer-loop optimizer

## Current Progress

This workspace now has two active stages:

- stage 1:
  broad capacity screening under a fixed hierarchical reference policy
- stage 2:
  fixed-capacity policy fine-tuning for shortlisted candidates

Stage-2 documentation and scripts are stored in:

- `docs/stage2_policy_tuning.md`
- `config/stage2_candidates.py`
- `train/finetune_stage2_candidate.py`
- `train/evaluate_stage2_candidate.py`

## Suggested Candidate Capacity Variables

Possible upper-level capacity variables include:

- PV scale
- PEM rated power
- DAC unit count
- `CO2` tank capacity
- `H2` tank capacity
- battery capacity

## Suggested Evaluation Metrics

Candidate configuration evaluation may include:

- annual methanol production
- annual grid purchase
- annual curtailment
- storage safety violations
- dispatch smoothness
- annualized capital cost
- annual operating cost
- overall profit or multi-objective score

The current recommended rule is:

- first filter by feasibility and storage safety
- then rank feasible configurations by annual profit under green methanol price scenarios

## Immediate Goal

Use this folder to design the capacity-optimization framework before writing the full search loop.
