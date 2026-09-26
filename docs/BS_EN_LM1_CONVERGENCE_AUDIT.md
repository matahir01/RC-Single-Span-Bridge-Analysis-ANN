# BS EN 1991-2 LM1 influence-search convergence audit

## Purpose

The production BS EN route uses the response-specific signed influence-surface
LM1 search. Because the tandem-system longitudinal positions are discretised,
the adopted search step must be demonstrated to be sufficiently refined for the
reference bridge rather than treated as a universal constant.

This audit is deliberately separate from the completed STAAD structural-solver
comparison. STAAD agreement verifies structural response for exported load
cases; this convergence audit checks whether the BS EN LM1 search itself has
stabilised as the tandem-position grid is refined.

## Reference basis

- Bridge: 15 m simply supported single-span RC reference bridge.
- Carriageway: 7.0 m.
- Primary traffic basis: BS EN 1991-2:2003 LM1.
- Concrete elastic modulus used only for the verification run: 31,000 MPa,
  explicitly recorded as the BS EN 1992-1-1 Table 3.1 C25/30 verification
  assumption.
- Acceptance tolerance: maximum relative change <= 5% across the girder
  envelopes for bending moment, shear, torsion and deflection.
- Tandem placements must remain exhaustive at every refinement. A reduced
  search is not eligible to be labelled converged.

## First refinement: 2.4 m -> 1.2 m

GitHub Actions run `36228045371` completed the exhaustive refinement and produced
an audit artifact. The engineering result was **NOT CONVERGED** at the adopted
5% tolerance:

| Item | Result |
| --- | ---: |
| Coarse longitudinal step | 2.4 m |
| Fine longitudinal step | 1.2 m |
| Exhaustive tandem combinations | Yes |
| Theoretical combinations per transverse layout at 1.2 m | 169 |
| Evaluated LM1 placements at 1.2 m | 676 |
| Maximum relative envelope change | 13.4036% |
| Governing quantity | Shear |
| Governing girder | 4 |

The 1.2 m result was therefore rejected. The 5% criterion was not relaxed.

## Second refinement: 1.2 m -> 0.6 m

GitHub Actions run `36228438781` completed successfully and uploaded the audit
artifact `bs-en-lm1-convergence-audit` with digest
`sha256:34c9540cc159ea882f5f65daac8f735caa477b953b24266dd7ff8bd270dc5dfc`.
The engineering convergence result was **PASS**:

| Item | Result |
| --- | ---: |
| Coarse longitudinal step | 1.2 m |
| Fine longitudinal step | 0.6 m |
| Exhaustive tandem combinations | Yes |
| Theoretical combinations per transverse layout at 0.6 m | 576 |
| Evaluated LM1 placements at 0.6 m | 2,304 |
| Maximum relative envelope change | 4.08765% |
| Governing quantity | Torsion |
| Governing girder | 2 |
| Acceptance tolerance | 5.0% |

Because 4.08765% is below the pre-declared 5% criterion and the tandem search
remained exhaustive, the **15 m reference bridge LM1 search-resolution gate is
closed at 0.6 m**.

## Production consequence

`ReferenceRunConfig` now uses `lm1_longitudinal_step_m = 0.6` for the 15 m
reference project so the production/reference deterministic path does not fall
back to the rejected 1.2 m grid.

This is not a universal Eurocode discretisation rule. A materially different
span, lane arrangement, girder layout or response topology should run the same
convergence audit and either accept its own converged step or refine further.
