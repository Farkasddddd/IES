# Stage 2 Round 1 Single-Factor Fine-Tune Configs

These configs are used for stage 2 warm-start fine-tuning experiments.

Base initialization policy:
- guarded GPU baseline trained at the Shanghai baseline capacity
- source model path is recorded in the stage manifest for each run

Round 1 purpose:
- validate that the warm-start fine-tune pipeline works end-to-end
- collect the first policy-shift evidence under single-factor capacity changes
- keep one changed factor per config while all other capacity ratios remain at the baseline values
