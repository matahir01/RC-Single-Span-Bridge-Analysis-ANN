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

The corrected 28-model HB/HA+HB rerun has now been returned and compared. The complete 83-model evidence set is **PASS for structural-response completeness and numerical agreement**: all 410,576 expected fields are present and zero engineering comparison tolerance is exceeded.

| Group | Models | Expected fields | Fields present | Missing | Tolerance failures |
|---|---:|---:|---:|---:|---:|
| permanent components | 4 | 2,552 | 2,552 | 0 | 0 |
| construction stages | 3 | 1,689 | 1,689 | 0 | 0 |
| HA | 14 | 29,666 | 29,666 | 0 | 0 |
| HA+HB | 15 | 141,330 | 141,330 | 0 | 0 |
| HB | 13 | 142,961 | 142,961 | 0 | 0 |
| LM1 characteristic | 17 | 46,189 | 46,189 | 0 | 0 |
| LM1 frequent, TS 0.75 / UDL 0.40 | 17 | 46,189 | 46,189 | 0 | 0 |
| **Total** | **83** | **410,576** | **410,576** | **0** | **0** |

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

The 28 affected BS traffic models (13 HB + 15 HA+HB) were rerun with the corrected exporter. Every expected field is now present and every comparison is within tolerance. The other 55 models did not require rerunning for this defect.

## Effect on verification status

The blocking weighted frequent-LM1 structural-response check is closed for the reference bridge: **17/17 models, 46,189/46,189 fields, zero comparison failures.**

The structural-response STAAD campaign is now closed for the 15 m reference bridge: all current 83 exported models, including the 17 weighted frequent-LM1 cases, have complete genuine STAAD returns with zero engineering comparison failures.

The broader deterministic program remains **NO-GO for release** because the applicable EN 1990/EN 1991-2 National Annex and remaining action-grouping/placement checks are not fully closed, and RC resistance, serviceability, fatigue and detailing calculations still require independent source/hand-calculation verification.

The earlier 67-model report is superseded for completeness by this 83-model follow-up. Its numerical agreement remains valid evidence, while the corrected rerun closes the HB/HA+HB print-output gap.


## Corrected BS rerun closure

A corrected rerun containing only the previously affected 13 HB and 15 HA+HB models was returned after the member-force print commands were changed to character-length chunking.

- HA+HB: 15/15 models, 141,330/141,330 expected fields, 0 missing, 0 comparison failures.
- HB: 13/13 models, 142,961/142,961 expected fields, 0 missing, 0 comparison failures.
- Corrected rerun total: 28/28 models, 284,291/284,291 expected fields, 0 missing, 0 comparison failures.
- All 28 outputs contain the latest-analysis result marker and no analysis-error lines were detected.
- Largest absolute member-force/moment difference in the corrected rerun: about 0.00527 kN or kNm, well inside the adopted 0.02 + 0.01% magnitude tolerance.

This closes the output-completeness defect documented above.
