# RC Single-Span Bridge Analysis & ANN

A focused engineering application for simply supported, single-span,
non-prestressed reinforced-concrete girder bridges.

The deterministic analysis/design engine is the primary product. ANN surrogate
modelling, reliability analysis and RBDO are downstream capabilities and must
not be trained on a deterministic engine whose verification gates are still
open.

## Design basis

One physical bridge model is shared by all code profiles:

`physical bridge -> code-specific traffic/combinations -> common structural solver -> code-specific RC design`

### Primary modern V1 route: BS EN

The primary route is explicitly the British-adopted first-generation Eurocode
bridge family used by this implementation:

- **BS EN 1990:2002+A1:2005** — basis and combinations;
- **BS EN 1991-2:2003** — bridge traffic actions;
- **BS EN 1992-2:2005** — concrete bridges, together with applicable
  BS EN 1992-1-1 provisions.

Internal modules may retain `eurocode` in their Python package names, but
user-facing provenance is BS EN. National Annex / Nationally Determined
Parameter choices are separate project inputs. Recommended Eurocode values are
not silently labelled as Nigerian National Annex values, and a UK National
Annex value is used only when the client, approving authority or project basis
adopts it.

### Secondary legacy route

BS 5400 / BD 37/01 is retained as a **legacy** profile for older projects and
comparison work. It is kept separate from BS EN: no automatic cube-to-cylinder
strength conversion and no borrowing of traffic, resistance or detailing
factors between the two routes.

The structural solver itself is code-neutral.

## V1 scope

V1 is intentionally narrow:

- simply supported, one span only;
- non-prestressed reinforced concrete;
- rectangular, T and I longitudinal girder profiles;
- composite reinforced-concrete deck;
- editable span, deck/carriageway width, girder count/spacing and sections;
- geometry-derived self-weight and permanent actions;
- essential three-stage unpropped construction analysis: precast girder,
  deck-construction and final hardened-composite stages;
- full-width grillage analysis with transverse distribution;
- BS EN 1991-2 LM1 traffic;
- legacy BD 37/01 HA, HB and HA+HB traffic;
- code-specific ULS/SLS combinations;
- flexure, shear, cracking and elastic-response deflection checks;
- practical reinforcement selection and bridge-specific detailing checks;
- calculation records carrying formula, substitution, result and reference;
- deterministic dataset / ANN / reliability / RBDO only after deterministic
  verification gates are accepted.

Continuous spans, prestressing, curved bridges, substructure/foundation design,
general local-deck design, staged continuity, changing supports, general
propping/removal and advanced creep/shrinkage redistribution are outside this
focused V1.

## Reference bridges

The repository includes:

- a 15 m rectangular-girder reference bridge with seven girders at 1.70 m
  spacing, 400 x 950 mm precast girders and a 75 + 175 mm deck build-up; and
- a 20 m haunched-I engineering benchmark used for additional geometry/design
  regressions.

Physical geometry is not adjusted merely to reproduce a target reinforcement
answer.

## Structural-analysis verification

The common solver/export path has genuine external STAAD evidence. The current
campaign is complete at:

- **83/83 external models**;
- **410,576/410,576 expected direct-global result fields**;
- **zero engineering comparison failures**.

The campaign covers construction stages, permanent-component response,
characteristic traffic, separately weighted frequent LM1 traffic and corrected
HB/HA+HB result completeness.

This verifies structural response for the exported reference model/load cases.
It does **not** establish that a traffic rule, National Annex choice, resistance
formula, crack limit, fatigue category or reinforcement drawing is correct.
Those are separate verification gates.

See:

- `docs/STAAD_EXTERNAL_VERIFICATION_2026-09-25.md`;
- `docs/STAAD_WEIGHTED_FREQUENT_EXTERNAL_VERIFICATION_2026-09-25.md`;
- `docs/FULL_BRIDGE_STAAD_MODEL.md`.

## BS EN 1991-2 LM1 status

The primary BS EN route uses a response-specific signed influence-surface search
rather than the historical whole-lane UDL approximation. For each fixed signed
response it:

1. searches complete tandem-system position vectors;
2. evaluates unit-pressure carriageway cells;
3. retains only UDL cells that increase the selected response; and
4. re-solves the governing physical tandem + selected-UDL case.

