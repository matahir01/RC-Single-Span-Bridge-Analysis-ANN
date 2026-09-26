# Legacy BS 5400 / BD 37 deterministic V1 closure record

Date: 26 September 2026

## Decision

The focused **legacy BS 5400 / BD 37 deterministic software capability** is
accepted for V1 within the documented scope below.

This is a software-verification/release decision. It is **not** approval of a
particular bridge, calculation package, reinforcement drawing or construction
work. BS 5400-4:1990 is a withdrawn legacy standard and the path is intended for
projects, owners or authorities that explicitly require that historical basis.
It must remain isolated from the BS EN route.

A real project can still be incomplete or fail. HB units, project action model,
material grades, crack/deflection limits, fatigue vehicle/detail category,
bearing geometry, construction-stage stress limits, splice rules and other
project-specific choices remain explicit inputs. The program must continue to
report unresolved/not-ready results when such information is absent or a check
fails.

## Accepted focused scope

- simply supported single-span non-prestressed RC girder bridges supported by
  the common V1 physical model;
- rectangular, T and I longitudinal girder profiles supported by V1;
- composite RC deck and the documented three-stage unpropped construction path;
- common full-width grillage structural analysis;
- BD 37/01 HA, HB and HA+HB loading and coexistence rules implemented by the
  focused traffic model;
- legacy primary ULS/SLS combinations 1-3 for the actions actually modelled;
- BS 5400 flexure, shear and crack-width logic used by the legacy design path;
- elastic-response deflection with explicit project acceptance criterion;
- discrete longitudinal/shear reinforcement selection and source-pinned legacy
  detailing limits;
- station-wise reinforcement zoning and the advanced Stage D infrastructure
  when its explicit legacy inputs are supplied;
- traceable calculation records with an explicit code basis.

Combinations 4-5 are not silently approximated. They remain outside the focused
legacy V1 scope until the corresponding secondary/accidental actions and project
authority basis are explicitly implemented.

## Structural-response evidence

The common solver/export path has genuine external STAAD.Pro evidence for the
reference model family:

- 83/83 external models returned;
- 410,576/410,576 expected direct-global result fields present;
- zero engineering comparison failures;
- HA, HB and HA+HB traffic models included;
- the corrected 13 HB + 15 HA+HB rerun contains every expected output field.

This accepts the structural-response capability for the verified V1 model
family. It does not by itself establish that a legacy traffic rule, resistance
formula or detailing choice is correct.

## BD 37/01 loading and combinations

Official archived BD 37/01 evidence is pinned in regression tests for the
focused legacy traffic path, including:

- notional-lane treatment used by the implementation;
- HA UDL and KEL mechanics;
- HB vehicle geometry and configured unit count;
- HA+HB coexistence, occupied-lane treatment and exclusion-zone mechanics;
- primary permanent and traffic factors used for combinations 1-3.

The resulting reference-model traffic responses are included in the completed
external STAAD campaign.

Authority-specific HB units and any action outside the implemented focused model
remain explicit. The legacy route does not borrow BS EN traffic or combination
factors.

## BS 5400 resistance evidence

The owner-supplied Ragana River Bridge calculation remains a narrow independent
legacy benchmark.

For shear, with the report's V = 835 kN, average web width 329 mm, d = 1349 mm,
As = 12,861 mm2, fcu = 35 MPa and fyv = 460 MPa, the production legacy kernel
reproduces the report's rounded design shear stress, concrete contribution and
required Asv/s.

The separately checked doubly reinforced path reproduces the Ragana beam basis
at M = 4174 kNm, including approximately 3148 kNm limiting concrete moment,
2388 mm2 compression steel and 9751 mm2 total tension steel with the stated
legacy reinforcement design stresses.

These legacy assumptions remain isolated from the BS EN resistance path.

## BS 5400 crack-width evidence

The inconsistent crack calculation printed in the Ragana document is still
excluded from acceptance evidence.

Instead, the production BS 5400-4 equations 24/25 implementation is pinned to a
separate published worked bridge calculation. For the sagging SLS example with
h = 400 mm, b = 1000 mm, d = 342 mm, As = 1340 mm2/m, Es = 200 GPa, modified
Ec = 14 GPa, Mg = 25 kNm/m, Mq = 45 kNm/m, T16 at 150 mm and 50 mm nominal
cover, the engine reproduces:

- compression depth approximately 96.9 mm;
- controlling surface distance a_cr approximately 87 mm; and
- crack width approximately 0.22 mm.

The allowable crack width remains a project/code-basis input.

## Source-pinned legacy reinforcement detailing

The focused detailing path now has direct regression evidence for the BS 5400-4
rules used by the software:

- minimum main tension steel: 0.15% b_a d for Grade 460 and 0.25% b_a d for
  Grade 250;
- maximum main tension/compression reinforcement: 4% gross concrete area;
- beam side-face reinforcement where side-face depth exceeds 600 mm: at least
  0.05% b_t d on each face;
- minimum clear spacing: maximum aggregate size + 5 mm;
- maximum tension-bar spacing: 300 mm, with crack control checked separately;
- maximum beam-link spacing: 0.75d.

Unknown reinforcement grades are not silently remapped: the project must supply
an adopted minimum-main-steel ratio when the built-in legacy Grade 250/460 rule
does not apply.

## Advanced Stage D boundary

The legacy Stage D path contains the mechanics for station-wise cage zoning,
termination, laps, construction-stage steel stress, bearing/end-zone congestion,
doubly reinforced SLS and fatigue stress-range assessment.

Two legacy items are intentionally **not invented** by the software:

1. a verified project fatigue vehicle/model/detail classification; and
2. a verified legacy tension-shift/curtailment length/rule for the project basis.

`run_bs5400_advanced_stage_d` requires these explicitly before the corresponding
advanced checks can be completed. This conservative refusal to fabricate a
legacy default is part of the accepted software boundary, not an unresolved
engine defect.

## Acceptance interpretation

The legacy BS 5400 / BD 37 software path is therefore **GO for the focused V1
scope documented above**.

That means the deterministic engine can be used as a legacy-code software path
when the project/authority explicitly adopts the relevant BS 5400 / BD 37 basis
and supplies all required project inputs. It does not mean:

- BS 5400 is being recommended over current standards;
- combinations/actions outside the implemented scope have been checked;
- a project-specific bridge automatically passes;
- a reinforcement drawing is approved; or
- independent engineering review is no longer required.

The modern BS EN and legacy BS 5400 / BD 37 acceptance gates remain separate so
future changes to one route cannot silently alter the other.
