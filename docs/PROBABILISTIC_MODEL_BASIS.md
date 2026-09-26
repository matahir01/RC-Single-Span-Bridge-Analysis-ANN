# Probabilistic model basis for the ANN/reliability study

Date: 26 September 2026

## Purpose and status

This note records the evidence basis for the stochastic layer of the 15 m RC-girder study.
The deterministic bridge engine is already verified within its documented V1 scope; this
note does **not** reopen that software gate. It controls a different question: whether the
probability model, ANN surrogate, reliability estimates and RBDO conclusions are defensible
for thesis/paper use.

The principal generic source is the Joint Committee on Structural Safety (JCSS)
Probabilistic Model Code (PMC):

- Part I, Basis of Design: https://www.jcss-lc.org/publications/jcsspmc/part_i.pdf
- Part II, Load Models: https://www.jcss-lc.org/publications/jcsspmc/part_ii.pdf
- Part III, Resistance Models: https://www.jcss-lc.org/publications/jcsspmc/part_iii.pdf
- Concrete: https://www.jcss-lc.org/publications/jcsspmc/concrete.pdf
- Reinforcing steel: https://www.jcss-lc.org/publications/jcsspmc/rebar.pdf
- Self weight: https://www.jcss-lc.org/publications/jcsspmc/self_weight.pdf
- Dimensions: https://www.jcss-lc.org/publications/jcsspmc/dimen00.pdf
- Model uncertainty: https://www.jcss-lc.org/publications/jcsspmc/modeluncertainties.pdf

These are generic prior models. Project test data, Nigerian traffic information and an
adopted authority/National Annex basis take precedence when available.

## 1. Concrete compressive strength

JCSS does not reduce concrete strength to a universal `mean = fck` plus a universal COV.
Its concrete model is hierarchical/predictive and permits updating with production/test data.
For C35, the source gives the following prior log-space parameters:

| Production type | m' | n' | s' | v' |
| --- | ---: | ---: | ---: | ---: |
| Ready mixed C35 | 3.85 | 3.0 | 0.09 | 10 |
| Precast C35 | 3.95 | 3.0 | 0.08 | 10 |

Where the JCSS conditions for its lognormal approximation are met, the repository now
computes the approximation directly rather than hard-coding a guessed COV:

`src/rc_single_span/research/source_profiles.py`

For the un-updated priors this gives approximately:

- ready-mixed C35: mean 47.35 MPa, COV 0.1237;
- precast C35: mean 52.25 MPa, COV 0.1099.

These are generic JCSS priors, not local Nigerian production measurements. The final study
must state whether the adopted concrete-production basis is ready mixed, precast, locally
updated, or treated by sensitivity analysis. Because the physical bridge contains a precast
girder and cast-in-situ deck, a single concrete-strength variable is a modelling reduction
that must be acknowledged if retained.

## 2. Reinforcing-steel yield strength and bar area

For high-standard reinforcing-steel production, the JCSS model gives an overall yield-strength
standard deviation of about 30 MPa. Under controlled production, the global mean is
approximately nominal grade plus `2 sigma`, and a normal distribution may be adopted for the
tabulated quantities. For a nominal 500 MPa product this corresponds to a generic mean near
560 MPa before any optional diameter correction.

JCSS gives reinforcement-area ratio relative to nominal area with mean 1.0 and COV 0.02.
The repository now exposes both source-derived profiles explicitly. If the research variable
represents an as-built discrete cage, `steel_area_mm2` should be tied to the selected nominal
cage rather than treated as an arbitrary unconstrained continuous area.

## 3. Dimensions and effective depth

For external reinforced-concrete dimensions up to roughly 1000 mm, the generic JCSS guidance
supports a normal model with approximately:

- mean dimensional deviation `min(0.003 X_nom, 3 mm)`;
- standard deviation `min(4 mm + 0.006 X_nom, 10 mm)`.

For effective depth, where better information is unavailable, JCSS gives the rough default
for deviation from nominal as approximately +10 mm mean and 10 mm standard deviation.

These absolute-mm models are now implemented in `source_profiles.py`. They replace the idea
that a convenient percentage COV should automatically be used for every dimension. JCSS also
warns that depth/cover can be correlated; if cover is later added as a separate variable, the
study must avoid double counting the same construction deviation.

## 4. Permanent action / self weight

JCSS models self weight through material density and dimensions. Ordinary concrete is given a
generic mean weight density of about 24 kN/m3 with COV 0.04. The bridge model, however, also
contains surfacing, barriers/line actions and other superimposed permanent actions.

A single `dead_load_factor` is therefore a **reduced response-separation model**. It may be
used only if its distribution is derived from the component permanent actions or supported by
a cited alternative source. The helper `build_jcss_reference_variables(...)` deliberately
requires the caller to provide `dead_load_factor`; it does not invent one.