Source-pinned tests cover the reference notional-lane arrangement, both lane
numberings, both remaining-area edges, tandem axle/wheel geometry and
characteristic resultants.

### Search convergence is still an acceptance gate

A dedicated exhaustive convergence audit now halves the longitudinal tandem
step and compares girder moment, shear, torsion and deflection envelopes. The
adopted verification criterion is a maximum relative envelope change of 5%.

The first recorded refinement **2.4 m -> 1.2 m did not converge**: the maximum
change was **13.4036%**, governed by shear on girder 4. The tolerance was not
relaxed. The next refinement is **1.2 m -> 0.6 m**.

See `docs/BS_EN_LM1_CONVERGENCE_AUDIT.md`.

## BS EN frequent SLS

The frequent-LM1 correction is implemented and externally checked. Tandem and
UDL components can be weighted separately before searching the governing
placement. The source-reference values used in the verification campaign are
0.75 for the tandem system and 0.40 for the UDL; these are verification values,
not an automatic Nigerian National Annex selection.

The weighted external STAAD campaign retained 17 frequent cases and matched
**46,189/46,189** expected result fields with zero engineering comparison
failures.

## BS EN concrete design verification

The primary route currently has independent/source-pinned checks for:

- flexural resistance against a published worked beam example;
- shear resistance against the JRC concrete-bridge example;
- recommended minimum longitudinal reinforcement expression;
- minimum shear reinforcement and link-spacing limits;
- crack-width calculation against a published example, with the production
  close-spacing path calling the same pinned formula;
- straight-bar anchorage against a worked example;
- EC2 tension-shift rule;
- reinforcement fatigue against the JRC bridge example.

The production design path also contains discrete cage selection, actual cage
centroid/effective-depth rechecks, station-wise steel-demand zoning,
curtailment, construction-stage steel stress, lap/splice zoning, local
bearing/end-zone congestion and doubly reinforced cage checks.

Project-specific values that cannot be inferred safely remain explicit,
including National Annex/NDP choices, crack/deflection criteria, fatigue
category/resistance data, construction-stage stress limits and local bearing
geometry.

## Legacy BS 5400 / BD 37 status

The legacy route includes HA, HB and HA+HB loading and primary combinations
1-3. Official archived BD 37/01 values are source-pinned, and the external
STAAD campaign includes the resulting traffic responses.

The owner-supplied Ragana River Bridge calculation is retained as a narrow
legacy BS design benchmark. Its shear calculation is reproduced. Its printed
crack calculation is internally inconsistent and is not used as acceptance
evidence. Legacy doubly reinforced flexure remains a separate verification item
and cannot alter the BS EN implementation.

## Reinforcement synthesis

The program keeps these concepts distinct:

`A_s,ULS -> code minimum -> candidate cages -> actual d -> ULS/SLS recheck -> bridge detailing -> recommended cage`

A cage is not promoted solely because its steel area exceeds the continuous ULS
requirement. See `docs/REINFORCEMENT_SYNTHESIS.md` and
`docs/DETAILING_STAGE_D.md`.

## Verification rule

A capability is never labelled verified merely because the software runs or a
unit test passes. The acceptance matrix separates:

- internal regression evidence;
- independent source/worked-example checks;
- external structural-software comparisons; and
- final acceptance.

The primary BS EN route and the secondary legacy route are tracked separately,
so unfinished legacy work does not masquerade as a BS EN blocker and unfinished
BS EN work cannot be hidden by a successful legacy benchmark.

See `src/rc_single_span/verification/acceptance.py` and
`docs/CODE_LOADING_INDEPENDENT_AUDIT.md`.

## Current release position

**Deterministic V1 remains NO-GO for final engineering release.**

The common structural-response verification is closed, and several BS EN
loading/resistance/serviceability equations have independent evidence. The main
remaining primary-route acceptance work is:

1. close the 15 m LM1 search-resolution convergence audit without widening the
   5% criterion merely to obtain a pass;
2. record the actual project/authority National Annex or NDP choices;
3. close the reference-girder serviceability/deflection acceptance package;
4. close the complete BS EN reinforcement/detailing reference-girder hand-check
   package; and
5. review a complete calculation report against the engine outputs and sources.

Only after these deterministic gates are accepted should production dataset
generation, ANN surrogate validation, reliability analysis and RBDO be treated
as the next phase.
