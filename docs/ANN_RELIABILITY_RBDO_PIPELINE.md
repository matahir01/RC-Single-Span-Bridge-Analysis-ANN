# ANN-assisted reliability and RBDO pipeline

Date: 3 October 2026

## Status

The repository contains an integrated research pipeline for:

1. explicit random-variable definition;
2. Latin-hypercube sampling (LHS), including optional Gaussian-copula dependence;
3. deterministic limit-state evaluation;
4. explicit load-effect and resistance-model uncertainty factors;
5. multi-output ANN surrogate training;
6. held-out and fresh-direct surrogate validation;
7. FORM reliability analysis in independent standard-normal space;
8. surrogate and direct Monte-Carlo reliability checks; and
9. reliability-based design optimisation (RBDO).

This is **research infrastructure, not a closed research result**. The deterministic
bridge-analysis/design software has its own verification record. The ANN,
probabilistic model and RBDO study require a separate evidence trail before their
numerical conclusions can be accepted in a thesis or paper.

The desktop **ANN / Reliability** tab now exposes this pipeline as a study
workbench. It edits the random-variable model, LHS and direct-validation counts,
direct Monte-Carlo count and BS EN LM1 step; the complete JSON configuration
also carries dependence, ANN, FORM, convergence and RBDO settings. A run uses
the current bridge project, runs off the UI thread, reports phases and supports
cooperative cancellation. Its output directory freezes the configuration and
project, dataset and train/validation/test CSV files, ANN model, numerical
summary and artifact hashes. The results can be previewed and exported as study
sheets. These controls expose the software workflow; they do not certify the
probability model or make exploratory results acceptable.

The packaged configuration remains `assumptions_confirmed=false`. The GUI
labels such a run **EXPLORATORY ONLY** and preserves the open evidence gates.
Users can load a sourced configuration when the study basis is ready. See
[`GUI_IMPLEMENTATION.md`](GUI_IMPLEMENTATION.md) for the desktop workflow.

## Deterministic-to-stochastic interface

The BS EN research path uses `BSENReliabilityBaseline` to extract separate
characteristic permanent and LM1 response components from a verified deterministic
reference run. The stochastic evaluator then applies uncertain material, geometry,
action and model-error variables to that baseline.

The current feature vector is:

- `fck_mpa` — concrete compressive strength;
- `fyk_mpa` — reinforcement yield strength;
- `effective_depth_m` — effective depth;
- `web_width_m` — girder/web width;
- `steel_area_mm2` — longitudinal tension-steel area;
- `dead_load_factor` — multiplier on the verified permanent response;
- `live_load_factor` — multiplier on the verified LM1 response;
- `moment_load_model_factor` — moment load-effect model uncertainty;
- `shear_load_model_factor` — shear load-effect model uncertainty;
- `flexure_resistance_model_factor` — flexural-resistance model uncertainty; and
- `shear_resistance_model_factor` — shear-resistance model uncertainty.

The last four variables were added so generic JCSS model uncertainty is not hidden
inside deterministic constants. The illustrative configuration uses the JCSS generic
lognormal values documented in `PROBABILISTIC_MODEL_BASIS.md`, but the final thesis
still has to justify their applicability and avoid double counting with other model
or action uncertainty.

The ANN targets remain physical limit-state margins:

- `g_flexure_knm = theta_RM R_M - theta_EM S_M`;
- `g_shear_kn = theta_RV R_V - theta_EV S_V`; and
- `g_deflection_mm = delta_limit - delta`.

Failure is `g <= 0`. A generic deflection model-error factor has **not** been invented:
no adopted source in the current evidence package justifies reusing the moment/shear
model-error values for deflection.

### Important response-separation boundary

The stochastic evaluator does **not** rebuild and solve a new full grillage for every
sampled point. The expensive traffic placement/distribution search is performed in
the deterministic baseline; sample-by-sample permanent and traffic multipliers scale
those verified response components. Sampled web width is carried into resistance
checks and the gross-section flexural-inertia scaling used by the elastic deflection
approximation.

That choice is deliberate and auditable. It is suitable only if the adopted research
methodology accepts response separation for the selected random variables. It must
not be described as a full stochastic finite-element/grillage re-analysis. If the
final methodology requires geometry-dependent re-analysis of traffic distribution or
other structural-model variables, a full-analysis evaluator must be added and the ANN
retrained on those outputs.

## Resistance and model uncertainty

The stochastic flexural and shear checks call the production BS EN/EC2 resistance
kernels rather than duplicated surrogate-only formulae.

The evaluator defaults `gamma_c = gamma_s = 1.0` because sampled material strengths
and actions are intended as physical random variables. This is not a code partial-
factor design check. Any alternative convention must be explicit and justified.

The physical resistance from the deterministic kernel is then multiplied by the
sampled resistance-model factor, while the separated permanent+traffic demand is
multiplied by its matching load-effect model factor. Nominal and model-adjusted
resistances/effects are retained in the evaluation output for auditability.

For shear, a project may provide `Asw/s`. When supplied, the stochastic shear margin
uses the lesser of calculated link resistance and crushing resistance before applying
the shear-resistance model factor. If no link quantity is supplied, the evaluator uses
the concrete/no-designed-link resistance path rather than inventing reinforcement.

## Deflection model

The reliability baseline uses the retained deterministic displacement evidence. With
the response-specific LM1 influence-surface search, the baseline records the governing
traffic displacement and characteristic permanent displacement consistently.

The stochastic evaluator can scale that baseline by the ratio of nominal to sampled
gross flexural inertia. This is an elastic response approximation, not a nonlinear
cracked/time-dependent deflection model.

