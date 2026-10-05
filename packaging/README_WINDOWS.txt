RC Single-Span Bridge Analysis — Windows x64

1. Extract the entire RCBridgeAnalyzer-Windows-x64.zip archive.
2. Open the extracted RCBridgeAnalyzer folder and run RCBridgeAnalyzer.exe.
3. Windows SmartScreen may ask you to confirm an unsigned application. Inspect
   the source and build workflow in this repository before choosing to run it.
4. The Bridge view shows live geometry. Ribbon buttons open input dialogs.
   Set project, geometry, materials, loads and the appropriate code route.
5. In Analysis choose Quick (3 m exploratory), Standard (adaptive 2.4/1.2/0.6
   m), or Final Verification (checks 1.2 against 0.6 m). Editing the LM1
   grid selects Custom, which makes no convergence claim. The app reports
   actual phases and elapsed time. Cancel discards the partial run.
6. Run analysis, review girder results, and export the calculation sheets PDF.
   The sheets show run assumptions, substituted load/design equations, case
   IDs and bending/shear diagrams from the completed result. The nominal
   traffic moment plot is an envelope, not a signed single-case diagram.
   Save/Open use JSON project files; reopening requires a fresh analysis run.
7. The BS 5400 / BD 37 legacy route has separate editable HA, HB and HA+HB
   placement steps in Analysis. Save/Open retains the exact steps. The default
   and documented half-step values are shown beside these controls. In the
   matched 15 m fixed-station audit, default-to-half changed the girder envelope
   by 4.889% and the station-moment shape by 6.714%; the 5% station-shape
   screen fails. Half-to-fine changed them by 1.250% and 3.513%. The app flags
   the grid as unverified; see the October 5 audit in the repository. A finer
   single run is not a convergence certificate.
8. "Web limit" PASS checks maximum web resistance only. The report calculates
   required shear links, but no provided-link schedule is entered or checked;
   it does not assert complete shear reinforcement adequacy.
9. "Retain all traffic cases" keeps the physical solutions for review. It does
   not run the much more expensive combined permanent+traffic deflection search.
   Choose the separate BS 5400 combined-deflection box only when that
   all-case check is required. Its progress and Cancel are shown in Analysis.
10. ANN / Reliability opens the study workbench for sampling, ANN fitting,
    direct validation and reliability analysis. Packaged priors are explicitly
    EXPLORATORY ONLY. A completed run saves its project, configuration, dataset
    splits, model, summary and review PDF; those outputs do not close the
    research evidence gates or establish a thesis result.

The reference starts at a 15 m span and seven rectangular girders. BS EN is
the initial route; BS 5400 / BD 37 is selected separately in Traffic.
Site-specific National Annex values and design criteria must be supplied and
reviewed for a real project. This application is an engineering calculation
aid and does not approve a bridge for construction.

Keep the _internal directory and all DLLs/plugins alongside the executable.
No Python installation is needed on the target Windows x64 computer.
