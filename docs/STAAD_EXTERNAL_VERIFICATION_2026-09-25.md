# STAAD full-width verification — external comparison

Date: 25 September 2026
Repository: `matahir01/RC-Single-Span-Bridge-Analysis-ANN`
Reference: 15 m single-span, seven-girder bridge

## Result

> **Follow-up evidence note:** the later weighted-campaign review found that the
> same HB and HA+HB STAAD input family can truncate selected four-digit member
> IDs in overlong `PRINT MEMBER FORCES GLOBAL LIST` commands. The numerical
> agreement recorded below remains useful, but the HB/HA+HB *field-completeness*
> claim is under review until those 28 models are rerun with the corrected
> character-length chunking. See
> `STAAD_WEIGHTED_FREQUENT_EXTERNAL_VERIFICATION_2026-09-25.md`.

**PASS for the structural-response comparison across all 67 exported models.** All 367,104 expected result fields were present in the genuine STAAD `.ANL` outputs; no engineering comparison tolerance was exceeded. This is structural-solver verification for this reference bridge, not independent verification of traffic code rules, RC design equations, detailing, or arbitrary input geometries.

| Group | Models | Fields matched | Differences beyond printed rounding | Engineering comparison failures |
|---|---:|---:|---:|---:|
| stages | 3 | 1,689/1,689 | 0 | 0 |
| permanent_components | 4 | 2,552/2,552 | 0 | 0 |
| traffic/lm1 | 18 | 48,906/48,906 | 6 | 0 |
| traffic/ha | 14 | 29,666/29,666 | 0 | 0 |
| traffic/hb | 13 | 142,961/142,961 | 10 | 0 |
| traffic/ha_hb | 15 | 141,330/141,330 | 17 | 0 |

## Comparison procedure

- Match each STAAD output to its companion manifest by relative path and load-case ID.
- Compare vertical node displacement DZ at every expected node, vertical support reaction FZ at every bearing node, and global member-end FZ, MX and MY at both ends of every expected member.
- Convert STAAD joint displacements from centimetres to metres; forces and moments are kN and kNm.
- Use 0.000003 m plus 0.01% of displacement magnitude and 0.02 kN or kNm plus 0.01% of force/moment magnitude as conservative comparison tolerances for this run. These include STAAD display precision and six-significant-digit section-property input formatting. The largest absolute member-moment difference was 0.0052815 kNm. No value exceeded the comparison tolerance.
- 33 member-moment values were just outside a strict 0.0051 kNm printed-rounding band. Their maximum difference was 0.0052815 kNm; none suggests a modelling discrepancy.

## Analysis diagnostics

- 67 complete STAAD output files; zero reported analysis errors.
- STAAD prints a general `SET Z UP` compatibility notice in every model; none uses the listed incompatible load commands.
- Four pre-composite models warn that the structure is disjointed. This is expected for seven unconnected precast girder lines before deck hardening. Each girder line has its own vertical bearing supports.
- The first final-composite superimposed case also independently balanced 544.80 kN of applied load with 544.80 kN of support reaction.

## Evidence and remaining gates

- External results ZIP SHA-256: `1b6113daaefc0868aa319571f929520118d8c8a5baee3a4a2f51fb267f3f0540`
- Compared input bundle ZIP SHA-256: `ff070cb96331dbd59df2a0321ea16ca6e906d834763b5a1904f0d7aab47dce73`
- The 324 combination applications are linear response superpositions of the verified component and traffic analyses; their arithmetic and published code factors still need independent checking before declaring code-loading verification complete.
- Flexure, shear, crack, deflection, fatigue, anchorage and detailing design equations still require independent verification against appropriate hand calculations or worked examples.
- The reference STAAD files use vertical-grillage representation and in-plane stabilization restraints. Physical bearing stiffness, other geometries, and longitudinal stage-dependent construction effects outside the model are not covered by this comparison.

## Model-by-model results

