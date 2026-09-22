# Engineering benchmark bridges

The focused single-span repository deliberately keeps more than one physical
bridge benchmark. A design feature is not accepted merely because it can
reproduce one familiar reinforcement cage.

## Benchmark A — 15 m rectangular research bridge

Source: examples/reference_bridge_15m.py.

This remains the primary research/reference case: 15 m simply supported span,
7 girders at 1.70 m spacing, 11.0 m deck, 7.0 m carriageway, 400 x 950 mm
rectangular precast girder and 75 + 175 mm deck construction. The stored
4 x 4 Y32 cage is a provided/reference cage to audit; it is not a value that
the design engine is allowed to reverse-engineer.

## Benchmark B — 20 m haunched I-girder

Source: examples/reference_bridge_20m_i.py.

This case represents a field-style I-girder while preserving the same focused
single-span architecture. The physical precast section is:

- 400 x 150 mm top flange;
- 150 mm tapered top haunch, 400 -> 250 mm;
- 250 x 500 mm clear web;
- 200 mm tapered bottom haunch, 250 -> 400 mm;
- 400 x 200 mm bottom flange.

The overall precast depth is 1.20 m. The benchmark deliberately stores no
provided longitudinal reinforcement. Future reinforcement-selection changes
must therefore derive their answer from actions, ULS/SLS/fatigue requirements
and constructability rather than matching a hard-coded bar schedule.

The permanent actions in this benchmark are explicitly labelled assumptions.
They are useful for repeatable regression work but are not as-built data.

## Acceptance rule

Changes to section geometry, loading, analysis or RC design should be checked
against both benchmark classes. Rectangular, T and I sections remain supported.
The I-girder may include optional tapered haunches; zero-haunch I-sections remain
backward compatible.

For haunched sections, area, centroid and bending inertias are calculated from
the exact symmetric trapezoidal bands. The grillage torsion constant for a
tapered haunch currently uses an explicitly documented mean-width rectangular
component approximation; this is not to be represented as an exact St-Venant
solution.
