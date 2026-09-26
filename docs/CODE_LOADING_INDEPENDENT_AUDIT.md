# Code loading independent audit — updated 26 September 2026

## Code basis and scope

The primary modern route is the British-adopted Eurocode family: **BS EN
1990:2002+A1:2005**, **BS EN 1991-2:2003** and **BS EN 1992-2:2005**. The
internal package name remains `eurocode` where necessary, but design provenance
is BS EN. The legacy BS 5400 / BD 37 route remains separate and is not allowed
to donate factors or material definitions to the BS EN path.

Primary external loading source: European Commission Joint Research Centre,
*Bridge Design to Eurocodes Worked Examples*, Chapter 3, Tables 3.6 and 3.8.
The source's recommended factors are verification values; they do not establish
a Nigerian National Annex. Nationally Determined Parameters and any authority
adoption remain explicit project inputs.

For the 15 m reference bridge's 7 m carriageway, two 3 m notional lanes and a
1 m remaining area give 1000 kN in the two complete characteristic tandem
systems and 555 kN of full-length UDL at the JRC characteristic magnitudes. The
source-pinned regression suite also checks both notional-lane numberings, both
possible remaining-area edges, 1.2 m tandem axle spacing and 2.0 m transverse
wheel spacing.

## BS EN LM1 favourable-region search

BS EN 1991-2 requires the UDL to be applied only on adverse portions of the
relevant influence surface. The production BS EN route no longer uses the
historical whole-lane UDL approximation. It now builds a fixed common-grillage
plan grid, solves unit-pressure cells once, searches the complete tandem
position vectors, and for each signed fixed response retains only UDL cells
that increase that response. Governing stored cases are then re-solved as
physical tandem plus selected-UDL load cases.

The search is response-specific: member-end bending, shear and torsion are
checked for both signs and deflection is sampled along each longitudinal member.
Station-wise moment demand used by reinforcement zoning is retained separately.

### Numerical convergence

Search resolution is a numerical parameter, not a code constant. The repository
therefore has a dedicated convergence audit that requires:

- exhaustive tandem combinations at every refinement;
- halving of the tandem longitudinal step;
- comparison of girder moment, shear, torsion and deflection envelopes; and
- maximum relative change no greater than the adopted 5% verification
  criterion.

The first recorded refinement, **2.4 m -> 1.2 m**, was deliberately rejected:
maximum relative change was **13.4036%**, governed by shear on girder 4. The
criterion was not widened. A finer **1.2 m -> 0.6 m** exhaustive audit is the
next acceptance check. See `docs/BS_EN_LM1_CONVERGENCE_AUDIT.md`.

## BS EN frequent SLS — corrected and externally checked

JRC Table 3.8 gives different recommended frequent factors for LM1's tandem
system and UDL: 0.75 and 0.40 respectively. Applying one factor to an already
combined LM1 envelope is therefore not a valid substitute for a separately
weighted search because the governing placement can change.

The current engine addresses this explicitly:

- `EurocodeServiceabilityFactors` accepts separate tandem and UDL frequent
  factors;
- scalar `frequent_sls` rejects distinct component factors rather than silently
  applying one number;
- the LM1 search can weight tandem and UDL components before the placement
  search;
- project combinations accept a separately searched frequent-LM1 result; and
- the full-width STAAD exporter maps the frequent combination to the weighted
  traffic cases at factor 1.0 instead of rescaling a characteristic envelope.

This correction has genuine external structural-response evidence. A weighted
campaign using tandem factor 0.75, UDL factor 0.40 and quasi-permanent traffic
factor 0.0 retained 17 frequent cases. Genuine STAAD returns matched all
**46,189/46,189** expected direct-global result fields with zero engineering
comparison failures.

That closes the weighted frequent-LM1 **solver-response** comparison. It does
not choose the project's National Annex or add actions that are outside the V1
action model.

## BS EN 1990 combinations

The primary combination module now identifies its outputs as BS EN 1990. The
JRC road-bridge values used for verification are pinned numerically, including
recommended persistent ULS factors for unfavourable permanent action and road
traffic. Favourable and unfavourable permanent response can be supplied
separately through `persistent_uls_split_permanent`; a stabilising response
keeps its physical sign rather than being converted to a positive magnitude.

For the focused simply supported gravity-girder V1 path, the permanent sagging
and positive shear envelopes are treated as unfavourable gravity effects. The
split helper exists so this V1 simplification cannot become a hidden general
combination rule.

