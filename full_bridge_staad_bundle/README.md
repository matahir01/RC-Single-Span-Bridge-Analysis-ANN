# Full seven-girder STAAD verification bundle

This bundle contains coordinated full-width models for the 15 m reference
bridge. Every structural model contains all seven physical longitudinal girder
lines. The final-composite and traffic models also contain transverse deck
members and therefore capture transverse distribution and torsion.

## Inventory

- 3 complete construction-stage models;
- 4 category-separated permanent-action models;
- 60 retained governing traffic models across LM1, HA, HB and HA+HB;
- 22 Eurocode/BS 5400 combination rules; and
- 324 explicit rule-by-traffic-case applications.

Each model directory contains a `.std` file, provenance manifest, internal
expected-results CSV and empty STAAD-results return template.

## Structural-stage rule

The precast and wet-deck files contain all seven girders in one coordinated
model, but do not invent transverse stiffness before the in-situ slab hardens.
No diaphragm properties are present in the project input. The final composite
stage activates the connected orthogonal deck grillage.

Early permanent actions must not be reapplied to the final-composite stiffness.
For that reason `combination_application_matrix.csv` and `.json` specify
response superposition across the stage-correct source models. A single
same-stiffness STAAD `LOAD COMB` would produce the wrong construction-stage
deflection and can also misrepresent locked-in early-stage response.

`combination_envelopes.csv` contains the internal per-girder force envelopes for
the implemented Eurocode and BS 5400 rules. It is a comparison target, not a
substitute for genuine STAAD results.

## External status

Generation and internal equilibrium checks are complete. Independent STAAD
verification remains **pending** until the `.std` files are run in STAAD.Pro,
the matching return templates are populated from genuine output, and the
results are compared. Do not copy internal expected values into return files.
