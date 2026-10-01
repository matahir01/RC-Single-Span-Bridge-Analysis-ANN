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

The reference starts at a 15 m span and seven rectangular girders. BS EN is
the initial route; BS 5400 / BD 37 is selected separately in Traffic.
Site-specific National Annex values and design criteria must be supplied and
reviewed for a real project. This application is an engineering calculation
aid and does not approve a bridge for construction.

Keep the _internal directory and all DLLs/plugins alongside the executable.
No Python installation is needed on the target Windows x64 computer.
