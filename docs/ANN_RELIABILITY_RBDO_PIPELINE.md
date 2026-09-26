# ANN-assisted reliability and RBDO pipeline

Date: 26 September 2026

## Status

The repository now contains an integrated research pipeline for:

1. explicit random-variable definition;
2. Latin-hypercube sampling (LHS);
3. deterministic limit-state evaluation;
4. multi-output ANN surrogate training;
5. held-out surrogate validation;
6. FORM reliability analysis;
7. surrogate Monte-Carlo reliability checks; and
8. reliability-based design optimisation (RBDO).

This is **research infrastructure, not a closed research result**. The deterministic
bridge-analysis/design software has its own verification record. The ANN,
probabilistic model and RBDO study require a separate evidence trail before their
numerical conclusions can be accepted in a thesis or paper.

## Deterministic-to-stochastic interface

The BS EN research path uses `BSENReliabilityBaseline` to extract separate
characteristic permanent and LM1 response components from a verified deterministic
reference run. The stochastic evaluator then applies uncertain resistance variables
and uncertain action multipliers to that baseline.

The initial feature vector is:

- `fck_mpa` — concrete compressive strength;
- `fyk_mpa` — reinforcement yield strength;
- `effective_depth_m` — effective depth;
- `web_width_m` — girder/web width;
- `steel_area_mm2` — longitudinal tension-steel area;
- `dead_load_factor` — multiplier on the verified characteristic permanent response;
- `live_load_factor` — multiplier on the verified characteristic LM1 response.

The initial ANN targets are physical limit-state margins:

- `g_flexure_knm = R_M - S_M`;
- `g_shear_kn = R_V - S_V`; and
- `g_deflection_mm = delta_limit - delta`.

Failure is therefore `g <= 0`.

### Important response-separation boundary

The initial stochastic evaluator does **not** rebuild and solve a new full grillage
for every sampled point. The expensive traffic placement/distribution search is
performed in the deterministic baseline; sample-by-sample permanent and traffic
multipliers scale those verified response components. Sampled web width is also
carried into the resistance checks and the gross-section flexural-inertia scaling
used by the elastic deflection approximation.

That choice is deliberate and auditable. It is suitable only if the adopted research
methodology accepts response separation for the selected random variables. It must
not be described as a full stochastic finite-element/grillage re-analysis. If the
final methodology requires re-analysis of geometry-dependent traffic distribution or
other structural-model variables, a full-analysis evaluator must be added and the ANN
retrained on those outputs.

## Resistance model

The stochastic flexural and shear checks call the production BS EN/EC2 resistance
kernels rather than duplicated surrogate-only formulae.

The research evaluator defaults `gamma_c = gamma_s = 1.0` because the sampled material
strengths and actions are intended as physical random variables. This is not a design
partial-factor check. Any alternative resistance-model convention must be set
explicitly and justified in the methodology.

For shear, a project may provide `Asw/s`. When supplied, the stochastic shear margin
uses the lesser of the calculated link resistance and crushing resistance. If no link
quantity is supplied, the evaluator is intentionally conservative and uses the
concrete/no-designed-link resistance path instead of inventing reinforcement.

## Deflection model

The reliability baseline first uses the exact combined characteristic deflection
envelope when the deterministic run retains all required traffic cases. With the
response-specific LM1 influence-surface search, only governing physical traffic cases
are retained. In that mode the baseline is explicitly labelled as the LM1
traffic-governing displacement station plus the characteristic permanent displacement
at the same station.

The stochastic evaluator can scale that baseline by the ratio of nominal to sampled
gross flexural inertia. This is an elastic response approximation, not a nonlinear
cracked/time-dependent deflection model.

The deflection acceptance limit is mandatory input. No universal hidden span-ratio
criterion is inserted by the research pipeline.

## Random variables and sampling

`research.sampling` currently supports independent normal, lognormal and uniform
variables, with optional lower/upper truncation for normal and lognormal variables.
Truncation is implemented by probability remapping rather than clipping, avoiding
artificial probability masses at the bounds.

LHS is generated through SciPy's `qmc.LatinHypercube`, with a stored seed for
reproducibility. The research pipeline default is 1,500 samples and a 70/15/15
train/validation/test split. Those are software defaults, **not automatically the
final thesis sample-size justification**.

The final study must document for every random variable:

- probabilistic family;
- mean or nominal/bias model;
- standard deviation or coefficient of variation;
- truncation bounds, if any;
- evidence/source;
- whether variables are independent or correlated; and
- whether the variable represents natural variability, model uncertainty or both.

The current transform assumes statistical independence. If the literature or project
basis requires correlations, correlation/Nataf or another justified joint model must
be implemented before final reliability results are reported.

## ANN surrogate

Two backends are available:

- `NumpyMLPRegressor` — lightweight multi-output MLP used by normal CI and reproducible
  CPU experiments;
- TensorFlow/Keras — optional thesis-production backend installed with `.[ann]`.

Both use standardized features and targets, ReLU hidden layers, linear multi-output
regression and early stopping. The default hidden architecture is `(64, 64)`, but the
final architecture must be selected from validation evidence rather than retained
merely because it is the default.

Reported surrogate evidence should include, at minimum, held-out RMSE, MAE and R2 for
each target. `validate_surrogate_against_direct` adds fresh independent deterministic
spot checks, maximum absolute error and separate error reporting close to `g = 0`,
where reliability estimates are most sensitive to surrogate error.

A high global R2 alone is **not** sufficient evidence for reliability work if the ANN
is inaccurate near the failure surface.

## Reliability analysis

The pipeline provides two complementary methods:

- **FORM** — independent-variable HLRF search in standard-normal space using central
  finite-difference gradients and damped updates;
- **Monte Carlo** — independent samples evaluated rapidly by the ANN surrogate, with
  reported raw failure probability and Wilson confidence interval.

`direct_monte_carlo_reliability` is also provided for validation against the direct
limit-state evaluator. Where computationally practical, ANN-based probability of
failure should be compared with direct Monte Carlo on a smaller validation sample and
with FORM/design-point checks.

No target reliability index is built into the code. The target beta used for the
actual bridge study must be justified from the adopted reliability framework,
consequence class/reference period and approving/research basis.

## RBDO

`optimize_surrogate_rbdo` uses SLSQP with ANN-predicted limit states and FORM reliability
constraints. A design variable moves the mean of its corresponding declared random
variable while retaining that variable's stated COV/standard-deviation model. Other
random variables remain unchanged.

The objective function is intentionally supplied by the study. It may represent, for
example, a transparent material-volume, reinforcement-mass, cost or combined objective.
The software does not invent unit costs or environmental coefficients.

Every final RBDO optimum should be re-evaluated by the direct deterministic model and
its reliability constraints independently checked before it is reported as the study's
recommended optimum.

## Required acceptance evidence before thesis use

The ANN/reliability/RBDO research phase should remain **VALIDATION PENDING** until all
of the following are available:

- source-justified probabilistic models for the adopted variables;
- documented treatment of dependence/correlation;
- a justified LHS size/convergence check;
- held-out ANN metrics for every limit state;
- fresh direct-vs-ANN validation points, especially near `g = 0`;
- FORM convergence and design-point review;
- Monte-Carlo cross-checks with uncertainty/confidence reporting;
- a justified target reliability index/reference period;
- an explicit RBDO objective and bounds; and
- direct deterministic verification of the final optimum.

Until those items are closed, the correct status is:

**ANN/reliability/RBDO implementation: available; research conclusions: not yet accepted.**
