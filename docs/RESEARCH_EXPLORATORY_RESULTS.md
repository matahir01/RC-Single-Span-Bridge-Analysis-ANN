# Exploratory ANN/reliability run: numerical audit

Run: [GitHub Actions 36671364046](https://github.com/matahir01/RC-Single-Span-Bridge-Analysis-ANN/actions/runs/36671364046) on commit
`88712208e00ec4c8b4d79d8d2e46769b5681d5f4` (30 September 2026).
[Download dataset, splits, ANN model, config and full summary](https://github.com/matahir01/RC-Single-Span-Bridge-Analysis-ANN/actions/runs/36671364046/artifacts/11078577938).
The Actions artifact SHA-256 is
`ea4f08a37220e44258cbcf7944ef6856037e7e93d59a411dd3f32b01beec9031`.
The JSON summary is retained at `docs/research_runs/2026-09-30_exploratory_summary.json`.
The source config, seeds and assumptions are in
`examples/provisional_exploratory_config.json` and [RESEARCH_EXPLORATORY.md](RESEARCH_EXPLORATORY.md).

| Check | Observed result | Decision |
| --- | --- | --- |
| LHS and separation | 1,500 valid rows; 1,050 train, 225 validation, 225 untouched test; zero invalid | Reproducible mechanism; sample adequacy still open. |
| Test ANN R² (flexure, shear, deflection) | 0.9844, 0.9875, 0.9872 | Global fit alone cannot certify the failure boundary. |
| Fresh 250-point direct check | R² 0.9894, 0.9884, 0.9894; near-limit sample counts 0, 67, 0 | No near-boundary check for flexure or deflection. |
| Independent LHS response convergence | Maximum standardized changes 0.1678 at 1,000, 0.1498 at 1,500, **0.05469 at 2,000** versus declared 0.05 | The planned 1,000–2,000 range did **not** meet this criterion. Tail convergence needs separate work. |
| Direct shear MC | 2,011 failures / 5,000: Pf 0.4022, 95% Wilson interval 0.3887–0.4159 | This provisional no-designed-link shear model has a large failure fraction; review the physical shear/link and action inputs. |
| ANN shear MC | 12,210 failures / 30,000: Pf 0.4070, 95% Wilson interval 0.4015–0.4126 | Broad agreement with direct shear sampling under the **same provisional model**; no design acceptance. |
| Flexure and deflection MC | Zero failures in each 5,000-point direct check; 95% Pf upper bound 0.000768 | Cannot establish the provisional CC2/50-year β=3.8 target (Pf about 0.000072). The reported continuity-corrected β is not proof of target reliability. |
| FORM | All three baseline searches reached 100 iterations without convergence | Their β values are **invalid as reliability estimates**. |
| Continuous-As RBDO | SLSQP reported failure; returned bound As=9,000 mm²; nominal training As domain 11,961–13,765 mm²; candidate direct shear Pf 0.4202 | No accepted optimum. Candidate extrapolates outside training and does not satisfy the shear requirement. |

The source-backed JCSS priors apply to only part of this model. Dead/live action
multipliers, independence, no-link shear treatment, deflection limit and the
3.0 m exploratory LM1 grid are not approved project inputs. The deterministic
software's separate V1 verification and the working Windows desktop package do
not turn these exploratory probability results into a bridge design.

## Independent LHS extension (1 October 2026)

The same unconfirmed configuration and 3.0 m deterministic baseline were
re-evaluated with independent LHS samples at 2,000, 3,000, 4,000, 6,000 and
8,000 points, seeds 20261001–20261005. The exact configuration SHA-256,
response statistics and seeds are in
[`2026-10-01_lhs_extension.json`](research_runs/2026-10-01_lhs_extension.json);
reproduce with `python examples/audit_provisional_lhs.py
examples/provisional_exploratory_config.json --output <file.json>`.

| Adjacent sizes | Maximum standardized response change | Governing statistic | 5% gate |
| --- | ---: | --- | --- |
| 2,000 → 3,000 | 10.639% | Shear-margin 5% quantile | Fail |
| 3,000 → 4,000 | 5.956% | Shear-margin 5% quantile | Fail |
| 4,000 → 6,000 | 9.600% | Shear-margin 5% quantile | Fail |
| 6,000 → 8,000 | 8.325% | Shear-margin 5% quantile | Fail |

The fresh run exactly reproduced the independently executed numerical record.
No sample size through 8,000 passes this particular adjacent independent-LHS
rule; increasing the count alone is not an adopted stopping decision. The
lower shear tail remains unstable, and this mean/quantile check does not prove
rare-event probability accuracy. Stratified/replicated tail studies, near-limit
validation and physical action/link evidence are still needed before retraining
the ANN or claiming RBDO reliability.

## Replicated LHS and direct boundary challenge

An additional replicated and direct-boundary diagnostic was run on 1 October
using the **same unconfirmed** config and the saved 1,500-row ANN model from
the original Actions artifact. The model archive's exact SHA-256 and the
training CSV hash are recorded in
[`2026-10-01_replicated_lhs_boundary.json`](research_runs/2026-10-01_replicated_lhs_boundary.json).
The new loader restores the old NPZ with explicit feature/target order and
checks all scaler and layer shapes; no ANN retraining occurred. An independent
reload and evaluation of the untouched 225-row test CSV reproduces all three
original R² values exactly and its RMSE values within 6 × 10⁻¹⁴. Reproduce with
`python examples/audit_research_numerical_gates.py
examples/provisional_exploratory_config.json --model <ann_model.npz>
--train <train.csv> --test <test.csv> --output <audit.json>`.

Three independently seeded LHS replications at each count (42,000 direct
evaluations, seeds 20261001–20261009) show why a single adjacent-size
comparison is inadequate:

| Samples per replicate | Maximum between-replicate standardized response change | Change in replicate-mean statistics from previous size | 5% screen |
| ---: | ---: | ---: | --- |
| 2,000 | 8.079% | — | Fail |
| 4,000 | 4.726% | 3.150% | Pass at this size only |
| 8,000 | **7.417%** | 2.748% | **Fail** |

The screen requires both last sizes to be stable between seeds and their
mean statistics to be stable across sizes. It fails. These are response
statistics, not a rare-event probability confidence interval. [SciPy's QMC
documentation](https://docs.scipy.org/doc/scipy/reference/stats.qmc.html)
describes independent randomized replications as a stability check; this
implementation uses a fresh randomized Latin hypercube per seed and size.

A fresh **direct evaluator** search over each marginal's 0.1–99.9% quantile
interval then bracketed the shear limit state and bisected to a direct
margin of approximately zero. At that point, which lies within every axis
range of the saved training split, the ANN predicted **+3.805 kN** of shear
margin (the safe side). Its absolute boundary error is 3.805 kN. The search
did not find a flexure or deflection sign change; the candidate margins
remained positive, but the global heuristic cannot prove a boundary is
absent. Joint corners in this diagnostic do not respect a selected copula
or carry a failure probability. This is a boundary prediction check, **not**
a reliability estimate or an accepted surrogate. The shear result alone
blocks the saved ANN from use as a failure-classifier near `g=0`.

## Required next research run

Resolve the permanent-action decomposition, joint vehicle/time traffic model
or explicitly bounded proxy sensitivity, dependence, physical shear links and
serviceability criterion. Expand/adapt sampling until the declared response
criterion and near-boundary validation are met. Verify the surrogate over the
RBDO design domain, require converged FORM or a justified alternative tail
method, and directly re-evaluate a feasible buildable cage. Keep the CC2/50-year
reference target editable pending project classification and authority basis.
