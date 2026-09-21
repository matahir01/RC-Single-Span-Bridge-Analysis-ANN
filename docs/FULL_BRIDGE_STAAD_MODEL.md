# Full seven-girder STAAD model

The full-bridge verification campaign replaces the earlier interpretation that
21 isolated girder-stage models could represent the complete bridge. Those
files remain useful line-girder checks, but they do not capture transverse load
distribution or traffic torsion.

## Delivered structural systems

The new campaign contains three coordinated construction systems:

1. **Precast stage:** all seven physical girder lines and all 14 bearings in one
   model. No transverse stiffness is invented because no diaphragm properties
   are supplied and the deck has not hardened.
2. **Wet-deck stage:** all seven girder lines carry wet in-situ concrete on the
   construction-stage section. The reference false slab is non-composite.
3. **Final composite stage:** the seven longitudinal girders are connected by
   transverse deck-strip members across the full 11 m deck, including edge
   overhangs.

Every retained LM1, HA, HB and HA+HB traffic placement is a complete connected
final-composite grillage. It is not an isolated-girder model.

## Why there is no single all-stage `LOAD COMB`

The bridge stiffness changes when the slab hardens. Applying precast self-weight
or wet concrete to the final-composite model would calculate those actions with
the wrong stiffness and could introduce transverse redistribution that did not
exist at load application.

The bundle therefore separates permanent actions by both construction stage and
permanent category. `combination_application_matrix.csv` and `.json` specify how
to factor and superpose the returned **responses** from the stage-correct models.
This preserves the load-time stiffness and also permits the separate BS 5400
factors for structural dead load, surfacing and other superimposed actions.

## Traffic search coverage

The reference export defaults are:

| Action | Search spacing |
|---|---:|
| EN 1991-2 LM1 tandem leads | 1.2 m |
| BD 37/01 HA KEL | 1.0 m |
| BD 37/01 HB longitudinal / transverse | 1.0 m / 0.5 m |
| BD 37/01 HA+HB longitudinal / transverse / HA KEL | 2.0 m / 1.0 m / 2.0 m |

All candidates are solved on connected full-width grillages. The exported set
retains every case governing moment, shear, torsion or deflection for at least
one of the seven physical girders. Search counts, exhaustiveness flags and every
retained-case purpose are recorded in `bundle_index.json`.

## Generate the bundle

From the repository root, choose an absent or empty output directory:

```text
python examples/export_full_bridge_staad_bundle.py \
  --elastic-modulus-mpa <VALUE> \
  --elastic-modulus-basis "<SOURCE OR DERIVATION>" \
  --psi1-traffic <VALUE> \
  --psi2-traffic <VALUE> \
  --output-dir generated_full_bridge_staad_bundle
```

The Eurocode ULS factors and every search spacing are also exposed as command
line options. The manual **Full seven-girder STAAD bundle** GitHub Actions
workflow provides the principal modulus and Eurocode factor inputs explicitly.

## Verification status

The internal solver checks equilibrium and writes expected results for every
file, but generation is not independent verification. The bundle remains
externally pending until genuine STAAD output is returned, sign conventions are
confirmed, and the comparison templates are reviewed.
