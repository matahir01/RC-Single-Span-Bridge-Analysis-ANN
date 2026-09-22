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

The routine intentionally does not invent a bending-moment envelope. Full
project integration therefore still requires a station-wise ULS steel-demand
envelope from the common grillage/combinations.

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

Both routines report force-equilibrium and moment residuals. They are
requirement solvers only at this stage; automatic discrete top-compression-bar
selection and final combined-cage verification remain to be integrated.

## Stage D still outstanding

The following items remain before Stage D can be called complete:

1. generate the station-wise ULS reinforcement-demand envelope directly from
   the retained common-grillage traffic/combinations;
2. integrate the doubly reinforced requirement into automatic bottom/top cage
   selection using the actual discrete cage centroids;
3. run a final combined doubly reinforced resistance check on the selected
   bottom and compression cages;
4. add code-specific support anchorage, tension-shift and bar-termination rules
   to the curtailment planner;
5. implement the actual bridge fatigue traffic/loading path and convert it to
   reinforcement stress ranges per candidate cage;
6. integrate construction-stage steel stress/resistance checks;
7. add lap/splice zoning and local bearing/end-zone congestion checks.

Until those are complete, Stage D outputs are engineering detailing inputs and
verified sub-checks, not a final construction drawing schedule.
