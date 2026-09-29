# Execution status

Updated: 29 September 2026 (UTC)

## Latest verified commits

- `c3c3fd571ba028a46e62a1d7d046badb78e8a191`: selected-code route;
  full suite 237 passed, Ruff passed. Coarse 3.0 m BS EN performance check
  ran the seven-girder reference in 100.4 seconds. This is not the final
  0.6 m convergence basis.
- `ccdb9843ac948609e30bad5cf75172ee8ad160d6`: ribbon input dialogs,
  original bridge workspace and project tree, JSON round trip, stale-result
  invalidation and PDF calculation report. Ruff and 242 tests passed; offscreen
  screenshot inspected. No Windows executable has passed its package test yet.

## Windows packaging batch

PyInstaller onedir spec, Windows x64 Actions build, bundled Qt plugin check,
packaged-EXE smoke mode and use instructions have been added locally. Linux
PyInstaller 6.22.3 built the onedir package and included Qt platform and print
plugins. Source GUI tests passed. A full default 0.6 m BS EN reference smoke
run remains in progress locally; Ruff and the full suite (242 tests in 74.53 seconds) passed. **The Windows executable ZIP is
not delivered until the Windows CI packaged-app test succeeds.**

Exact next action: push this batch to trigger Windows Actions, inspect its
build/packaged smoke result, fix failures, then publish the tested ZIP, SHA-256
and concise use instructions. Record the tested commit and artifact link here.

## Research status

`docs/RESEARCH_EVIDENCE_REGISTER.md` records source editions/sections, claims,
check methods and outstanding assumptions. The illustrative ANN configuration
remains unconfirmed. Select source-backed DL/LL probability models, dependence,
and sample size before training; independently evaluate held-out and near-limit
ANN results, cross-check FORM/direct MC and re-evaluate the RBDO optimum.
Software verification is separate from research acceptance and real-bridge
approval. National Annex values must remain explicit project choices.
