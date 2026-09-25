# Code loading independent audit — 25 September 2026

## Evidence and scope

Primary external source: European Commission Joint Research Centre, *Bridge Design to Eurocodes Worked Examples*, Chapter 3, Tables 3.6 and 3.8, https://eurocodes.jrc.ec.europa.eu/sites/default/files/2022-06/Bridge_Design-Eurocodes-Worked_examples-main_only.pdf. This independent source was checked against the implemented LM1 lane constants and the 15 m benchmark's 7 m carriageway. The source's recommended factors do not replace a project-specific National Annex.

For a 7 m carriageway, two 3 m notional lanes and a 1 m remaining area give, over 15 m, 1000 kN in two complete tandem systems and 555 kN of UDL at the JRC's characteristic magnitudes (lane 1: 9 kN/m²; lane 2: 2.5 kN/m²; remaining: 2.5 kN/m²). The code's primitive LM1 loads reproduce these values. This load accounting checks the generation of one full-length placement; it does not independently verify every adverse placement or the lane permutation search.

## Blocking finding: Eurocode frequent SLS

JRC Table 3.8 gives different recommended frequent factors for LM1's tandem system (0.75) and UDL (0.40). The current `EurocodeServiceabilityFactors` has only one `psi1_traffic` value, and `frequent_sls` applies it to an already combined LM1 envelope. For this illustrative full-length placement, a factor of 0.75 applied uniformly gives 1166.25 kN, whereas component weighting gives 972 kN. These totals illustrate the factor error only; they are not girder effects. The governing placements must be searched again after weighting the components, because their locations can change.

**Status: full Eurocode frequent-SLS code-loading verification remains open.** The reference runner now accepts separate tandem and UDL factors and re-runs LM1 placement search with component-weighted loads before combining girder effects. The export of a STAAD combination matrix with different factors is deliberately rejected until its full-width traffic models and governing case IDs can include this weighted search. Existing single-factor runs remain legacy calculations and must not be interpreted as verification against the distinct recommended factors. The National Annex and a new independent external response comparison remain necessary; do not infer a corrected design result by rescaling the old combined envelope.

## Owner-supplied Ragana bridge calculation benchmark

The supplied `river-ragana-bridge-design-calculations-final_compress.pdf` (T. Onyango / Eng. M. Olela, April 2015), printed pp. 65-67, provides a useful **BS 5400 shear-component benchmark**. With the report's stated V = 835 kN, average web width = 329 mm, effective depth = 1349 mm, provided main steel = 12861 mm², fcu = 35 MPa and fyv = 460 MPa, the app returns design stress 1.881 MPa, adjusted concrete shear stress 0.786 MPa and Asv/s = 1.229 mm²/mm. The report rounds these to 1.88, 0.79 and 1.23 respectively. A source-based regression test is committed in `tests/test_ragana_bs5400_reference.py`. This verifies one shear-equation substitution; the 20 m Kenyan bridge's section, factors, traffic and materials do not establish a full-project validation for the 15 m reference bridge.

The report's printed p. 68 cracking worked example gives b = 329 mm, modular ratio 15, As = 12861 mm² and d = 1349 mm but reports neutral axis x = 1043 mm. Direct substitution into its own quadratic, b*x²/2 + 15*As*x - 15*As*d = 0, gives about 801 mm. That cracking result cannot serve as an independent acceptance benchmark until the inconsistency is resolved. The report also identifies HA as critical while taking its listed governing SLS moment from the HB column; use its combined-load selections cautiously.

## Remaining source checks

- Confirm LM1 notional-lane assignment, lane permutations, wheel coordinates and the adverse longitudinal placement search against the complete EN 1991-2 rules and the applicable National Annex.
- Confirm EN 1990 ULS/SLS factor combinations for favourable and unfavourable permanent effects and the actual action grouping, including the separated frequent LM1 components.
- Check BD 37/01 HA, HB and HA+HB coexistence, lane factors, clear zones and combination factors against the authoritative composite text. The Irish NRA addendum is jurisdiction-specific and cannot by itself establish the Nigerian project's governing HB units or factors.
- Independently check the EC2 and BS 5400 RC resistance, serviceability, fatigue and detailing calculations against published worked examples or traceable hand calculations. STAAD structural agreement is not evidence for these design equations.

The 67-model STAAD structural-response campaign remains a passed verification of its exported model and loads. It does not establish that the selected loads or design factors comply with either standard.
