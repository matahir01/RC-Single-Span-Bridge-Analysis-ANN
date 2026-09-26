# BS EN bridge deflection basis

## Scope

The primary modern route in this repository is BS EN.  The deterministic solver
calculates elastic vertical displacement from the same physical bridge model and
load cases used for the other response checks.  Acceptance of that displacement
is deliberately separated from calculation of the displacement itself.

## No hidden universal span ratio

The program does **not** hard-code a single L/n deflection limit and label it a
BS EN requirement.  A project may adopt an allowable displacement or span ratio
through its client brief, approving authority, National Annex/NDP basis or other
traceable project specification.  That criterion must therefore remain an
explicit project input.

`ProjectDeflectionCriterion.from_span_ratio(...)` is only a unit/provenance
helper.  It converts an explicitly supplied span ratio to millimetres:

`delta_allow = L / n`

where `n` has no software default.  For example, a 15 m span with a project-
specified L/300 limit produces 50 mm, while L/250 produces 60 mm.  Neither ratio
is asserted by the engine to be a universal BS EN road-bridge rule.

## Response combination

For a selected serviceability traffic basis, the project design result combines
stage-aware permanent displacement and the corresponding analysed traffic
response linearly:

`delta_total = delta_G + psi * delta_Q`

The all-case verification search separately checks retained traffic cases and
longitudinal stations so that the final verification is not restricted to the
station that governed the traffic-only displacement envelope.

When no project deflection limit is supplied, the software reports the response
but returns no pass/fail decision.  When a limit is supplied, the result carries
both the allowable value and optional criterion provenance so the calculation
report can identify the project basis rather than implying a code default.

## Verification boundary

The underlying elastic displacements have independent STAAD comparison evidence
within the completed full-width structural-response campaign.  The remaining
serviceability acceptance task is to review a complete BS EN reference-girder
deflection calculation with its deliberately selected project criterion and the
all-case combined-displacement search.  That review is separate from structural
solver agreement and from the project authority's choice of allowable limit.
