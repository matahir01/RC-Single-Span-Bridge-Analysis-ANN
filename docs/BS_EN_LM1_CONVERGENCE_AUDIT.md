# BS EN 1991-2 LM1 influence-search convergence audit

## Purpose

The production BS EN route uses the response-specific signed influence-surface
LM1 search.  Because the tandem-system longitudinal positions are discretised,
the adopted search step must be demonstrated to be sufficiently refined for the
reference bridge rather than treated as a universal constant.

This audit is deliberately separate from the completed STAAD structural-solver
comparison.  STAAD agreement verifies structural response for exported load
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
- Tandem placements must remain exhaustive at every refinement.  A reduced
  search is not eligible to be labelled converged.

## First refinement: 2.4 m -> 1.2 m

GitHub Actions run `36228045371` completed the exhaustive refinement and produced
an audit artifact.  The engineering result was **NOT CONVERGED** at the adopted
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

The 1.2 m result is therefore **not** accepted merely because it is finer than
the previous grid.  The 5% criterion has not been relaxed.

## Required next refinement

The audit workflow has been changed to evaluate **1.2 m -> 0.6 m** with the same
5% acceptance criterion and exhaustive-search requirement.  The 0.6 m grid is
within the configured exhaustive-combination cap for the 7 m reference
carriageway.

Until that refinement completes satisfactorily, the BS EN LM1 numerical-search
convergence item remains open.  A failure at 0.6 m is evidence to refine or
improve the search further, not a reason to widen the acceptance tolerance.
