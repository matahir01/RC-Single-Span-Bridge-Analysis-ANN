# RC Single-Span Bridge Analysis & ANN

A focused engineering application for simply supported, single-span, non-prestressed reinforced-concrete girder bridges.

The deterministic bridge-analysis and design engine is the primary product. ANN surrogate modelling, reliability analysis and RBDO are advanced capabilities built on top of verified deterministic results; the application is not branded or architected as an MSc-only tool.

## Design philosophy

One physical bridge model is shared by all code profiles.

Physical bridge -> code-specific traffic and combinations -> common structural solver -> code-specific RC design.

Eurocode and BS 5400 are allowed to differ only where the standards actually differ: traffic generation, combination rules, material interpretation, resistance/serviceability checks and detailing provisions.

The structural solver itself is code-neutral.

No automatic BS cube-strength to Eurocode cylinder-strength conversion is permitted. If a project is analysed to both standards, the applicable material strengths must be supplied explicitly and remain traceable.

## V1 scope

The target V1 application is intentionally narrow:

- simply supported, one span only;
- non-prestressed reinforced concrete;
- longitudinal rectangular, T or I girder profiles;
- composite reinforced-concrete deck;
- editable span, deck/carriageway width, girder count/spacing and physical sections;
- geometry-derived self-weight and permanent actions;
- targeted construction-stage analysis for precast girder, deck-construction and final-composite states;
- full-width grillage analysis with transverse distribution;
- Eurocode EN 1990 / EN 1991-2 / EN 1992-2 profile;
- BS 5400 / BD 37 profile;
- common-grillage traffic adapters for Eurocode LM1 and BD 37/01 HA/HB;
- flexure, shear, cracking and deflection checks;
- practical reinforcement selection and constructability checks;
- calculation reports with formula, substitution, result and reference;
- verification evidence kept separate for structural analysis, code loading and RC design;
- deterministic dataset export, ANN, reliability and RBDO only after deterministic gates are accepted.

## Explicitly outside V1

Continuous spans, prestressing, curved bridges, substructure/foundation design, general local-deck design, arbitrary bridge systems and unrelated advanced features are excluded. The V1 construction-stage scope is deliberately limited to the essential unpropped single-span sequence with unchanged supports: precast girder stage, deck-construction stage, and final hardened-composite stage. General propping/removal, changing support systems, staged continuity, creep/shrinkage redistribution and advanced time-dependent construction modelling remain outside V1. They belong in the broader RC-Bridge-Analysis-ANN project if pursued later.

## Reliability rule

A capability is never labelled verified merely because the software runs.

Structural analysis is checked against independent structural software such as STAAD using the same physical model and loads. Code loading and combinations are checked against published/code-reference examples and hand calculations. RC design equations are checked independently against worked examples and hand calculations. Internal unit tests protect implementation consistency but do not replace independent engineering verification.

## Foundation status

The repository currently contains the first common foundation:

- validated single-span physical bridge model;
- explicit Eurocode and BS 5400 material requirements;
- rectangular/T/I girder definitions;
- deck build-up with explicit composite participation;
- longitudinal reinforcement representation;
- code-neutral load-effect container;
- exact simple-span UDL and segmented-load mechanics migrated from the verified parent project;
- CI, linting and regression tests;
- a 15 m reference bridge with 7 girders at 1.70 m spacing, 400 x 950 mm precast girders, 75 + 175 mm deck build-up and four layers of four Y32 bars.

This is not yet a completed design application. The common full-width grillage, permanent-action/construction-stage backbone, Eurocode LM1, BD 37/01 HA/HB nominal traffic, BD 37/01 HA+HB coexistence/application mechanics, code-specific ULS/SLS combinations, and the focused EC2/BS 5400 longitudinal-girder design layer are now implemented. The practical reinforcement/constructability layer is now implemented for the focused V1 girder path. The next milestone is the independent verification and calculation-reporting campaign.

## Migration policy

Stable code is migrated selectively from matahir01/RC-Bridge-Analysis-ANN. General and continuous-span features are not copied merely because they already exist. Every migrated component must have relevant regression tests in this repository and fit the single-span architecture.

