# Archive Policy

## Goal

Every meaningful optimization attempt should leave a reproducible record.

This includes:

- what script was run
- what assumptions were used
- what objective logic was used
- what candidates were tested
- what result was selected as best

## Required Outputs Per Search Run

Each search run should create its own folder under:

`RL_capacity_optimization/results/search_runs/`

The run folder should store:

- `run_metadata.json`
- `results_raw.json`
- `results_table.csv`
- `run_summary.md`

## Metadata Contents

Metadata should include at least:

- run id
- run type
- timestamp
- reference policy name
- number of trials
- random seed
- objective basis
- methanol price scenarios

## Summary Contents

Each summary file should explain:

- how candidates were ranked
- how many candidates were feasible
- which candidate was selected as current best
- the selected configuration
- the selected configuration's `LCOM`
- the selected configuration's annual profit under the baseline green methanol scenario

## Decision Log

Important modeling choices should also be written to:

`RL_capacity_optimization/docs/decision_log.md`

This is a human-readable record of why the current code is structured the way it is.