The deflection acceptance limit is mandatory input. No universal hidden span-ratio
criterion is inserted by the research pipeline.

## Random variables, dependence and sampling

`research.sampling` supports normal, lognormal and uniform marginals with optional
lower/upper truncation for normal and lognormal variables. Truncation uses probability
remapping rather than clipping, avoiding artificial point masses at the bounds.

`GaussianCopula` provides an explicit dependence model. The declared matrix is a
correlation matrix in latent standard-normal space and must be symmetric, positive
definite, unit-diagonal and ordered exactly like the random variables. The same
copula can be propagated through:

- LHS dataset generation;
- sample-size convergence audits;
- fresh direct-vs-ANN validation;
- direct Monte Carlo;
- ANN Monte Carlo;
- FORM transforms; and
- the FORM constraints used by RBDO.

FORM still searches in an **independent** standard-normal `u` space. The Cholesky
transform maps that `u` vector into correlated latent-normal coordinates before the
marginal probability transforms. Beta therefore retains its standard reliability-
space interpretation.

An identity matrix in the example configuration is only a placeholder. It is disabled
by default and must not be described as observed independence. The final study must
justify each non-zero correlation and every decision to neglect a plausible dependence.

LHS is generated through SciPy's `qmc.LatinHypercube`, with stored seeds for
reproducibility. The repository also contains a direct sample-size convergence audit.
The example value of 1,500 samples and the 70/15/15 split are software/example settings,
not automatic thesis justification.

For every random variable, the final study must document:

- probabilistic family;
- mean or nominal/bias model;
- standard deviation or coefficient of variation;
- truncation bounds, if any;
- evidence/source;
- dependence/correlation assumptions; and
- whether the variable represents natural variability, action uncertainty or model
  uncertainty.

## Target reliability

The software now exposes source-pinned EN 1990 Annex C/JRC ULS reference targets through
`bs_en_1990_target_reliability(...)` rather than hiding a single beta value:

| Consequence class | beta, 1 year | beta, 50 years |
| --- | ---: | ---: |
| CC1 | 4.2 | 3.3 |
| CC2 | 4.7 | 3.8 |
| CC3 | 5.2 | 4.3 |

The example study uses **CC2 / 50 years / beta = 3.8 as a thesis reference scenario**, not
as an automatic classification of a real Nigerian bridge. CC1 and CC3 are retained for
sensitivity reporting. A real project must use the consequence class, National Annex and
reference period required by its approving authority/project basis.

## ANN surrogate

Two backends are available:

- `NumpyMLPRegressor` — lightweight multi-output MLP used by CI and reproducible CPU
  experiments;
- TensorFlow/Keras — optional thesis-production backend installed with `.[ann]`.

Both use standardized features and targets, ReLU hidden layers, linear multi-output
regression and early stopping. The default hidden architecture is `(64, 64)`, but the
final architecture must be selected from validation evidence rather than retained
merely because it is the default.

Reported surrogate evidence should include held-out RMSE, MAE and R2 for each target.
`validate_surrogate_against_direct` adds fresh deterministic points, maximum absolute
error and separate error reporting close to `g = 0`, where reliability estimates are
most sensitive to surrogate error. The same dependence model used for training-sample
generation can be used for this validation set.

A high global R2 alone is **not** sufficient evidence for reliability work if the ANN
is inaccurate near the failure surface.

## Reliability analysis

The pipeline provides complementary methods:

- **FORM** — HLRF search in independent standard-normal reliability space, with the
  optional Gaussian-copula transform applied before the marginal transforms;
- **ANN Monte Carlo** — rapid probability-of-failure estimation with Wilson confidence
  intervals; and
- **direct-evaluator Monte Carlo** — a smaller validation reference using the same
  declared probability/dependence model.

Where computationally practical, ANN probability of failure should be compared with
direct Monte Carlo and FORM. FORM convergence, design points and sensitivity vectors
must be reviewed; numerical agreement should not be judged only from one beta number.

## RBDO

`optimize_surrogate_rbdo` uses SLSQP with ANN-predicted limit states and FORM reliability
constraints. A design variable moves the mean of its corresponding declared random
variable while retaining that variable's stated COV/standard-deviation model. Other
random variables remain unchanged. The same Gaussian-copula model may be passed to the
FORM constraints.

The objective function is intentionally supplied by the study. It may represent a
transparent material-volume, reinforcement-mass, cost or combined objective. The
software does not invent unit costs or environmental coefficients.

Every final RBDO optimum should be re-evaluated by the direct deterministic/reliability
model before it is reported as the study's recommended optimum.

## Required acceptance evidence before thesis use

The ANN/reliability/RBDO phase remains **VALIDATION PENDING** until all of the following
are available:

- final source-justified marginal probability models;
- source-justified dependence coefficients or a defensible independence argument;
- a justified traffic/live-load uncertainty model or explicitly labelled proxy with
  sensitivity analysis;
- demonstrated LHS/sample-size convergence with the final probability model;
- held-out ANN metrics for every limit state;
- fresh direct-vs-ANN validation, especially near `g = 0`;
- FORM convergence/design-point review;
- Monte-Carlo cross-checks with uncertainty/confidence reporting;
- an explicitly declared thesis reliability class/reference period and sensitivity;
- an explicit RBDO objective and bounds; and
- direct verification of the final optimum.

The target-reliability **source basis**, dependence **software capability**, and explicit
moment/shear model-uncertainty **software capability** are now implemented. This does not
close the research gate by itself because the final numerical probability model and
validation evidence are still outstanding.

**ANN/reliability/RBDO implementation: available; research conclusions: not yet accepted.**
