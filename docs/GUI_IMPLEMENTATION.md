# Desktop GUI implementation

Date: 26 September 2026

## Current status

A PySide6/Qt desktop GUI is now wired to the verified deterministic bridge engine.
The GUI is deliberately an adapter/presentation layer: design-code logic remains in
the existing `analysis`, `traffic`, `codes`, `design`, `verification`, and `research`
packages rather than being duplicated in Qt callbacks.

The current functional GUI provides:

- project create/open/save using a versioned JSON payload;
- editable 15 m C35/45 B500 thesis-bridge defaults;
- rectangular, T and I precast-girder input panels;
- deck construction and composite-participation inputs;
- material and longitudinal-reinforcement inputs;
- explicit surfacing, barrier and services actions;
- selectable BS EN or BS 5400 / BD 37 analysis profile;
- editable LM1 frequent factors, LM1 search step and HB units;
- background deterministic analysis so the Qt interface remains responsive;
- governing girder M/V/T result tables;
- an optional code-specific Design Checks tab;
- BS EN flexure, shear, crack-width and deflection result rows when enabled;
- BS 5400 flexure, shear, crack-width and deflection result rows when enabled;
- an explicit project deflection-limit/provenance pair rather than a hidden L/n rule;
- saved analysis and design settings in the GUI project file; and
- dedicated verification and ANN/reliability workspace placeholders.

The application entry point is:

```text
rc-bridge-gui
```

Install the GUI extra first:

```text
pip install -e ".[gui]"
```

The command is routed through a small launcher that gives a clear installation
message when PySide6 is not installed.

## GUI CI

`.github/workflows/gui-smoke.yml` installs the GUI extra plus the Linux Qt runtime
libraries, launches the window using Qt's offscreen platform and runs the dedicated
GUI smoke test. This supplements the normal Ruff/pytest workflow; it does not replace
interactive Windows acceptance testing.

## Engineering boundary

The GUI does not create new engineering rules. It collects explicit inputs,
constructs the same `BridgeProject` models used by the tested engine and calls the
existing deterministic runner.

The BS EN result page exposes the persistent ULS girder envelope from the verified
LM1 route. The legacy BS result page exposes the vertical-grillage HA/HB/HA+HB
combinations 1-3. BS 5400 combinations 4-5 remain executable in the engine, but the
GUI must not fabricate their horizontal/local structural effects. A later input or
import panel will accept those effects with provenance from an appropriate model and
then feed the full 1-5 combination layer.

The Design Checks tab only calls the code-design engine when the user enables it.
Starter values are editable working inputs, not universal code values or Nigerian
National Annex defaults. In particular, a deflection pass/fail result is produced
only when an explicit project limit and its basis/provenance are supplied.

Advanced detailing still needs additional project inputs before it can be promoted
into the GUI: fatigue resistance/detail class, bearing/end-zone geometry, splice
policy, construction-stage limits, containment/project criteria and related drawing
constraints must remain explicit rather than being invented by the interface.

## Next GUI increments

1. Add construction-stage, traffic-position and girder-envelope visualisation.
2. Add full BS 5400 combination-4/5 effect import/input and governing envelope.
3. Add the advanced detailing/fatigue/bearing/splice input and results workspace.
4. Add STAAD export/import and comparison views.
5. Add calculation-report PDF/Excel export and report browser.
6. Add project-level validation messages and richer input provenance fields.
7. Add ANN/LHS/FORM/Monte-Carlo/RBDO controls after the final probabilistic study
   basis is frozen.
8. Package the tested GUI as a Windows executable after desktop acceptance tests.

A GUI result is a software calculation output, not approval of a real bridge or a
replacement for project-specific engineering review.
