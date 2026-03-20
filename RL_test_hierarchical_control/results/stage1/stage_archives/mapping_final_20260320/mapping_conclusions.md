# Mapping Conclusions

## Final Best Candidates
- best zero-violation LCOM candidate: final_r_h2_55 (7.6509 yuan/kg, 147980.54 kg)
- best zero-violation methanol candidate: promote_r_bat_e_35 (149919.41 kg, 8.8830 yuan/kg)

## Main Mapping Findings
- H2 storage is the strongest and most robust lever in the explored local region. Increasing r_h2 from 45.8 to around 55 consistently improved both annual methanol output and LCOM, and the improvement survived screen, promote, and final phases.
- Battery energy expansion improves throughput, but its economic advantage is less robust than the H2 lever. Short and medium runs around r_bat_e=3.0 to 3.5 looked strong, but the long-run final result settled below the best H2-storage candidate.
- PEM expansion is not the dominant bottleneck in the current Shanghai baseline neighborhood. Increasing r_pem to 0.6 did not deliver a better cost-performance tradeoff, and PEM-including combinations did not beat the best non-PEM candidates.
- CO2 storage expansion has a weaker positive effect than H2 storage and battery energy. It can improve cost and output slightly, but it did not emerge as the main driver in the tested region.
- Battery-H2 interactions are sub-additive in the tested neighborhood. Combining the individually good battery and H2 settings did not outperform the best H2-only candidate after adaptation.

## Strategy Mapping Findings
- Better-performing policies did not simply push methanol pull harder. Compared with the guarded baseline, strong candidates usually lowered average methanol pull ratio and reduced battery reserve preference, while still increasing annual methanol output. This indicates a shift toward steadier, better-buffered operation rather than aggressive instantaneous pulling.
- Successful H2-storage expansion was associated with a higher effective H2 inventory target and a noticeably lower battery reserve preference. The controller relied more on hydrogen buffering and less on conservative battery holding.
- Strong battery-expansion candidates also reduced battery reserve preference relative to baseline, suggesting that larger battery energy capacity gave the policy confidence to operate with less reserve hoarding.
- Strong final candidates increased CO2 target ratios as well, indicating that once hydrogen buffering improved, the policy preferred to hold more carbon-side readiness and feed the methanol section more smoothly over the year.

## Practical Conclusion
- For the currently explored Shanghai baseline neighborhood, the dominant design direction is to increase H2 storage to a moderate higher range first. Battery energy expansion remains a valid secondary lever, especially for output growth, but PEM expansion is not the preferred next investment under the current assumptions.