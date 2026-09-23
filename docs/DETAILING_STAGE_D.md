# Stage D — Anchorage, Curtailment, Face Steel and Fatigue Infrastructure

Stage D converts a globally adequate longitudinal cage into bridge-specific
detailing information. It is deliberately split into explicit engineering
sub-checks so the program never promotes a bar schedule simply because the
midspan ULS area is adequate.

## Implemented in the current Stage D batch

### 1. EC2 anchorage

The Eurocode detailing path now calculates straight-bar tension anchorage from

`f_bd = 2.25 eta1 eta2 f_ctd`

and

`l_b,rqd = (phi / 4) sigma_sd / f_bd`.

The alpha-factor product and the tension-bar minimum anchorage length are then
applied. Bond-condition factors remain explicit inputs. If available anchorage
length is supplied the result reports a direct pass/fail; otherwise the
required length is reported without inventing available geometry.

### 2. BS 5400 side-face reinforcement

The existing BS 5400 minimum side-face steel demand is now converted into a
discrete reinforcement recommendation on each face. Bar diameter and optional
maximum spacing are explicit inputs. The previous provided-area audit remains
available separately.

### 3. Preliminary curtailment/zoning engine

A station-wise required-steel envelope can now be converted into longitudinal
bar-continuation zones. The routine:

- requires the actual station-wise steel demand as input;
- calculates the minimum number of bars required in each interval;
- identifies theoretical cut-off locations;
- extends cut-offs by the supplied anchorage length away from the high-demand
  region.

The routine intentionally does not invent a bending-moment envelope. It is now
fed directly by the implemented EC2 LM1 station-demand envelope and by the BS
5400 common-grid HA/HB/HA+HB station-demand envelope when those traffic searches
are supplied to project detailing.

### 4. Reinforcement fatigue stress-range checker

A dedicated fatigue checker now exists for an already established equivalent
reinforcement stress range and characteristic fatigue resistance. It applies
explicit action/resistance factors and reports utilization and margin.

It deliberately does not invent:

- the bridge fatigue traffic model;
- equivalent-cycle factors;
- reinforcement/detail category;
- S-N resistance.

Those belong to the applicable code-specific fatigue loading/detailing path and
must be supplied before the fatigue result can be promoted to design evidence.

### 5. Doubly reinforced flexural requirement

The layered-section engine now has a dedicated doubly reinforced extension for
both EC2 and the repository's BS 5400 flexural basis.

For EC2, when the configured singly reinforced neutral-axis limit is exceeded,
the routine fixes the concrete block at that limiting neutral axis and resolves
the excess moment through a compression-steel/additional-tension-steel couple.
Compression-steel stress is calculated from strain compatibility and capped at
the design yield stress.

For BS 5400, the same layered limiting concrete-block basis used by the
repository's existing singly reinforced check is retained, and the excess
moment is carried by an explicit design-stress compression/tension couple.

Both requirement routines report force-equilibrium and moment residuals. The
detailer now continues beyond the continuous requirement: it generates
discrete bottom-tension and top-compression cage candidates, calculates each
multilayer cage centroid, updates the actual d and d', solves final combined
force equilibrium, and verifies the selected pair at ULS. EC2 uses
strain-compatible steel stresses capped at fyd; the BS 5400 path retains the
repository's explicit legacy design-stress basis. A cage pair is not accepted
merely because each separate provided area exceeds the continuous requirement.

### 6. Station-wise Eurocode ULS reinforcement envelope

The LM1 common-grillage search now retains a governing bending-moment envelope
at every longitudinal grillage station for every girder. This is accumulated
during the traffic search itself, so it does not depend on retaining every
full traffic case in memory.

For a selected girder the EC2 detailing path can now combine, station by
station:

- the factored permanent-action bending moment evaluated at the same exact
  longitudinal coordinate;
- the governing LM1 traffic bending moment and its governing traffic case ID;
- the configured persistent ULS factors;
- the layered EC2 flexural resistance model;
- code minimum longitudinal steel.

The result is a true longitudinal `A_s(x)` demand envelope rather than a
single midspan/global maximum. When the LM1 search is exhaustive and every
station remains within the singly reinforced scope, the project-detailing path
can immediately convert that envelope into an anchorage-extended preliminary
curtailment plan for the selected discrete cage.

Reduced LM1 searches are deliberately not allowed to certify curtailment.

## Stage D still outstanding

The following items remain before Stage D can be called complete:

1. add code-specific support anchorage, tension-shift and bar-termination rules
   to the curtailment planner;
2. implement the actual bridge fatigue traffic/loading path and convert it to
   reinforcement stress ranges per candidate cage;
3. integrate construction-stage steel stress/resistance checks;
4. add lap/splice zoning and local bearing/end-zone congestion checks;
5. extend the doubly reinforced selected-cage path through the relevant SLS
   crack/stress checks before it can be promoted to a final drawing schedule.

Until those are complete, Stage D outputs are engineering detailing inputs and
verified sub-checks, not a final construction drawing schedule.

## BS 5400 exact common-grid reinforcement zoning

The HA-alone, HB-alone and HA+HB common-grillage searches retain a governing
longitudinal bending-moment envelope at every generated girder station, with
governing case IDs and member IDs. For reinforcement zoning the three searches
are now also supplied with the same explicit design-station x-grid. Those
coordinates are inserted into each actual grillage topology, so their moments
are solved at exact common stations rather than interpolated between different
traffic grids.

At every common station the BS detailing path evaluates permanent actions with
their category-specific ULS factors and compares HA, HB and HA+HB with the
traffic-specific gamma_fL values for combinations 1-3. The layered BS flexural
solver then produces A_s(x), retaining minimum main steel where it governs.
When the search is exhaustive, the singly reinforced envelope is complete, a
longitudinal cage is selected, and a BS anchorage length is supplied explicitly,
the result can feed the preliminary bar-continuation/curtailment plan.
