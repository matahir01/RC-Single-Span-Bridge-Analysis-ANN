# Stage 8 STAAD verification workflow

The repository can prepare the construction-stage verification models and result
templates needed for independent STAAD.Pro comparison without rebuilding the
bridge by hand.

## What the bundle contains

For every girder and every construction stage the bundle writes:

- the exact STAAD `.std` model generated from the solved verification model;
- a manifest describing model provenance, section properties, restraints and
  comparison scope;
- the internal expected-result CSV;
- an empty external-result return template for genuine STAAD results.

The bundle also contains:

- `bundle_index.json`, which records the bridge, elastic modulus and its stated
  basis, repository SHA, stage-model inventory and external-verification status;
- `internal_crosscheck.csv`, which records the analytical construction-stage
  result against the separate Stage-8 beam-FE implementation.

The internal cross-check must pass before the bundle is written. This is still
not independent verification: the bundle index remains
`external_verification_status = "pending"` until real STAAD results are run and
compared.

## Elastic modulus is explicit

The 15 m reference project intentionally does not invent an elastic modulus.
Every export therefore requires both:

1. the elastic modulus in MPa; and
2. a traceable text basis/source for that value.

If the modulus is derived from a design standard rather than project test data,
record that derivation/basis explicitly in the export input and later
calculation report.

## Export locally

From the repository root:

```text
python examples/export_reference_staad_packages.py \
  --elastic-modulus-mpa <VALUE> \
  --elastic-modulus-basis "<SOURCE OR DERIVATION>" \
  --output-dir stage8_staad_bundle
```

`--repository-sha` is optional locally. In GitHub Actions it is populated from
the checked-out commit automatically.

## Export from GitHub Actions

Open **Actions → Stage 8 STAAD verification bundle → Run workflow** and supply:

- `elastic_modulus_mpa`;
- `elastic_modulus_basis`.

After the run completes, download the
`stage8-staad-verification-bundle` artifact.

## Committed reference bundle

The first generated reference bundle is committed at `stage8_staad_bundle/`.
It was generated from source commit
`28a4f7e3d6af3dd6108b355a642df8f6a8f48dc5` using:

- concrete elastic modulus `Ecm = 31,000 MPa`, from EN 1992-1-1:2004+A1:2014
  Table 3.1 for normal-weight C25/30 concrete;
- 80 mm carriageway surfacing at 22 kN/m3;
- left and right safety barriers at 10 kN/m each; and
- left and right service lines at 2 kN/m each.

The modulus and superimposed permanent actions are verification-benchmark
assumptions, not project test or as-built data. Replace them with approved
project values before using the models for a project-specific design decision.
The bundle contains seven girders by three loaded stages, for 21 `.std` files.
Every internal analytical-versus-beam-FE row passes, while the external status
remains `pending` until genuine STAAD results are returned and compared.

## External comparison sequence

For each selected `.std` model:

1. open and analyze it in STAAD.Pro without changing the exported structural
   model or loads;
2. obtain support reactions, joint vertical displacements and global
   member-end `FZ`, `MX`, `MY`;
3. populate the matching external-results template;
4. retain the STAAD output/report as source evidence;
5. compare the returned values using the repository comparison machinery.

The first genuine comparison must also confirm STAAD's reported member-end sign
convention. No acceptance-matrix item should be promoted merely because the
export files were generated.

## Current verification boundary

The prepared construction-stage models cover the production V1 staged mechanics:

- precast girder + precast false-slab weight on the construction-stage girder;
- wet in-situ deck concrete on the pre-composite construction stiffness;
- final superimposed permanent actions on the hardened composite girder.

The false slab remains non-composite unless the project geometry explicitly
states otherwise. Traffic verification remains a separate full-width grillage
campaign.
