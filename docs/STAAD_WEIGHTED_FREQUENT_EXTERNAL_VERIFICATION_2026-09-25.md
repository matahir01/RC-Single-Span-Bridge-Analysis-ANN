# Weighted frequent LM1 STAAD external verification — follow-up

Date: 25 September 2026  
Repository: `matahir01/RC-Single-Span-Bridge-Analysis-ANN`  
Reference: 15 m single-span, seven-girder bridge

> **Status update — 26 September 2026:** the structural-response evidence in
> this report is unchanged. Subsequent source-pinned BS EN checks and the LM1
> convergence audit closed the focused primary BS EN deterministic V1 software
> gate. See `docs/BS_EN_V1_DETERMINISTIC_CLOSURE.md`. That software GO is not
> approval of any particular bridge project or reinforcement drawing.

## Evidence received

- Weighted verification input bundle artifact SHA-256: `cc376befcb8ae7eb0ec0cf82ca2e95f7451a3c79fd512416f7e5fc72b625461b`
- Genuine STAAD results ZIP SHA-256: `78e8249b2f649ee73edf8a9cc576388a697c02af6448d289b9877a83303e4f3a`
- 83 expected model names and 83 STAAD `.ANL` returns matched one-to-one.
- Every return contains the latest-analysis result marker. Four expected pre-composite disjointed-structure warnings remain present.

## Result

**PASS for the separately weighted frequent-LM1 structural-response comparison.**

All 17 `traffic/lm1_frequent` STAAD returns were compared against all 46,189 expected direct-global fields. No expected field was missing and no engineering comparison tolerance was exceeded.

The corrected 28-model HB/HA+HB rerun was also returned and compared. The complete 83-model evidence set is **PASS for structural-response completeness and numerical agreement**: all 410,576 expected fields are present and zero engineering comparison tolerance is exceeded.

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

## Historical missing-output root cause

The first returned HB/HA+HB output set had missing member-end rows because the old exporter emitted fixed groups of 24 member IDs after:

`PRINT MEMBER FORCES GLOBAL LIST`

With four-digit member IDs, some command lines exceeded STAAD's practical input-line length and the final ID could be truncated. This was an output-evidence formatting defect, not a structural member or numerical-response failure.

The deterministic pattern was:

- HB: 25 omitted members per model × 6 fields × 13 models = 1,950 fields.
- HA+HB: 15 omitted members per model × 6 fields × 15 models = 1,350 fields.

## Corrective action and closure

The exporter now chunks member-force print commands by character length rather than a fixed member count. A regression test covers the four-digit IDs, and the reusable `.ANL` comparator refuses to pass incomplete expected-field sets.

The 28 affected models were rerun:

- HA+HB: 15/15 models, 141,330/141,330 fields, 0 missing, 0 comparison failures.
- HB: 13/13 models, 142,961/142,961 fields, 0 missing, 0 comparison failures.
- Corrected rerun total: 28/28 models, 284,291/284,291 fields, 0 missing, 0 comparison failures.
- All 28 outputs contain the latest-analysis marker and no analysis-error lines were detected.
- Largest absolute member-force/moment difference in the corrected rerun: about 0.00527 kN or kNm.

## Verification interpretation

The STAAD structural-response gate is closed for the verified V1 model family:
**83/83 models, 410,576/410,576 fields, zero engineering comparison failures**.

Subsequent work on 26 September 2026 separately closed the BS EN LM1
search-resolution audit at 0.6 m for the 15 m reference bridge (4.08765% maximum
change from the 1.2 m refinement under a 5% criterion), source-pinned the primary
BS EN design/detailing equations, and closed the focused BS EN deterministic V1
**software-capability** gate.

This report remains structural-software evidence. It does not select a National
Annex, prescribe a universal deflection/crack limit, or approve a real bridge
for construction.