The deterministic engine already separates permanent-load categories, so a later thesis
refinement can replace the scalar factor with category-specific stochastic factors without
changing the deterministic loading engine.

## 5. Road traffic / LM1 uncertainty

BS EN 1991-2 Load Model 1 is a calibrated characteristic bridge traffic model. The Eurocode
worked examples explain its calibration from measured European traffic and the long return
period used for the characteristic road-traffic model. A lifetime traffic random variable is
therefore **not** defensibly created by placing an arbitrary lognormal COV around `LM1 = 1.0`.

Useful general bridge-traffic background includes:

- JRC, *Bridge Design – Eurocodes Worked Examples*:
  https://eurocodes.jrc.ec.europa.eu/sites/default/files/2022-06/Bridge_Design-Eurocodes-Worked_examples.pdf
- O'Brien et al. (2016), *The Effect of Traffic Growth on Characteristic Bridge Load Effects*,
  Transportation Research Procedia 14, 3990-3999,
  https://doi.org/10.1016/j.trpro.2016.05.496

### 5.1 Nigeria-specific traffic evidence now ingested

The repository now contains a source-traceable Nigeria traffic evidence layer in
`research/nigeria_traffic.py`.

**Federal Ministry of Works Highway Manual.** Appendix A reports an extensive Nigerian
Federal Road Network axle-load study completed in 2008 and explicitly states that overloading
was rife. It provides representative ADT/heavy-vehicle flows. Examples relevant to northern
corridors include:

| Link | ADT | Heavy vehicles/day | Heavy vehicles |
| --- | ---: | ---: | ---: |
| Ilorin-Jebba | 5,000 | 2,200 | 44% |
| Lokoja-Abuja | 9,000 | 900 | 10% |
| Abuja-Kaduna | 8,000 | 800 | 10% |
| Jos-Bauchi | 7,000 | 380 | 5% |
| Bauchi-Yola | 4,200 | 370 | 9% |
| Kaduna-Zaria | 11,000 | 920 | 8% |
| Potisku-Maiduguri | 5,000 | 920 | 18% |
| Maiduguri-Ngala | 3,000 | 1,000 | 33% |

Source:
https://www.fmw.gov.ng/themes/front_end_themes_01/images/uploads_images/1569354557.pdf

The same manual gives pavement-oriented ESA/heavy-vehicle evidence showing the severity of
overloading, but **ESAs are not converted directly into bridge LM1 effects** in this project.
Pavement equivalency factors and bridge bending/shear extremes are different response problems.

**Kaduna-Zaria WIM spectra.** Awosanya, Murana & Olowosulu (2024) publish portable-WIM axle
spectra by axle configuration and direction. The paper reports 86/99 trucks southbound/
northbound, with 229/268 counted axles and average 2.66/2.71 axles per truck. Its Table 3
contains the complete binned frequencies for single-axle single-tyre, single-axle dual-tyre,
tandem-dual and the very small tridem sample. Those bins are digitised in
`kaduna_zaria_wim_spectra_2024()` and regression-tested against the published totals.

Source:
https://www.azojete.com.ng/index.php/azojete/article/view/937

A newer open-access 2026 Nigerian WIM study also reports axle-load violations on the
Lokoja-Abuja, Ilorin-Jebba and Abakaliki-Ogoja freight corridors:
https://doi.org/10.1016/j.trip.2026.101946

### 5.2 What the public Nigerian data do and do not allow

The public sources establish that Nigerian heavy-vehicle loading and overloading cannot be
represented responsibly by assuming European traffic statistics without qualification. They
also provide real axle spectra and corridor flow evidence for sensitivity studies.

They do **not**, in the currently available public tables, provide a complete vehicle-by-
vehicle joint sequence containing all axle-group weights, axle spacings, inter-vehicle gaps and
time ordering needed for a defensible 15 m bridge extreme-load simulation. The 2024 paper
states that GVM and individual axle weights were measured, but the published tables provide
aggregated axle spectra rather than the raw joint vehicle records.

Consequently:

- the repository does not convert pavement ESAL/ESA values into a bridge load multiplier;
- the published axle bins are not recombined randomly and labelled as observed vehicles;
- `nigeria_traffic_evidence().bridge_effect_calibration_ready` remains `False`;
- a final Nigeria-specific bridge traffic calibration requires raw/joint WIM vehicle data or a
  separately justified vehicle-generation model.

If raw Nigerian WIM records cannot be obtained, the defensible fallback is a clearly labelled
proxy scenario with sensitivity analysis, not a claim that an arbitrary COV is locally observed.

## 6. Model uncertainty