## Development sequence

1. Common physical model and simple-span mechanics.
2. Common full-width grillage, permanent actions and essential three-stage construction analysis.
3. Eurocode LM1 adapter and convergence-controlled search. **Implemented.**
4. BS 5400 / BD 37/01 HA and HB adapters on the same grillage. **Implemented, including nominal HA-alone, HB-alone and HA+HB coexistence/application under 6.4.2.**
5. Code-specific ULS/SLS combinations. **Implemented for Eurocode persistent ULS plus characteristic/frequent/quasi-permanent SLS, and for BS 5400 primary highway combinations 1-3 with separate structural-dead, surfacing and other-superimposed permanent factors and component-wise HA/HB/HA+HB governing envelopes.** BS combinations 4-5 remain outside the current primary-action set because they require secondary/accidental actions not yet modelled.
6. EC2 and BS 5400 flexure/shear/cracking/deflection. **Implemented for the focused single-span longitudinal-girder path.** ULS flexure and shear consume the actual code-specific combined effects; cracking uses the actual layered composite section with non-participating false-slab gaps retained; deflection combines stage-aware permanent displacement with the common-grillage traffic displacement at the same traffic-governing station. A final all-case combined-deflection re-search remains an explicit verification item rather than a hidden approximation. Out-of-scope singly-reinforced flexure states are reported per girder instead of aborting the whole bridge run.
7. Practical reinforcement and constructability checks. **Implemented for the focused single-span girder path.** Required longitudinal steel is solved from the layered ULS section; discrete unbundled bar and closed-link arrangements are selected against explicit area/spacing limits; provided cages can be audited from stored layer counts/diameters without inventing missing vertical spacing. EC2 and BS detailing limits remain separate, and BS Grade 410 is never silently remapped to Grade 460—the adopted minimum-main-steel ratio must be supplied explicitly when the legacy default does not apply. Anchorage/lap geometry, fatigue-specific detailing zones and drawing-level local congestion remain explicit later verification/detail-drawing items.
8. Independent verification campaign and calculation reports. **In progress:** the reproducible reference runner, explicit acceptance matrix, external-comparison tolerances, all-case combined-deflection re-search, structured formula/substitution/result/reference reporting, exact-common-grillage STAAD verification export, global FZ/MX/MY member-result mapping, and the dedicated construction/permanent-action verification suite are implemented. The complete STAAD campaign now contains all seven physical girders in the precast, wet-deck and final-composite systems; the final system includes transverse deck members. Governing EN 1991-2 LM1 and BD 37/01 HA, HB and HA+HB placements are exported as connected full-width grillages. Permanent actions are also separated by load-time stage and category, with explicit Eurocode and BS 5400 response-superposition matrices so early loads are not incorrectly reapplied to final-composite stiffness. See `docs/FULL_BRIDGE_STAAD_MODEL.md` and `docs/STAAD_VERIFICATION.md`. Internal agreement remains internal evidence only: genuine STAAD returns and sign-convention review are still required before structural-analysis evidence is promoted.
9. Deterministic dataset generation.
10. ANN surrogate validation, reliability analysis and RBDO.

The first generated construction-stage evidence bundle is committed under
`stage8_staad_bundle/`. It contains 21 loaded STAAD `.std` models (seven girders
by three stages), expected-result tables, empty STAAD-return templates and
provenance manifests. Its internal cross-check is passing; external STAAD
verification remains pending.

The committed bridge-level reference snapshot is under
`full_bridge_staad_bundle/`. Unlike the original 21 supplementary line-girder
files, its stage systems contain all seven girders and its final/traffic models
use the connected transverse deck grillage. The repository keeps all 67 STAAD
`.std` models and their manifests browsable, together with the bundle index and
Eurocode/BS 5400 combination matrices. The complete generated evidence tree
(including internal expected-result tables and empty external-return templates)
is retained losslessly as `full-seven-girder-staad-bundle.zip` with a committed
SHA-256 checksum. The production reference search retained 18 LM1, 14 HA, 13 HB
and 15 HA+HB governing cases, giving 60 full-width traffic models and 324
rule-by-case combination applications. External STAAD verification remains
pending.
