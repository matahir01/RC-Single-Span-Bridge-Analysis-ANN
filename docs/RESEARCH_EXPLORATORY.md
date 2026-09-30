# Reproducible exploratory ANN/reliability run

The input file `examples/provisional_exploratory_config.json` is a **sensitivity
scenario**, not an adopted probability model. Run it explicitly with:

```bash
python -m pip install -e '.[dev]'
python examples/run_reference_ann_reliability.py \
  examples/provisional_exploratory_config.json --exploratory \
  --output artifacts/research_exploratory
```

Use a new or empty output directory. The research Actions workflow performs
this same calculation on Python 3.11, runs the mechanism tests, and retains
the dataset, train/validation/test CSVs, trained ANN, config, summary and
hashes as a downloadable artifact. The normal runner rejects an unconfirmed
config without `--exploratory`.

| Model item | Exploratory treatment | Evidence and unresolved decision |
| --- | --- | --- |
| `fck` | JCSS C35 precast predictive-prior lognormal approximation, mean 52.25 MPa, COV 0.1099 | [JCSS concrete §3.1.5](https://www.jcss-lc.org/publications/jcsspmc/concrete.pdf). The cast deck and local production data are not separately modelled. |
| `fyk`, `As` | JCSS high-standard B500 normal 560/30 MPa; nominal cage area 12,868 mm², COV 0.02 | [JCSS reinforcing steel §3.2](https://www.jcss-lc.org/publications/jcsspmc/rebar.pdf). Actual cage and production/diameter correction need selection. |
| `d`, `b` | JCSS generic normal absolute deviations: 1.110/0.010 m and 0.4012/0.0064 m | [JCSS dimensions §3.10](https://www.jcss-lc.org/publications/jcsspmc/dimen00.pdf). Precast tolerances and cover dependence are unresolved. |
| `DL`, `LL` | Hypothetical unit-mean normal COV 0.10 and lognormal COV 0.15 | **No source supports these aggregate multipliers** for this bridge. JCSS concrete self weight does not describe all permanent actions; published Nigerian WIM axle bins lack joint vehicle records for bridge extremes. See [probabilistic basis](PROBABILISTIC_MODEL_BASIS.md). |
| Moment/shear model factors | Generic JCSS means/COVs in the input file | [JCSS model uncertainty §3.9](https://www.jcss-lc.org/publications/jcsspmc/modeluncertainties.pdf). Applicability and overlap with action variability need review. |
| Correlation | Disabled identity placeholder | No correlation data for the selected construction and traffic population. Absence of an adopted matrix is not empirical independence. |
| Bounds | None on the source priors or hypothetical multipliers | No arbitrary acceptance bounds are asserted. The stochastic evaluator rejects nonphysical samples; results must report invalid sample counts. |
| Structural response | BS EN 15 m deterministic reference at 3.0 m LM1 grid, with response scaling | This coarse search is for research exploration only. The GUI and deterministic reference use the verified 0.6 m default. No full grillage re-analysis is performed at every LHS point. |
| Limit states | Flexure, shear, gross elastic deflection with illustrative 50 mm threshold | A project deflection criterion, long-term/cracked behaviour and reinforcement links remain open. |
| Objective and target | Minimise continuous nominal `As` over 9,000–15,000 mm², subject to provisional CC2/50-year β≥3.8 for all three margins | The class/period target is editable and tied to the repo's EN 1990/JRC source; it is not a project classification. A buildable cage, construction cost and project authority criteria are unresolved. |

The 1,500-point seeded LHS uses a 70/15/15 split. Training/validation and
test files are distinct, and 250 fresh direct points are evaluated after
training. Independent LHS response checks at 500, 1,000, 1,500 and 2,000
points compare means, spread, quantiles and observed failure fractions with
a declared 5% standardized-change heuristic. This does **not** establish
rare-event tail convergence or universal adequacy of 1,500 training points.
The summary records ANN held-out and fresh error, near-zero margin counts,
FORM convergence, surrogate and direct Monte Carlo intervals, and an RBDO
candidate direct recheck with a nominal training-domain flag.

A 5,000-point direct Monte Carlo run cannot establish β=3.8: that index
corresponds to a failure probability of roughly 7.2×10⁻⁵, so the expected
failure count is below one. Even zero observed failures gives a finite upper
confidence bound. The RBDO optimizer may propose a design outside the ANN
training domain; no resulting optimum is accepted without a surrogate domain
and direct validation check. A 3.0 m grid and provisional action models also
preclude acceptance of this run as final thesis or project design evidence.
