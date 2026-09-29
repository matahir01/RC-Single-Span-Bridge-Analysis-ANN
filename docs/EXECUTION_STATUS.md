# Execution status

Updated: 29 September 2026 (UTC)

## Pushed baseline

Latest pushed code commit before this GUI batch: `c3c3fd571ba028a46e62a1d7d046badb78e8a191`.
It selects BS EN or legacy BS 5400/BD 37 traffic/design calculations without
running the other code route. The reference runner's `both` default remains for
verification callers. Ruff passed; full suite 237 passed; new routing tests 3
passed. A seven-girder BS EN reference run using a coarse 3.0 m LM1 step
produced seven rows in 100.4 seconds. That is a performance check, not the
final 0.6 m convergence basis.

## GUI batch under verification

- Original top ribbon and focused, transactional input windows for project,
  layout, rectangular/T/I sections, deck, materials, loads, traffic and design.
- Left project tree and central live plan/cross-section schematic.
- Versioned JSON save/open with validation and no silent out-of-range clamping.
- Input-change and in-flight result invalidation; only a completed current
  analysis can populate results and the calculation report.
- PDF export of the completed run snapshot, code basis, effects, design rows,
  notes and complete input register.
- Meaningful offscreen tests cover dialog rollback, ribbon action, JSON
  round trip, invalid open rollback, stale results and PDF output.

GUI workflow tests (5), Ruff and the full suite (242 tests in 68.00 seconds) passed. This is
source verification only. No Windows executable has passed a packaged-app test.

## Research status

`docs/RESEARCH_EVIDENCE_REGISTER.md` records source editions/sections, claims,
check methods and outstanding assumptions. The example ANN configuration is
unconfirmed. DL/LL probability models, dependence, sample-size convergence,
independent ANN evaluation and RBDO numerical validation remain open. Software
verification is not approval of a real bridge.

## Exact next action

Finish the GUI suite, push the verified GUI batch, then add a Windows x64 onedir
build workflow. On a Windows runner launch the packaged EXE, run the 15 m
seven-girder reference, save/reopen JSON and produce/check a PDF. Publish the
working ZIP with a hash and instructions. Continue the evidence-gated ANN/RBDO
study after executable delivery.
