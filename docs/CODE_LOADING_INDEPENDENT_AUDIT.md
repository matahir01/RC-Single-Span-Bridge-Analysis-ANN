# Code loading independent audit — 25 September 2026

## Evidence and scope

Primary external source: European Commission Joint Research Centre, *Bridge Design to Eurocodes Worked Examples*, Chapter 3, Tables 3.6 and 3.8, https://eurocodes.jrc.ec.europa.eu/sites/default/files/2022-06/Bridge_Design-Eurocodes-Worked_examples-main_only.pdf. This independent source was checked against the implemented LM1 lane constants and the 15 m benchmark's 7 m carriageway. The source's recommended factors do not replace a project-specific National Annex.

For a 7 m carriageway, two 3 m notional lanes and a 1 m remaining area give, over 15 m, 1000 kN in two complete tandem systems and 555 kN of UDL at the JRC's characteristic magnitudes (lane 1: 9 kN/m²; lane 2: 2.5 kN/m²; remaining: 2.5 kN/m²). The code's primitive LM1 loads reproduce these values. This load accounting checks the generation of one full-length placement; it does not independently verify every adverse placement or the lane permutation search.

## Blocking finding: Eurocode frequent SLS

JRC Table 3.8 gives different recommended frequent factors for LM1's tandem system (0.75) and UDL (0.40). The current `EurocodeServiceabilityFactors` has only one `psi1_traffic` value, and `frequent_sls` applies it to an already combined LM1 envelope. For this illustrative full-length placement, a factor of 0.75 applied uniformly gives 1166.25 kN, whereas component weighting gives 972 kN. These totals illustrate the factor error only; they are not girder effects. The governing placements must be searched again after weighting the components, because their locations can change.

**Status: Eurocode frequent-SLS code-loading verification fails.** Separate TS and UDL actions, apply the factors selected by the applicable National Annex, re-run the loaded-grillage search for the frequent combination, then propagate the resulting component-wise effects and governing case IDs into project design and exported combination matrices. Do not infer a corrected design result by simply rescaling the existing combined envelope.

## Remaining source checks

- Confirm LM1 notional-lane assignment, lane permutations, wheel coordinates and the adverse longitudinal placement search against the complete EN 1991-2 rules and the applicable National Annex.
- Confirm EN 1990 ULS/SLS factor combinations for favourable and unfavourable permanent effects and the actual action grouping, including the separated frequent LM1 components.
- Check BD 37/01 HA, HB and HA+HB coexistence, lane factors, clear zones and combination factors against the authoritative composite text. The Irish NRA addendum is jurisdiction-specific and cannot by itself establish the Nigerian project's governing HB units or factors.
- Independently check the EC2 and BS 5400 RC resistance, serviceability, fatigue and detailing calculations against published worked examples or traceable hand calculations. STAAD structural agreement is not evidence for these design equations.

The 67-model STAAD structural-response campaign remains a passed verification of its exported model and loads. It does not establish that the selected loads or design factors comply with either standard.
