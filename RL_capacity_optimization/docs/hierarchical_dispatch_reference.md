# Hierarchical Control Model Notes

## Purpose

This folder contains the hierarchical-control version of the integrated energy system model.
The key design idea is:

- Storage tanks are the core coupling states.
- Physical safety is enforced by a rule layer.
- Reinforcement learning only provides high-level operating preferences.

This is different from the earlier flat-control version, where RL directly controlled low-level device actions.

## Overall Control Logic

The system is organized around four layers.

### 1. Safety Layer

This layer enforces hard physical logic.

- `CO2` tank must not overflow.
- `H2` tank must not overflow.
- `CO2` tank must not be drained to zero.
- `H2` tank must not be drained to zero.
- Battery must stay within its allowed SOC band.
- DAC units must follow the fixed state machine:
  - adsorption for 2 hours
  - saturated waiting state with no time limit
  - desorption for 1 hour
  - cooling for 1 hour
  - ready waiting state with no time limit

### 2. Stability Layer

This layer encodes the operating philosophy.

- `CO2` and `H2` storage should stay in a healthy working zone.
- In the current implementation, the safe band is `20%` to `80%`.
- The RL policy is encouraged to keep tanks in a narrower target zone inside that safe band.
- Methanol production should avoid large hour-to-hour oscillations.
- Battery should also avoid staying near empty or near full for long periods.

### 3. Execution Layer

This layer converts high-level intent into actual device behavior.

- DAC provides slow `CO2` replenishment.
- PEM provides relatively fast `H2` adjustment.
- Methanol synthesis consumes `CO2` and `H2` only if storage remains above the safe floor.
- Battery absorbs short-term PV fluctuations.
- Grid is used as a fallback when on-site flexibility is not enough.

### 4. Learning Layer

RL does not directly choose device power for every unit.
Instead, RL outputs high-level operating preferences:

- desired `CO2` inventory target
- desired `H2` inventory target
- methanol production aggressiveness
- battery reserve preference

The rule layer then translates these preferences into low-level actions.

## Why This Structure Was Chosen

The original flat RL design exposed too much physical logic directly to the policy.
That caused several problems:

- DAC state dependence was hard for RL to learn cleanly.
- Tank safety depended too much on reward shaping.
- The policy could produce physically poor but numerically acceptable behaviors.
- Short-horizon training did not match long-horizon operating intuition well.

The hierarchical version addresses this by separating:

- what must always remain physically valid
- what should remain operationally healthy
- what RL is allowed to optimize

## State Variables That Matter Most

The most important dynamic states are:

- `CO2` tank inventory
- `H2` tank inventory
- battery `SOC`
- DAC phase distribution
  - ready
  - adsorption
  - saturated
  - desorption
  - cooling
- recent methanol production level
- current PV level and time position

These states are all represented in the environment observation.

## How DAC Control Works

The DAC cluster is not directly controlled by a low-level action like "turn on unit 137".
Instead, the RL policy outputs a desired `CO2` inventory target.
The rule layer then converts this target into DAC behavior:

- if current `CO2` inventory is below target, the controller increases the tendency to start desorption from saturated units
- if `CO2` inventory is not high enough, the controller also keeps feeding ready units into adsorption
- DAC state transitions remain fully constrained by the timer-based state machine

So the RL policy controls the inventory objective, while the rule layer controls the exact DAC transitions.

## How PEM Control Works

PEM is treated as a fast-response unit.
It is not forced to blindly follow DAC output.
Instead, PEM production is determined from:

- desired `H2` inventory target
- expected methanol demand
- current `H2` tank inventory

This reflects the intended operating logic:

- DAC is a slow `CO2` supply chain
- PEM is a faster balancing actuator
- `H2` should be produced according to downstream demand and inventory status, not only according to instantaneous DAC behavior

## How Methanol Synthesis Is Controlled

Methanol synthesis is not allowed to deplete storage below the safety floor.
The policy chooses a high-level pull intensity, and the rule layer converts it into actual feed:

- actual `CO2` feed is limited by current drawable `CO2`
- actual `H2` feed is limited by current drawable `H2`
- the target stoichiometric ratio is enforced through the rule layer

This means the methanol section is treated as a controlled sink that must respect storage health.

## How Battery and Grid Are Used

Battery acts as a short-term buffer.
Its role is not to perform aggressive arbitrage in the current version.

- when PV surplus exists, battery charges if it is below its preferred reserve zone
- when local generation is insufficient, battery discharges if it is above its lower safe boundary
- grid then covers the remaining deficit

This makes the battery a stabilizing unit rather than the main optimization target.

## Current RL Action Meaning

The environment action space is four-dimensional in this version:

1. `CO2` inventory target
2. `H2` inventory target
3. methanol pull intensity
4. battery reserve preference

This is the core difference from the earlier version.

## Current Design Philosophy

The model reflects the following engineering intuition:

- tanks are the system core and must remain healthy
- DAC is slow, energy-intensive, and strongly state-dependent
- PEM is flexible and should support downstream inventory balance
- methanol production should be stable, not violently oscillatory
- battery smooths short-term disturbances
- grid is a safety backup, not the default primary source

## What This Version Is Good For

This version is intended as a structured prototype for:

- annual dispatch analysis
- cross-region PV profile testing
- future capacity co-optimization studies
- comparing control philosophies without violating basic physical logic

It is not yet the final economic optimum.
Its main value is that it preserves the intended control logic much better than the flat RL setup.

## Next Likely Improvements

Reasonable next steps include:

- improving the rule that maps `CO2` target error into DAC adsorption/desorption decisions
- improving battery reserve logic
- introducing more realistic initialization for short training windows
- extending the same framework to different regional PV datasets
- coupling this dispatch layer with upper-level capacity optimization
