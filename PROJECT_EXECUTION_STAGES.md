# Project Execution Stages

This project follows a staged workflow. The goal is not to jump directly to a global capacity optimum, but to build a reliable control and analysis pipeline step by step.

## Stage 1: Stable, Trustworthy Baseline Policy at the Shanghai Baseline Capacity

Goal:
- verify the environment structure is physically self-consistent
- verify the high-level action design is meaningful
- verify the rule layer translates policy intent into reasonable device behavior
- verify reward design can drive interpretable behavior
- verify annual metrics are complete and trustworthy

Inputs:
- Shanghai PV profile
- baseline capacity configuration
- standardized stage1 environment interface

Deliverables:
- baseline policy `pi_base` under the Shanghai baseline capacity
- standardized environment interface with parameterized config, relative actions, and complete outputs

Practical meaning:
- this stage establishes the formal baseline used by later comparison work
- later capacity studies should not bypass this baseline

## Stage 2: Change Capacity Parameters and Fine-Tune from the Baseline Policy

Goal:
- reuse the baseline policy as a good initialization under nearby capacity settings
- avoid unnecessary retraining from scratch for every new configuration

Method:
- start from the baseline policy
- modify one or more capacity ratios
- continue training under the new configuration
- archive both the new configuration and the fine-tuned policy

Expected outputs:
- one policy per studied capacity configuration
- training metadata linking each policy back to its initialization source

Practical meaning:
- this stage is used to study how policy behavior shifts when capacity changes
- it is not yet the final scientific output by itself

## Stage 3: Build the Capacity -> Policy -> Performance Mapping

Goal:
- extract general patterns instead of only collecting many separate policies

Core question:
- how does capacity configuration change policy characteristics
- how do policy characteristics change annual performance

Typical outputs:
- trends in inventory targets, methanol pull behavior, and battery preference
- trends in production, cost, curtailment, and constraint behavior
- interpretable regime changes such as hydrogen-limited vs carbon-limited operation

Practical meaning:
- this stage is the core analysis layer for paper writing
- the key result is the mapping, not a single best model checkpoint

## Stage 4: Train a Capacity-Conditioned Unified Agent

Goal:
- train one policy that responds to configuration context within a predefined capacity range

Careful wording:
- not a policy that works for every possible capacity
- a policy that can adapt within the capacity distribution covered during training

Requirements:
- stage1 interface must already include configuration state
- stage2 and stage3 must already define the capacity ranges and policy-response patterns worth learning

Practical meaning:
- this stage turns the staged research results into a generalized control model

## Current Execution Rule

Until the new GPU line fully meets the replacement standard, keep two tracks in parallel:

- stable line: responsible for formal scans and pattern extraction
- improved GPU line: responsible for safety convergence fixes and later fine-tuning capability

The improved GPU line can replace the old stable baseline only when it satisfies all of the following:

- annual constraint violations equal zero
- annual methanol output is not meaningfully worse than the old stable line
- LCOM is not meaningfully worse than the old stable line
- training efficiency is higher
- engineering workflow is cleaner and easier to extend
