# Probabilistic model basis for the ANN/reliability study

Date: 26 September 2026

## Purpose and status

This note records what can presently be justified from published reliability guidance and
what still requires an explicit research decision before the 15 m RC-girder study is run as
a thesis-quality probabilistic analysis.

The deterministic bridge engine is already verified within its documented V1 scope. This
note concerns the **probabilistic layer only**. A deterministic software GO does not turn a
probability model, target reliability level or ANN result into an accepted research result.

The principal generic source is the Joint Committee on Structural Safety (JCSS)
Probabilistic Model Code (PMC). JCSS describes the PMC as a basis for reliability-based
design of specific projects and for code calibration. Relevant stable documents are:

- JCSS, *Probabilistic Model Code, Part I: Basis of Design*:
  https://www.jcss-lc.org/publications/jcsspmc/part_i.pdf
- JCSS, *Part II: Load Models*:
  https://www.jcss-lc.org/publications/jcsspmc/part_ii.pdf
- JCSS, *Part III: Resistance Models*:
  https://www.jcss-lc.org/publications/jcsspmc/part_iii.pdf
- JCSS, *Concrete*:
  https://www.jcss-lc.org/publications/jcsspmc/concrete.pdf
- JCSS, *Static Properties of Reinforcing Steel*:
  https://www.jcss-lc.org/publications/jcsspmc/rebar.pdf
- JCSS, *Self Weight*:
  https://www.jcss-lc.org/publications/jcsspmc/self_weight.pdf
- JCSS, *Dimensions*:
  https://www.jcss-lc.org/publications/jcsspmc/dimen00.pdf
- JCSS, *Model Uncertainties*:
  https://www.jcss-lc.org/publications/jcsspmc/modeluncertainties.pdf

These are generic prior models. They do not override project test data, quality-control data,
site-specific traffic information or an adopted national/authority reliability basis.

## 1. Concrete compressive strength

JCSS does **not** reduce concrete strength to a universal `mean = fck` plus a universal COV.
Its concrete model is hierarchical/predictive and allows prior information to be updated by
production/test information.

For C35 concrete, JCSS Table 3.1.2 gives prior log-space parameters:

| Production type | m' | n' | s' | v' |
| --- | ---: | ---: | ---: | ---: |
| Ready mixed C35 | 3.85 | 3.0 | 0.09 | 10 |
| Precast C35 | 3.95 | 3.0 | 0.08 | 10 |

JCSS explicitly notes that these prior parameters may depend on geographical area and
production technology. It also describes a lognormal approximation only under conditions on
the updated predictive parameters; the full predictive model should therefore not be replaced
silently by an arbitrary `COV = 0.10` model.

**Study decision:** keep `fck_mpa` configurable. Before final runs, either (a) implement/use
the JCSS predictive model with a documented production category and any available updating
data, or (b) adopt a clearly stated lognormal approximation derived from an accepted source
and show sensitivity to that approximation. The illustrative JSON values are not yet accepted.

## 2. Reinforcing-steel yield strength and bar area

The JCSS reinforcing-steel model is much more directly usable for the present study.
For high-standard production it gives component standard deviations that combine to an
overall yield-strength standard deviation of about **30 MPa**. Under controlled production,
the global mean is given as approximately the nominal grade plus `2 sigma`. JCSS states that
a normal distribution can be adopted for the tabulated reinforcing-steel quantities.

For an S500/B500-type nominal grade, the generic JCSS default therefore corresponds to a
global mean around **560 MPa** with standard deviation around **30 MPa**, subject to actual
product/production evidence. This is more defensible as a generic prior than treating 500 MPa
itself as the mean.

For reinforcement area, JCSS gives the area ratio relative to nominal area with mean 1.0 and
COV **0.02**. The source also indicates that yield stress and bar area may be treated as
uncorrelated at the basic-variable level used there, while yield strengths of bars within one
structure can be strongly correlated.

**Study decision:** the final configuration should distinguish nominal design grade from the
probabilistic mean. `steel_area_mm2` should normally be generated from the nominal selected
cage times an area-ratio variable rather than interpreted as an unconstrained independent
continuous quantity if the research question is about an as-built discrete cage.

