# Stage 8 construction-stage STAAD bundle

This directory contains the first generated STAAD verification evidence for the
15 m reference bridge.

## Contents

- 21 loaded `.std` models: seven girders by three construction stages;
- one expected-results CSV and one blank external-results template per model;
- one provenance manifest per model;
- `internal_crosscheck.csv`; and
- `bundle_index.json`.

The stages are:

1. precast girder plus false-slab self-weight on the precast-girder section;
2. wet in-situ deck weight on the construction-stage section; and
3. surfacing, barriers and services on the hardened composite section.

The reference elastic modulus is 31,000 MPa. Its code basis and the exact source
commit are recorded in `bundle_index.json`. The surfacing, barrier and service
loads are explicitly labelled verification-benchmark assumptions, not as-built
data.

## Which models to open first

Start with these two representative files:

- `girder_01/precast_girder/g01_precast_girder.std` for an exterior-girder
  construction response; and
- `girder_04/superimposed/g04_superimposed.std` for an interior final-composite
  response.

Then run all 21 models for the complete evidence set. Copy genuine STAAD results
into each matching `_external_results_template.csv`; do not copy the internal
expected values into those templates.

Generation and internal agreement do not constitute independent verification.
The bundle remains externally pending until STAAD outputs are returned and
compared.
