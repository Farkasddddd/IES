# Stage 2 Acceleration Workflow

The current fine-tune loop can produce a capacity-policy-performance mapping, but it becomes slow if every candidate receives the same training budget.

Use a three-phase workflow instead:

## Phase 1: Screen

Purpose:
- quickly eliminate weak directions

Recommended setting:
- warm-start fine-tune for 2000 timesteps
- full-year evaluation for ranking

Interpretation:
- not for final claims
- good for deciding which local directions deserve more compute

## Phase 2: Promote

Purpose:
- confirm whether screen winners remain strong after more adaptation

Recommended setting:
- warm-start fine-tune for 10000 timesteps
- full-year evaluation for updated ranking

Interpretation:
- suitable for early mapping conclusions
- good for local interaction studies

## Phase 3: Final

Purpose:
- generate final candidate policies and archival evidence

Recommended setting:
- warm-start fine-tune for 60000 timesteps
- full-year evaluation

Interpretation:
- use this phase only for shortlisted candidates

## Practical Rule

Do not push every capacity point directly to long training.

Instead:
- screen many points cheaply
- promote only the best few
- finalize only the best candidates

## Batch Runner

Use:
- `C:\Users\Farkas\Desktop\IES\RL_test_hierarchical_control\train\run_stage2_finetune_batch.py`

This runner:
- reads a directory of config json files
- warm-starts from a given baseline model
- trains and evaluates each config
- incrementally saves a batch manifest and summary table
