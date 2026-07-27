#Frozen research protocol

- Protocol source: `PLAN_QUANT_RESEARCH_HSMM_XAUUSD.md`
- Frozen configuration: `configs/research_v1.yaml`
- Frozen on: 2026-07-16
- Primary asset/frequency: XAUUSD M15
- Primary label horizon: 16 bars; sensitivities: 8 and 32 bars
- Candidate states: mean reversion, trend, breakout, neutral
- Candidate state counts: 3, 4, 5; primary: 4
- Primary comparison: explicit-duration HSMM versus Gaussian HMM
- Trading inference: filtered posterior only; smoothing and Viterbi are diagnostic only
- OOS rule: scaler, feature selection, calibration and model fit are training-only
- Entry rule: next executable quote after the signal bar closes
- Decision rule: net expected value must be positive after observed spread and configured costs

##Data deviation registered before modelling

The local corpus does not contain the protocol's requested 2012–2020 XAUUSD history.
Observed XAUUSD coverage starts in January 2021 and ends in May 2026. XAGUSD and
NSXUSD context start in May 2024. Results must therefore be described as a reduced
historical study, not as validation of the original 2012–2026 design. A second
independent XAUUSD provider and macro-event history are also absent.

##Protected decisions

Thresholds in the frozen YAML are starting values, not results. Changes require a new
configuration version and a ledger entry. OOS blocks may never be used to select
features, state semantics, duration family, probability threshold, or cost assumptions.

##Pre-fit data-rule amendment

Before any model fit, `max_gap_bars` was corrected from 4 to 480. The initial one-hour
rule split the corpus at routine daily rollovers (864 segments and about 21% repeated
feature warm-up). The corrected five-day rule resets state only at abnormal outages,
while weekend and holiday gaps remain observable market jumps. This amendment used no
model or OOS result.
