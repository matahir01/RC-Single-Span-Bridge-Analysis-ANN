# Execution status

Updated: 29 September 2026 (UTC)

## Latest code batch

Base on main: `0d9b6e5b46deef5b8c81da6144b32414088824b3`.
The restored temporary checkout had lost the prior uncommitted drafts. The current
batch routes the GUI to only the selected BS EN or BS 5400 / BD 37 deterministic
traffic/design path. The reference runner retains its existing `both` default for
verification callers. The BS EN ANN reference script requests its own route.

Checks: Ruff passes; new route tests 3 passed; GUI smoke/design adapter tests 5
passed. A seven-girder BS EN reference run with a 3.0 m LM1 search step produced
seven rows in 100.4 seconds locally. This coarse step is a performance check,
not the final 0.6 m reference analysis or a convergence claim. Full suite: 237 passed in 66.67 seconds.

## Delivered research documentation

`docs/RESEARCH_EVIDENCE_REGISTER.md` records JCSS/JRC/Nigerian source claims,
methods and unresolved probability-model assumptions. The illustrative ANN
configuration remains unconfirmed. No thesis reliability/RBDO numerical conclusion
has been accepted yet.

## Remaining work

1. Push the selected-route code batch after the full suite passes, record its SHA.
2. Finish original ribbon dialogs, navigation tree, central bridge view, transactional
   save/open, stale-result invalidation, traceable analysis/results and PDF report.
3. Build the Windows x64 PyInstaller onedir distribution on Windows Actions. Run
   the packaged EXE itself through GUI launch, reference analysis, save/reopen and
   report output; publish the verified ZIP and SHA-256.
4. Select explicit source-backed DL/LL distributions and dependence or a labelled
   proxy, then run sample-size convergence, independent ANN validation, FORM/MC
   comparison, RBDO and direct optimum recheck. Keep approval of a real bridge
   distinct from software and research verification.

Exact next action after this batch: implement and test the ribbon input dialogs
and central workspace, then commit/push them before the Windows package batch.