The applicable National Annex/project NDP basis remains explicit. Wind,
thermal, accidental and other secondary action combinations are not claimed as
implemented merely because the primary gravity/traffic combination arithmetic
is source-pinned.

## BS EN concrete design source checks

The following independent checks are now attached to the primary route:

- **Flexure:** Concrete Centre published beam example; with the example's
  explicit `alpha_cc = 0.85`, the layered flexure path reproduces the published
  lever arm and required tension steel to rounding.
- **Shear:** JRC concrete-bridge worked example using `fck = 35 MPa`,
  `d = 360 mm`, `bw = 1000 mm`, `As = 1848 mm²` and `VEd = 235 kN`; the engine
  reproduces the concrete resistance and required vertical-link demand to the
  published basis.
- **Minimum longitudinal steel:** the JRC recommended
  `max(0.26 fctm/fyk, 0.0013) bt d` expression is pinned directly. Coefficients
  remain overrideable where National Annex choice applies.
- **Shear detailing:** recommended minimum link ratio and explicit link-spacing
  limits are source-pinned; they are not mixed with the legacy BS 5400 rules.
- **Cracking:** a published EC2 crack-width example gives approximately
  0.184 mm; the production close-spacing crack check now calls the same
  source-pinned formula used by that benchmark.
- **Anchorage:** the BS EN/EC2 straight-bar anchorage calculation has a
  published worked-example regression.
- **Tension shift:** the EC2 truss-model expression
  `a_l = z(cot(theta)-cot(alpha))/2` is source-pinned; support anchorage and
  continuation remain separate explicit detailing inputs.
- **Fatigue:** the reinforcement fatigue calculation is checked against the JRC
  bridge example, while project fatigue category/resistance inputs remain
  explicit.

These examples verify individual equations and implementation paths. They do
not by themselves certify a complete project girder or drawing.

## Legacy BS 5400 / BD 37 evidence

The official archived Highways Agency *BD 37/01 CR01*, Appendix A, remains the
primary legacy traffic source. Tests pin the 7 m two-lane split, HA UDL/KEL,
short-span lane factors, HB geometry and HA+HB coexistence mechanics including
occupied-lane treatment and exclusion zones. The corrected external STAAD
rerun also covers the resulting HB and HA+HB structural responses.

The owner-supplied Ragana River Bridge calculation provides a useful narrow
legacy RC benchmark. With its stated `V = 835 kN`, average web width 329 mm,
`d = 1349 mm`, `As = 12861 mm²`, `fcu = 35 MPa` and `fyv = 460 MPa`, the legacy
shear kernel reproduces the report's rounded shear stress, concrete contribution
and required `Asv/s`.

The Ragana cracking calculation remains unsuitable as acceptance evidence: its
printed neutral axis does not satisfy its own displayed transformed-section
quadratic. Its doubly reinforced flexure also uses a legacy compression-steel
coefficient that must be checked against an authoritative BS 5400 source before
changing the software. No such legacy assumption is imported into the primary
BS EN route.

## Structural solver evidence

The current external STAAD evidence set is complete at **83/83 models** and
**410,576/410,576 expected fields**, with zero engineering comparison failures.
The campaign includes construction stages, permanent components, characteristic
traffic, separately weighted frequent LM1 traffic, and corrected HB/HA+HB
output completeness.

This is evidence for structural response of the exported model/load cases. It
is not evidence that a selected code factor, NDP, crack limit, fatigue category
or reinforcement drawing is correct.

## Remaining BS EN acceptance work

1. Finish the 15 m LM1 search-resolution convergence audit without relaxing the
   5% criterion; refine further if the 0.6 m result still has not stabilised.
2. Record the project/authority National Annex or NDP choices instead of
   labelling recommended Eurocode values as Nigerian defaults.
3. Close the reference-girder **serviceability** package, especially the
   selected deflection criterion/combination, without inventing a universal
   road-bridge limit.
4. Close the BS EN **detailing** package as one traceable reference-girder hand
   check: selected cage, anchorage, tension shift/curtailment, fatigue,
   construction-stage stress, laps and bearing/end-zone congestion.
5. Review one complete calculation report against the engine outputs and source
   references before promoting reporting to accepted.

The primary BS EN deterministic path therefore remains **NO-GO for final
engineering release** while these acceptance items remain open. The legacy BS
5400 route can continue to be improved independently without blocking closure of
the primary BS EN V1 route.
