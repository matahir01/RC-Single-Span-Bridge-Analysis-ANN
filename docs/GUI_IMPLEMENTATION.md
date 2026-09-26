# Desktop GUI implementation

Date: 26 September 2026

## Current status

A PySide6/Qt desktop GUI has been started on top of the verified deterministic
bridge engine. The GUI is deliberately an adapter/presentation layer: design-code
logic remains in the existing `analysis`, `traffic`, `codes`, `design`,
`verification`, and `research` packages.

The first functional GUI pass provides:

- project create/open/save using a versioned JSON payload;
- editable 15 m thesis-bridge defaults;
- rectangular, T and I precast-girder input panels;
- deck construction and composite-participation inputs;
- C35/45/B500 material and longitudinal-reinforcement inputs;
- explicit surfacing, barrier and services actions;
- selectable BS EN or BS 5400 / BD 37 analysis profile;
- editable LM1 frequent factors, LM1 search step and HB units;
- background deterministic analysis so the Qt interface remains responsive;
- governing girder M/V/T result tables; and
- dedicated verification and ANN/reliability workspace placeholders.

The application entry point is:

```text
rc-bridge-gui
```

Install the GUI extra first:

```text
pip install -e ".[gui]"
```

## Engineering boundary

The GUI does not create new engineering rules. It only collects explicit inputs,
constructs the same `BridgeProject` models used by the tested engine and calls the
existing deterministic runner.

The BS EN result page currently exposes the persistent ULS girder envelope from the
verified LM1 route. The legacy BS result page exposes the vertical-grillage HA/HB/
HA+HB combinations 1-3. BS 5400 combinations 4-5 remain executable in the engine,
but the GUI must not fabricate their horizontal/local structural effects. A later
input panel will accept those effects (with provenance) from an appropriate model
and then feed the full 1-5 combination layer.

Similarly, design/detailing PASS/CHECK results will only be shown after their
required project inputs are supplied. No hidden crack-width, deflection, fatigue,
bearing, splice, containment or construction-stage criteria are to be invented by
the GUI.

## Next GUI increments

1. Add full code-specific design/detailing input panels and results.
2. Add construction-stage, traffic-position and girder-envelope visualisation.
3. Add full BS 5400 combination-4/5 effect import/input and governing envelope.
4. Add STAAD export/import and comparison views.
5. Add calculation-report PDF/Excel export and report browser.
6. Add project-level validation messages and input provenance fields.
7. Add ANN/LHS/FORM/Monte-Carlo/RBDO controls after the final probabilistic study
   basis is frozen.
8. Package the tested GUI as a Windows executable after desktop acceptance tests.

A GUI result is a software calculation output, not approval of a real bridge or a
replacement for project-specific engineering review.
