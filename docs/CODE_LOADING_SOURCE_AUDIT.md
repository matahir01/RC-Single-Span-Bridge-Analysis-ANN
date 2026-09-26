# V1 highway loading and combination source audit

This audit separates the already completed 83-model STAAD structural-solver
comparison from the rules used to generate design traffic and combinations.
The old STAAD files represent the load cases actually exported at that time;
they cannot certify subsequently changed traffic placement.

## BS EN bridge actions

The primary modern code route is the first-generation British adoption:
**BS EN 1990:2002+A1:2005**, **BS EN 1991-2:2003** and, for concrete design,
**BS EN 1992-2:2005**. The detailed project basis is recorded in
`docs/BS_EN_DESIGN_BASIS.md`.

The main independent worked source is the JRC *Bridge Design to Eurocodes: Worked
Examples*, Chapter 3, Table 3.6, Table 3.8 and Section 3.9.3. The JRC examples
check the underlying EN provisions; the software and reports identify the code
family as BS EN. Nationally Determined Parameters remain explicit project inputs.
A UK National Annex is not silently treated as a Nigerian National Annex.

| Item | Source value or rule | Engine location | Status |
| --- | --- | --- | --- |
| LM1 lane 1/2/3 tandem axles | 300/200/100 kN per axle | `codes/eurocode/lm1.py` | Pinned by literal source test |
| LM1 lane 1/other-lane UDL | 9/2.5 kN/m² | `codes/eurocode/lm1.py` | Pinned by literal source test |
| Leading road traffic ULS | γQ = 1.35; adverse G = 1.35, favourable G = 1.0 on the adopted first-generation recommended basis | `codes/eurocode/combinations.py` | Pinned for the modelled leading LM1 case; NDP basis remains explicit |
| LM1 frequent SLS | ψ1,TS = 0.75, ψ1,UDL = 0.40 on the JRC recommended basis | `traffic/lm1.py` | Separate weighted traffic searches; scalar aggregate factor is rejected |
| LM1 quasi-permanent | ψ2 = 0 in the JRC recommended bridge example | project-supplied `EurocodeServiceabilityFactors` | Explicit project choice; no Nigerian National Annex presumed |
| Complete tandem placement | Both axles of each 1.2 m tandem remain on the loaded length | `traffic/lm1.py` | Source-pinned regression check |
| UDL influence surface | Apply UDL to unfavourable portions longitudinally and transversely | `traffic/lm1_influence.py` | Fixed-grid response-specific search implemented; convergence and end-to-end verification remain required |

The influence search re-solves the selected physical TS plus UDL case and
retains case provenance. It maximizes signed member-end moment, shear and
torsion on the grillage; deflection uses fixed sampling stations plus the
exact member-interpolated maximum of the resulting cases. Cell and tandem
search resolution are numerical controls and need convergence checks on the
final project geometry. The legacy full-UDL route remains selectable only to
reproduce the already completed historical STAAD campaign; it is not the final
BS EN design-placement rule where an influence surface has adverse and
favourable regions.

This focused V1 audit does not certify combinations with wind, thermal, snow,
settlement or accidental actions because they are outside the current
primary-traffic action set.

## Legacy BD 37/01 / BS 5400 traffic

Primary source: BD 37/01 CR01, composite BS 5400: Part 2, Appendix A, clauses
5.1.2, 5.2.2, 6.2.7, 6.3.4 and 6.4.2.

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
are outside this primary-action set. The legacy route remains useful for
Nigerian projects specified to older British bridge practice and as an
independent comparison route, but it must not be numerically blended with the
BS EN profile.

Code-resistance checks remain a separate verification campaign; these loading
tests do not certify BS EN 1992-2 or legacy BS 5400 concrete design, fatigue or
reinforcement detailing.