JCSS recommends explicit model-uncertainty factors. Generic values now represented directly in
the evaluator are:

| Model uncertainty | Distribution | Mean | COV |
| --- | --- | ---: | ---: |
| Frame load-effect moment | Lognormal | 1.0 | 0.10 |
| Frame load-effect shear | Lognormal | 1.0 | 0.10 |
| Concrete bending resistance | Lognormal | 1.2 | 0.15 |
| Concrete shear resistance | Lognormal | 1.0 | 0.10 |

The research feature vector contains:

- `moment_load_model_factor`;
- `shear_load_model_factor`;
- `flexure_resistance_model_factor`;
- `shear_resistance_model_factor`.

Moment/shear demand is first assembled from permanent and traffic response components and then
multiplied by its matching load-effect model factor. The physical BS EN/EC2 resistance is
multiplied by the matching resistance-model factor. Nominal and adjusted values are retained in
the evaluator output.

A generic deflection model-error factor has **not** been invented. Before final runs, the thesis
must verify that the adopted JCSS factors do not double count uncertainty already represented
elsewhere and explain their applicability to the response-separation model.

## 7. Dependence and correlation

A Gaussian-copula dependence model is implemented. The declared matrix is in latent standard-
normal space and must be symmetric, positive definite, unit diagonal and ordered exactly like
the stochastic variables. The same dependence model is propagated through:

- LHS dataset generation;
- sample-size convergence;
- fresh direct-vs-ANN validation;
- direct Monte Carlo;
- ANN Monte Carlo;
- FORM; and
- RBDO FORM constraints.

FORM still searches in independent standard-normal `u` space; the Cholesky transform maps
that vector to correlated latent normals before the marginal transforms.

The **software mechanism is implemented**, but final coefficients are unresolved. The disabled
identity matrix in the example configuration is only a placeholder and must not be reported as
empirical independence.

## 8. Target reliability index

Source-pinned EN 1990 Annex C/JRC ULS reference targets are implemented explicitly:

| Consequence class | beta, 1 year | beta, 50 years |
| --- | ---: | ---: |
| CC1 | 4.2 | 3.3 |
| CC2 | 4.7 | 3.8 |
| CC3 | 5.2 | 4.3 |

Verified JRC background page:
https://eurocodes.jrc.ec.europa.eu/publications/reliability-background-eurocodes

**Study decision:** use CC2 / 50 years / beta = 3.8 as the central thesis reference scenario,
with CC1 and CC3 50-year targets retained for sensitivity. This is a research scenario, not an
automatic classification of a real Nigerian bridge. A real project still requires the class,
reference period and National Annex/authority basis actually adopted for that project.

## 9. Current source-backed software status

The following research mechanisms are now implemented and tested:

- JCSS C35 source-prior helpers for ready-mixed and precast production;
- JCSS B500-type yield-strength and reinforcement-area profiles;
- JCSS dimensional/effective-depth profiles;
- explicit JCSS moment/shear load-effect and resistance-model uncertainty variables;
- Gaussian-copula dependent LHS, Monte Carlo, FORM and RBDO constraints;
- EN 1990/JRC target-reliability profiles;
- Nigerian Federal Road Network flow evidence; and
- digitised Kaduna-Zaria WIM axle spectra with published count totals pinned by tests.

`build_jcss_reference_variables(...)` assembles the source-backed variables in the exact ANN
feature order but intentionally requires the final `dead_load_factor` and `live_load_factor`
models as explicit inputs. This keeps unresolved action models visible instead of allowing a
helper to manufacture them.

## 10. Remaining probability-model closure work

Before `assumptions_confirmed` can become `true` for the final thesis study:

1. select the concrete-production treatment and state how precast girder/cast deck differences
   are represented;
2. confirm the B500 production/diameter treatment and selected nominal reinforcement cage;
3. adopt the source-derived dimensional models or replace them with project QC measurements;
4. derive the permanent-action factor from the actual permanent components or adopt a cited
   alternative;
5. obtain joint Nigerian WIM vehicle records for direct bridge extreme-value calibration, or
   formally adopt and sensitivity-test a documented proxy traffic model;
6. verify no double counting in the model-uncertainty factors;
7. adopt source-justified dependence coefficients or document defensible independence;
8. demonstrate LHS/sample-size convergence with the final probability model;
9. train/select the ANN from held-out and near-limit-state evidence;
10. cross-check FORM, ANN Monte Carlo and direct-evaluator Monte Carlo; and
11. perform RBDO and independently re-evaluate the final optimum.

The probabilistic research gate therefore remains **VALIDATION PENDING**. The remaining
blockers are evidence/parameter decisions and final numerical validation, not missing basic
ANN/reliability software infrastructure.
