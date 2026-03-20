# Stage-2 Policy Tuning

## Goal

Stage 2 fixes a shortlisted capacity configuration and then fine-tunes the hierarchical dispatch policy specifically for that design.

This stage is needed because:

- stage-1 capacity screening reused a common reference policy
- a candidate can look promising under transferred control but still have room for policy-specific improvement
- safety comfort and economic performance should be rechecked after the controller adapts to the fixed design

## Workflow

1. select a small number of shortlisted capacity candidates
2. initialize from the archived hierarchical reference policy
3. continue SAC training under the fixed capacity configuration
4. run a full-year `8760 h` annual evaluation
5. compare pre-fine-tune and post-fine-tune performance

## Candidate Source

Current stage-2 candidate definitions are stored in:

- `config/stage2_candidates.py`

These candidates were selected from the archived stage-1 shortlist and include:

- medium-risk profitable candidates for primary tuning
- one high-risk, high-profit exploratory candidate for comparison

## Scripts

- `train/finetune_stage2_candidate.py`
  - fine-tune a fixed candidate from the reference model
- `train/evaluate_stage2_candidate.py`
  - run a `8760 h` annual rollout and compute economic metrics

## Archive Rule

Every fine-tuning run is stored under:

- `results/stage2_runs/<run_id>/`

Each run should contain:

- `run_metadata.json`
- `training_summary.md`
- `models/policy_finetuned.zip`
- `annual_eval_hourly.csv`
- `annual_eval_summary.json`
- `annual_eval_summary.md`
