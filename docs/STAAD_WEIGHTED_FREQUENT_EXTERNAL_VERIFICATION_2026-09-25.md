# Weighted frequent LM1 STAAD external verification — follow-up

Date: 25 September 2026  
Repository: `matahir01/RC-Single-Span-Bridge-Analysis-ANN`  
Reference: 15 m single-span, seven-girder bridge

## Evidence received

- Weighted verification input bundle artifact SHA-256: `cc376befcb8ae7eb0ec0cf82ca2e95f7451a3c79fd512416f7e5fc72b625461b`
- Genuine STAAD results ZIP SHA-256: `78e8249b2f649ee73edf8a9cc576388a697c02af6448d289b9877a83303e4f3a`
- 83 expected model names and 83 STAAD `.ANL` returns matched one-to-one.
- Every return contains the latest-analysis result marker. Four expected pre-composite disjointed-structure warnings remain present.

## Result

**PASS for the newly weighted Eurocode frequent-LM1 structural-response comparison.**

All 17 `traffic/lm1_frequent` STAAD returns were compared against all 46,189 expected direct-global fields. No expected field was missing and no engineering comparison tolerance was exceeded.

The complete 83-model evidence set is **not yet completeness-passable** because the returned HB and HA+HB output files omit selected member-end result rows. Among fields actually printed by STAAD, there are zero engineering comparison failures.

| Group | Models | Expected fields | Fields present | Missing | Tolerance failures |
|---|---:|---:|---:|---:|---:|
| permanent components | 4 | 2,552 | 2,552 | 0 | 0 |
| construction stages | 3 | 1,689 | 1,689 | 0 | 0 |
| HA | 14 | 29,666 | 29,666 | 0 | 0 |
| HA+HB | 15 | 141,330 | 139,980 | 1,350 | 0 |
| HB | 13 | 142,961 | 141,011 | 1,950 | 0 |
| LM1 characteristic | 17 | 46,189 | 46,189 | 0 | 0 |
| LM1 frequent, TS 0.75 / UDL 0.40 | 17 | 46,189 | 46,189 | 0 | 0 |
| **Total** | **83** | **410,576** | **407,276** | **3,300** | **0** |

The largest absolute differences among present fields remain small: approximately 0.0050 kN for support reactions and 0.00529 kN/kNm for member-end forces/moments. The comparison uses 0.000003 m plus 0.01% of magnitude for displacement and 0.02 kN or kNm plus 0.01% of magnitude for force/moment.

## Missing-output root cause

The absent fields are not missing structural members and they are not numerical comparison failures. They arise from an evidence-export formatting defect.

The previous exporter emitted fixed groups of 24 member IDs after:

`PRINT MEMBER FORCES GLOBAL LIST`

Once member IDs reach four digits, some command lines exceed STAAD's practical input-line length. STAAD warns that the line is being split and can truncate the final ID. In the supplied returns, examples such as intended member 1032 are echoed as `103`, so that member's six direct-global end-force fields are never printed.

The pattern is deterministic:

- HB: 25 omitted members per model × 6 fields × 13 models = 1,950 missing fields.
- HA+HB: 15 omitted members per model × 6 fields × 15 models = 1,350 missing fields.

The structural results that STAAD did print agree with the native engine within the verification tolerances.

## Corrective action

The STAAD exporter now constructs member-force print commands by character length rather than by a fixed 24-member count. A regression test explicitly recovers every member ID across the four-digit range, including the previously truncated IDs. A reusable `.ANL` parser/comparator has also been added so future verification cannot report a pass when expected fields are absent.

Only the 28 affected BS traffic models (13 HB + 15 HA+HB) need a fresh STAAD run for completeness. The other 55 models, including all 17 weighted frequent-LM1 cases, do not need to be rerun for this defect.

## Effect on verification status

The blocking weighted frequent-LM1 structural-response check is closed for the reference bridge: **17/17 models, 46,189/46,189 fields, zero comparison failures.**

The broader deterministic program remains **NO-GO for release** because:

1. the 28 affected BS traffic evidence files still need complete member-end output after the exporter fix;
2. the applicable EN 1990/EN 1991-2 National Annex and remaining action-grouping/placement checks are not fully closed; and
3. RC resistance, serviceability, fatigue and detailing calculations still require independent source/hand-calculation verification.

The earlier 67-model external-verification report remains evidence of strong numerical agreement, but the current follow-up exposes a print-output completeness issue in the same HB/HA+HB model family. Its HB/HA+HB completeness claim should therefore be treated as under review until the corrected 28-model rerun is returned.