## 3. Dimensions and effective depth

JCSS recommends normal models as reasonable for external reinforced-concrete dimensions.
For dimensions up to roughly 1000 mm, its generic guidance gives a mean dimensional
deviation of approximately `0.003 X_nom` (capped at about 3 mm) and a standard deviation
approximately `4 mm + 0.006 X_nom` (capped at about 10 mm).

For effective depth, where no better information is available, JCSS gives the rough default
for the deviation from nominal:

- mean deviation approximately **+10 mm**;
- standard deviation approximately **10 mm**.

JCSS also warns that depth and reinforcement cover can be highly correlated and that cover
statistics are strongly dependent on construction/spacer practice.

**Study decision:** replace the illustrative percentage COVs for `web_width_m` and
`effective_depth_m` with absolute-mm models derived from selected nominal geometry unless
project quality-control measurements justify another model. If cover is introduced separately,
dependence with effective depth must be handled explicitly rather than double-counted.

## 4. Permanent action / self weight

JCSS Part II models self-weight through material weight density and dimensions. For ordinary
concrete it gives a mean weight density of **24 kN/m3** with COV **0.04**; high-strength
concrete is listed around 24-26 kN/m3 with COV 0.03. Dimensions and density are random
contributors to self weight.

A single `dead_load_factor` is therefore only a reduced model. It combines material density,
geometry, surfacing, barriers and other permanent-action uncertainty into one multiplier.
That may be acceptable for an ANN response-separation study, but its mean/COV must be
derived from component permanent actions or supported by another accepted source.

**Study decision:** do not retain the illustrative `dead_load_factor COV = 0.10` as a final
number without derivation. A preferred model is component-based uncertainty for girder, deck,
surfacing/barrier and other superimposed permanent actions, propagated to the baseline response.

## 5. Road traffic / LM1 uncertainty

EN 1991-2 Load Model 1 is itself a calibrated characteristic traffic model. EN 1991-2 Table
2.1 describes the characteristic LM1 basis, for alpha factors equal to 1, as approximately a
**1000-year return-period** traffic action (equivalently about 5% probability of exceedance in
50 years for the calibration traffic on main European roads). The Eurocode bridge worked
examples also explain that LM1 was calibrated from measured European traffic and that the
1000-year return period was deliberately used for the characteristic road-traffic model.

A lifetime traffic random variable is consequently not well represented merely by putting an
arbitrary lognormal COV around `LM1 = 1.0`. Published bridge-traffic reliability work commonly
uses weigh-in-motion (WIM) records, traffic simulation and extreme-value extrapolation; for
example, characteristic effects can be fitted/extrapolated using generalized extreme-value
models and converted to LM1 alpha factors.

Useful background sources include:

- JRC/Eurocodes, *Bridge Design - Eurocodes Worked Examples*:
  https://eurocodes.jrc.ec.europa.eu/sites/default/files/2022-06/Bridge_Design-Eurocodes-Worked_examples.pdf
- O'Brien et al., *The Effect of Traffic Growth on Characteristic Bridge Load Effects*,
  Transportation Research Procedia 14 (2016), 3990-3999,
  https://doi.org/10.1016/j.trpro.2016.05.496

**Study decision:** the illustrative `live_load_factor` lognormal model remains
**UNRESOLVED**. Preferred evidence is Nigerian/site-specific WIM or other defensible traffic
data. If unavailable, the thesis must identify the adopted proxy/calibration, retain LM1's
calibration meaning, and perform sensitivity analysis rather than present a chosen COV as
locally observed fact.

## 6. Model uncertainty

JCSS recommends explicit model-uncertainty factors in reliability work. Its generic table gives,
among other entries:

| Model uncertainty | Distribution | Mean | COV |
| --- | --- | ---: | ---: |
| Frame load-effect moment | Lognormal | 1.0 | 0.10 |
| Frame load-effect shear | Lognormal | 1.0 | 0.10 |
| Concrete bending resistance | Lognormal | 1.2 | 0.15 |
| Concrete shear resistance | Lognormal | 1.0 | 0.10 |

The research evaluator now represents these explicitly as:

