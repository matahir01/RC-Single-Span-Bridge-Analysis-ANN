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
design of specific projects and for code calibration. The relevant stable documents are:

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
global mean around **560 MPa** with standard deviation around **30 MPa**, subject to the
actual product/production evidence. This is more defensible as a generic prior than treating
500 MPa itself as the mean.

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
`effective_depth_m` with absolute-mm models derived from the selected nominal geometry,
unless project quality-control measurements justify another model. If cover is introduced as
a separate variable, dependence with effective depth must be handled explicitly rather than
double-counted.

## 4. Permanent action / self weight

JCSS Part II models self-weight through material weight density and dimensions. For ordinary
concrete it gives a mean weight density of **24 kN/m3** with COV **0.04**; high-strength
concrete is listed around 24-26 kN/m3 with COV 0.03. Dimensions and density are treated as
random contributors to self weight.

A single `dead_load_factor` is therefore only a reduced model. It combines material density,
geometry, surfacing, barriers and other permanent-action uncertainty into one multiplier.
That may be acceptable for an ANN response-separation study, but its mean/COV must be
derived from the component permanent actions or supported by another accepted source.

**Study decision:** do not retain the illustrative `dead_load_factor COV = 0.10` as a final
number without derivation. A preferred next model is component-based uncertainty for girder,
deck, surfacing/barrier and other superimposed permanent actions, propagated to the baseline
response.

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

**Study decision:** the current illustrative `live_load_factor` lognormal model remains
**UNRESOLVED**. Preferred evidence is Nigerian/site-specific WIM or other defensible traffic
data. If that is unavailable, the thesis must clearly identify the adopted proxy/calibration,
retain LM1's calibration meaning, and perform sensitivity analysis rather than presenting a
chosen COV as locally observed fact.

## 6. Model uncertainty

JCSS recommends explicit model-uncertainty factors in reliability work. Its generic table gives,
among other entries:

| Model uncertainty | Distribution | Mean | COV |
| --- | --- | ---: | ---: |
| Frame load-effect moment | Lognormal | 1.0 | 0.10 |
| Frame load-effect shear | Lognormal | 1.0 | 0.10 |
| Concrete bending resistance | Lognormal | 1.2 | 0.15 |
| Concrete shear resistance | Lognormal | 1.0 | 0.10 |

These values are generic and the exact interpretation must match the mechanical model being
used. They should not be multiplied into the present evaluator without checking for overlap
with other uncertainty factors.

**Study decision:** the current seven-variable ANN intentionally does not yet include these
model-error factors. Before final reliability results, either introduce explicit load-effect and
resistance-model uncertainty variables or document a defensible reason for excluding them.
This is a current research acceptance blocker.

## 7. Dependence and correlation

The present software baseline started with independent random variables because that is the
simplest transparent model. JCSS evidence shows that this is not automatically appropriate
for every physical variable; dimensions/cover may be correlated and steel properties within a
structure can be strongly correlated.

**Study decision:** independence must be justified variable-by-variable. If the adopted model
contains material dependence, production-batch dependence, correlated dimensions or common
model uncertainty, a correlation/copula model must be used and reported. Independence is not
a hidden default that can be presented as an observed fact.

## 8. Target reliability index

The software deliberately contains no default target beta. Target reliability depends on the
adopted reliability/consequence class, reference period and governing framework.

JCSS Part I gives one-year ULS target guidance as a function of consequences and relative
safety cost; its common moderate-consequence/normal-cost example is beta about 4.2 for one
year. For Eurocode reliability differentiation, the established central target for RC2/CC2 ULS
is beta about **3.8 for a 50-year reference period**. The European Commission JRC notes that
the second-generation EN 1990-1 retained the same central 50-year target as the first-generation
Eurocode calibration.

Useful source:

- European Commission JRC, *Second generation Eurocodes: basis of structural and geotechnical
design* / reliability background (2024), JRC material describing the retained central
`beta = 3.8` 50-year CC2 target:
  https://publications.jrc.ec.europa.eu/repository/handle/JRC139110

**Study decision:** do not automatically set beta_target = 3.8 merely because it is common.
The thesis should state the bridge consequence/reliability class and chosen reference period,
then adopt the corresponding target. Sensitivity to an alternative class may be useful for a
main bridge where higher consequences are arguable.

## 9. Recommended staged probability-model closure

Before the example configuration can be changed from `assumptions_confirmed=false`, close the
following in order:

1. select the production basis for concrete strength and document any local/test updating;
2. adopt the reinforcement yield/area model consistent with the selected B500 product basis;
3. replace percentage dimensional COVs with source/project-based dimensional deviations;
4. derive permanent-action uncertainty from its components;
5. choose and justify the road-traffic extreme/load-model uncertainty treatment;
6. decide whether JCSS resistance/load-effect model uncertainties are explicit variables;
7. establish the required dependence/correlation model;
8. demonstrate LHS/sample-size convergence;
9. state the adopted consequence/reliability class, reference period and target beta; and
10. only then train/validate the final ANN and perform the final RBDO run.

Until these decisions are documented and the numerical validation evidence passes, the
probabilistic research gate remains **VALIDATION PENDING** even though the complete software
pipeline is executable.