| Model | Matched fields | Beyond printed rounding | Comparison failures |
|---|---:|---:|---:|
| `permanent_components/deck_construction_structural_dead/deck_construction_structural_dead` | 413 | 0 | 0 |
| `permanent_components/precast_girder_structural_dead/precast_girder_structural_dead` | 413 | 0 | 0 |
| `permanent_components/superimposed_other_superimposed/superimposed_other_superimposed` | 863 | 0 | 0 |
| `permanent_components/superimposed_surfacing/superimposed_surfacing` | 863 | 0 | 0 |
| `stages/deck_construction/full_bridge_deck_construction` | 413 | 0 | 0 |
| `stages/final_composite/full_bridge_final_composite` | 863 | 0 | 0 |
| `stages/precast_girder/full_bridge_precast_girder` | 413 | 0 | 0 |
| `traffic/ha/ha_000008/ha_000008` | 2,119 | 0 | 0 |
| `traffic/ha/ha_000009/ha_000009` | 2,119 | 0 | 0 |
| `traffic/ha/ha_000010/ha_000010` | 2,119 | 0 | 0 |
| `traffic/ha/ha_000025/ha_000025` | 2,119 | 0 | 0 |
| `traffic/ha/ha_000026/ha_000026` | 2,119 | 0 | 0 |
| `traffic/ha/ha_000027/ha_000027` | 2,119 | 0 | 0 |
| `traffic/ha/ha_000035/ha_000035` | 2,119 | 0 | 0 |
| `traffic/ha/ha_000041/ha_000041` | 2,119 | 0 | 0 |
| `traffic/ha/ha_000045/ha_000045` | 2,119 | 0 | 0 |
| `traffic/ha/ha_000137/ha_000137` | 2,119 | 0 | 0 |
| `traffic/ha/ha_000162/ha_000162` | 2,119 | 0 | 0 |
| `traffic/ha/ha_000178/ha_000178` | 2,119 | 0 | 0 |
| `traffic/ha/ha_000179/ha_000179` | 2,119 | 0 | 0 |
| `traffic/ha/ha_000205/ha_000205` | 2,119 | 0 | 0 |
| `traffic/ha_hb/ha_hb_000630/ha_hb_000630` | 9,422 | 1 | 0 |
| `traffic/ha_hb/ha_hb_000632/ha_hb_000632` | 9,422 | 0 | 0 |
| `traffic/ha_hb/ha_hb_000657/ha_hb_000657` | 9,422 | 0 | 0 |
| `traffic/ha_hb/ha_hb_000676/ha_hb_000676` | 9,422 | 2 | 0 |
| `traffic/ha_hb/ha_hb_000678/ha_hb_000678` | 9,422 | 4 | 0 |
| `traffic/ha_hb/ha_hb_000703/ha_hb_000703` | 9,422 | 1 | 0 |
| `traffic/ha_hb/ha_hb_000708/ha_hb_000708` | 9,422 | 2 | 0 |
| `traffic/ha_hb/ha_hb_000734/ha_hb_000734` | 9,422 | 0 | 0 |
| `traffic/ha_hb/ha_hb_000742/ha_hb_000742` | 9,422 | 1 | 0 |
| `traffic/ha_hb/ha_hb_000746/ha_hb_000746` | 9,422 | 0 | 0 |
| `traffic/ha_hb/ha_hb_000754/ha_hb_000754` | 9,422 | 1 | 0 |
| `traffic/ha_hb/ha_hb_000760/ha_hb_000760` | 9,422 | 1 | 0 |
| `traffic/ha_hb/ha_hb_000785/ha_hb_000785` | 9,422 | 3 | 0 |
| `traffic/ha_hb/ha_hb_000786/ha_hb_000786` | 9,422 | 1 | 0 |
| `traffic/ha_hb/ha_hb_000832/ha_hb_000832` | 9,422 | 0 | 0 |
| `traffic/hb/hb_000118/hb_000118` | 10,997 | 1 | 0 |
| `traffic/hb/hb_000122/hb_000122` | 10,997 | 1 | 0 |
| `traffic/hb/hb_000126/hb_000126` | 10,997 | 1 | 0 |
| `traffic/hb/hb_000127/hb_000127` | 10,997 | 1 | 0 |
| `traffic/hb/hb_000131/hb_000131` | 10,997 | 0 | 0 |
| `traffic/hb/hb_000135/hb_000135` | 10,997 | 1 | 0 |
| `traffic/hb/hb_000136/hb_000136` | 10,997 | 1 | 0 |
| `traffic/hb/hb_000137/hb_000137` | 10,997 | 1 | 0 |
| `traffic/hb/hb_000139/hb_000139` | 10,997 | 0 | 0 |
| `traffic/hb/hb_000140/hb_000140` | 10,997 | 1 | 0 |
| `traffic/hb/hb_000141/hb_000141` | 10,997 | 0 | 0 |
| `traffic/hb/hb_000143/hb_000143` | 10,997 | 1 | 0 |
| `traffic/hb/hb_000144/hb_000144` | 10,997 | 1 | 0 |
| `traffic/lm1/lm1_000120/lm1_000120` | 2,717 | 0 | 0 |
| `traffic/lm1/lm1_000216/lm1_000216` | 2,717 | 0 | 0 |
| `traffic/lm1/lm1_000328/lm1_000328` | 2,717 | 0 | 0 |
| `traffic/lm1/lm1_000369/lm1_000369` | 2,717 | 0 | 0 |
| `traffic/lm1/lm1_000376/lm1_000376` | 2,717 | 0 | 0 |
| `traffic/lm1/lm1_000384/lm1_000384` | 2,717 | 1 | 0 |
| `traffic/lm1/lm1_000455/lm1_000455` | 2,717 | 1 | 0 |
| `traffic/lm1/lm1_000457/lm1_000457` | 2,717 | 1 | 0 |
| `traffic/lm1/lm1_000584/lm1_000584` | 2,717 | 0 | 0 |
| `traffic/lm1/lm1_000592/lm1_000592` | 2,717 | 0 | 0 |
| `traffic/lm1/lm1_000625/lm1_000625` | 2,717 | 0 | 0 |
| `traffic/lm1/lm1_000632/lm1_000632` | 2,717 | 0 | 0 |
| `traffic/lm1/lm1_000640/lm1_000640` | 2,717 | 1 | 0 |
| `traffic/lm1/lm1_000711/lm1_000711` | 2,717 | 1 | 0 |
| `traffic/lm1/lm1_000713/lm1_000713` | 2,717 | 1 | 0 |
| `traffic/lm1/lm1_000888/lm1_000888` | 2,717 | 0 | 0 |
| `traffic/lm1/lm1_000973/lm1_000973` | 2,717 | 0 | 0 |
| `traffic/lm1/lm1_000984/lm1_000984` | 2,717 | 0 | 0 |
