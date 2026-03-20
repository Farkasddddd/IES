# Decision Log

## 2026-03-19

### Capacity optimization outer loop

Decision:

- do not retrain RL for every capacity combination in the first stage
- use the hierarchical dispatch policy from `RL_test_hierarchical_control` as a fixed lower-level controller

Reason:

- retraining RL for each candidate would make the outer-loop search too expensive
- first-stage screening only needs a consistent dispatch baseline to compare relative capacity quality

### Capacity combination evaluation rule

Decision:

- first filter by feasibility
- then rank feasible candidates by annual profit under the baseline green methanol price scenario

Current hard feasibility rules:

- `CO2` overflow must be zero
- `H2` overflow must be zero
- `CO2` tank ratio must stay within `20% ~ 80%`
- `H2` tank ratio must stay within `20% ~ 80%`
- battery `SOC` must stay within `20% ~ 80%`

Current baseline economic ranking:

- green methanol price = `6 yuan / kg`

Supporting price scenarios also retained:

- `4 yuan / kg`
- `8 yuan / kg`

### Transferability and safety

Decision:

- every candidate should also report a safety margin and a transfer-distance metric
- capacity combinations far from the hierarchical reference design should be treated more cautiously in stage-1 screening

Reason:

- the lower-level policy was trained around a reference dispatch configuration
- a capacity combination can look economically attractive while still being less trustworthy as a fixed-policy transfer case
- keeping explicit transfer and safety indicators makes later stage-2 fine-tuning decisions easier

### Economic assumptions

Decision:

- use the economic parameter table confirmed by the user
- store all editable economic inputs in `config/economic_params.py`

Reason:

- future sensitivity analysis will require quick parameter changes
- keeping a single editable source avoids inconsistencies between scripts

### Local screening after random search

Decision:

- after the first random-search stage, run a local search around archived profitable candidates
- use a tighter operational comfort band (`25% ~ 75%`) as the main safety-margin metric
- keep the original `20% ~ 80%` hard band as a separate feasibility margin

Reason:

- hard feasibility alone is not enough to distinguish candidates that run too close to the boundary
- local search near profitable anchors is cheaper than restarting from a broad global search every time
- this preserves consistency with the fixed-policy transfer assumption while improving shortlist quality

### Stage-2 fine-tuning

Decision:

- after stage-1 screening, keep only a few shortlisted capacity combinations for dedicated policy tuning
- initialize stage-2 tuning from the archived hierarchical reference policy instead of training from scratch
- archive every fixed-capacity tuning run and its `8760 h` annual re-evaluation together

Reason:

- stage-1 profitability under a transferred policy is only a first-pass filter
- stage-2 should answer whether a candidate remains attractive after the controller adapts to that specific design
- warm-start fine-tuning is much cheaper than full retraining for every stage-1 candidate