- `moment_load_model_factor`;
- `shear_load_model_factor`;
- `flexure_resistance_model_factor`; and
- `shear_resistance_model_factor`.

Moment/shear action components are first formed from the permanent and traffic multipliers and
then multiplied by the matching load-effect model factor. Physical flexural/shear resistance
from the production BS EN/EC2 kernels is multiplied by the matching resistance-model factor.
Both nominal and model-adjusted quantities remain available in evaluator output.

A generic deflection model-error factor has **not** been created because the current JCSS values
used here do not justify copying the moment/shear values into the SLS displacement model.

**Study decision:** the software-capability blocker is closed, but applicability remains a
methodology decision. Before final runs, verify that these generic JCSS factors do not double
count uncertainties already represented in the material/action variables and state why the
selected model-error variables are appropriate to this response-separation model.

## 7. Dependence and correlation

The software now contains a Gaussian-copula dependence model with a correlation matrix in
latent standard-normal space. The matrix must be symmetric, positive definite, unit diagonal
and ordered exactly like the random-variable vector. The same dependence model can be carried
through LHS, convergence audits, ANN/direct validation, direct and surrogate Monte Carlo,
FORM and RBDO reliability constraints.

FORM continues to search in independent standard-normal `u` space. A Cholesky transform maps
that vector to the correlated latent-normal vector before the marginal transforms. This keeps
the reliability-index geometry explicit.

JCSS evidence still shows that independence is not automatically appropriate for all physical
variables; dimensions/cover may be correlated and steel properties within a structure can be
strongly correlated.

**Study decision:** the **software mechanism is implemented**, but the coefficients remain
unresolved. Independence must be justified variable-by-variable. The disabled identity matrix
in the example configuration is only a placeholder and must not be reported as empirical
independence.

## 8. Target reliability index

Source-pinned EN 1990 Annex C/JRC ULS reference targets are implemented explicitly rather than
hidden in the optimizer:

| Consequence class | beta, 1 year | beta, 50 years |
| --- | ---: | ---: |
| CC1 | 4.2 | 3.3 |
| CC2 | 4.7 | 3.8 |
| CC3 | 5.2 | 4.3 |

The European Commission JRC reliability material summarizes these EN 1990 targets and notes
that reliability differentiation / National Annex choices remain part of the adopted basis.

Useful source:

- European Commission JRC, reliability requirements / EN 1990 Annex C material:
  https://eurocodes.jrc.ec.europa.eu/publications/reliability-backgrounds

**Study decision:** use **CC2, 50 years, beta = 3.8 as the central thesis reference scenario**,
with CC1 and CC3 50-year values retained for sensitivity reporting. This is a research scenario,
not an automatic classification of a real bridge. A real project still requires the consequence
class/reference period required by its authority and adopted National Annex.

## 9. Recommended staged probability-model closure

Before the example configuration can be changed from `assumptions_confirmed=false`, close the
following in order:

1. select the production basis for concrete strength and document any local/test updating;
2. adopt the reinforcement yield/area model consistent with the selected B500 product basis;
3. replace percentage dimensional COVs with source/project-based dimensional deviations;
4. derive permanent-action uncertainty from its components;
5. choose and justify the road-traffic extreme/load-model uncertainty treatment;
6. verify applicability/no-double-counting of the now-implemented JCSS model-error factors;
7. adopt source-justified dependence coefficients or document a defensible independence model;
8. demonstrate LHS/sample-size convergence with the final probability model;
9. run ANN architecture/validation acceptance checks;
10. cross-check FORM, ANN Monte Carlo and direct-evaluator Monte Carlo; and
11. perform RBDO and independently re-evaluate the final optimum.

The target-reliability source basis, Gaussian-copula infrastructure and explicit moment/shear
model-error infrastructure are now implemented. The remaining blockers are the **final numerical
probability model and validation evidence**, especially concrete, permanent action, road traffic,
dependence coefficients, sample-size convergence and ANN/reliability/RBDO validation.

Until those decisions and numerical checks are closed, the probabilistic research gate remains
**VALIDATION PENDING** even though the complete software pipeline is executable.
