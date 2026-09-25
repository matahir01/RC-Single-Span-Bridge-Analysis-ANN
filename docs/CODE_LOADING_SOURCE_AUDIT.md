# V1 highway loading and combination source audit

This audit separates the already completed 83-model STAAD structural-solver
comparison from the rules used to generate design traffic and combinations.
The old STAAD files represent the load cases actually exported at that time;
they cannot certify subsequently changed traffic placement.

## Eurocode bridge actions

Primary worked source: [JRC Bridge Design to Eurocodes: Worked Examples](https://eurocodes.jrc.ec.europa.eu/sites/default/files/2022-06/Bridge_Design-Eurocodes-Worked_examples.pdf),
Chapter 3, Table 3.6, Table 3.8 and Section 3.9.3 (pp. 58-63 of the chapter).

| Item | Source value or rule | Engine location | Status |
| --- | --- | --- | --- |
| LM1 lane 1/2/3 tandem axles | 300/200/100 kN per axle | `codes/eurocode/lm1.py` | Pinned by literal source test |
| LM1 lane 1/other-lane UDL | 9/2.5 kN/m² | `codes/eurocode/lm1.py` | Pinned by literal source test |
| Leading road traffic ULS | γQ = 1.35; adverse G = 1.35, favourable G = 1.0 | `codes/eurocode/combinations.py` | Pinned for the modelled leading LM1 case |
| LM1 frequent SLS | ψ1,TS = 0.75, ψ1,UDL = 0.40 | `traffic/lm1.py` | Separate weighted traffic searches; scalar aggregate factor is rejected |
| LM1 quasi-permanent | ψ2 = 0 in the JRC recommended bridge example | project-supplied `EurocodeServiceabilityFactors` | Explicit project choice; no Nigerian National Annex presumed |
| UDL influence surface | Apply to unfavourable portions longitudinally and transversely | `traffic/lm1_influence.py` | New fixed-grid response-specific search; production reference runner can select it with `lm1_udl_influence_surface=True` |

The influence search re-solves the selected physical TS plus UDL case and
retains case provenance. It maximizes signed member-end moment, shear and
torsion on the grillage; deflection uses fixed sampling stations plus the
exact member-interpolated maximum of the resulting cases. Cell and tandem
search resolution are numerical controls and need convergence checks on the
final project geometry. The legacy full-UDL route remains selectable to
reproduce the 83-model campaign. This audit does not certify combinations
with wind, thermal, snow, settlement or accidental actions, which are outside
the focused primary-traffic V1 model.

## BD 37/01 / BS 5400 traffic

Primary source: [BD 37/01 CR01, composite BS 5400: Part 2](https://www.standardsforhighways.co.uk/tses/attachments/d9448824-a259-4cd3-938b-15daeacd90a0?inline=true),
Appendix A, clauses 5.1.2, 5.2.2, 6.2.7, 6.3.4 and 6.4.2.

| Item | Source values or rule | Engine location | Status |
| --- | --- | --- | --- |
| Structural concrete dead γfL | ULS 1.15, SLS 1.0 | `codes/bs5400/combinations.py` | Pinned by source test |
| Deck surfacing γfL | ULS 1.75, SLS 1.20 | `codes/bs5400/combinations.py` | Pinned by source test |
| Other superimposed γfL | ULS 1.20, SLS 1.0 | `codes/bs5400/combinations.py` | Pinned by source test |
| HA alone γfL | Combination 1: 1.50/1.20 (ULS/SLS); 2–3: 1.25/1.00 | `codes/bs5400/combinations.py` | Pinned by source test |
| HB and coexistent HA γfL | Combination 1: 1.30/1.10; 2–3: 1.10/1.00 | `codes/bs5400/traffic.py` | Pinned by source test |
| HA+HB coexistence | HB may straddle lanes; displaced HA has 25 m clear zones, no KEL; a qualifying residual strip keeps UDL using the 2.5 m lane factor | `traffic/bs5400_combined.py` | Implemented in the primary-traffic search; retain geometric edge-case verification |

The source allows authority-specific HB unit counts and certain permanent
load factor reductions. The engine requires an explicit project choice for
those parameters. Combinations 4–5 need secondary or accidental actions and
are outside this primary-action set. Code-resistance checks remain a separate
verification campaign; these loading tests do not certify EC2 or BS concrete
design, fatigue or reinforcement detailing.
