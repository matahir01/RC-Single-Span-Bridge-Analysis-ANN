from dataclasses import dataclass
from threading import Event

import numpy as np
import pytest

from rc_single_span.core.progress import AnalysisCancelled, AnalysisControl
from rc_single_span.research.dataset import generate_dataset, split_dataset
from rc_single_span.research.evaluator import LimitStateEvaluation
from rc_single_span.research.sampling import RandomVariable
from rc_single_span.research.surrogate import MLPConfig, NumpyMLPRegressor, train_numpy_ann


@dataclass
class _SyntheticEvaluator:
    feature_names: tuple[str, ...] = ("x1", "x2")
    target_names: tuple[str, ...] = ("g1", "g2")

    def evaluate(self, sample: dict[str, float]) -> LimitStateEvaluation:
        x1 = sample["x1"]
        x2 = sample["x2"]
        return LimitStateEvaluation(
            True,
            {
                "g1": 2.0 * x1 - 0.5 * x2 + 1.0,
                "g2": -1.5 * x1 + 3.0 * x2 - 2.0,
            },
        )


def test_dataset_split_and_numpy_ann_learn_multioutput_limit_states() -> None:
    variables = (
        RandomVariable("x1", "uniform", lower=-2.0, upper=2.0),
        RandomVariable("x2", "uniform", lower=-1.0, upper=3.0),
    )
    dataset = generate_dataset(_SyntheticEvaluator(), variables, 400, seed=123)
    split = split_dataset(dataset, seed=456)
    assert split.train.size + split.validation.size + split.test.size == dataset.size

    model, history, metrics = train_numpy_ann(
        split,
        config=MLPConfig(
            hidden_layers=(16, 16),
            learning_rate=2.0e-3,
            batch_size=32,
            epochs=400,
            patience=50,
            seed=99,
        ),
    )
    assert history.best_epoch > 0
    assert model.fitted
    assert min(metrics.r2) > 0.98
    prediction = model.predict(np.asarray([0.3, 1.2]))
    expected = np.asarray([2.0 * 0.3 - 0.5 * 1.2 + 1.0, -1.5 * 0.3 + 3.0 * 1.2 - 2.0])
    assert np.allclose(prediction, expected, atol=0.15)


def test_dataset_generation_reports_progress_and_stops_cooperatively() -> None:
    variables = (
        RandomVariable("x1", "uniform", lower=-2.0, upper=2.0),
        RandomVariable("x2", "uniform", lower=-1.0, upper=3.0),
    )
    cancelled = Event()
    progress: list[tuple[str, int, int]] = []

    def report(phase: str, completed: int, total: int) -> None:
        progress.append((phase, completed, total))
        cancelled.set()

    with pytest.raises(AnalysisCancelled):
        generate_dataset(
            _SyntheticEvaluator(),
            variables,
            50,
            seed=123,
            control=AnalysisControl(report, cancelled.is_set),
        )

    assert progress == [("LHS limit-state evaluations", 1, 50)]


def test_saved_ann_inference_is_identical_and_checks_feature_order(tmp_path) -> None:
    variables = (
        RandomVariable("x1", "uniform", lower=-2.0, upper=2.0),
        RandomVariable("x2", "uniform", lower=-1.0, upper=3.0),
    )
    split = split_dataset(generate_dataset(_SyntheticEvaluator(), variables, 120, seed=2))
    model, _, _ = train_numpy_ann(
        split,
        config=MLPConfig(hidden_layers=(8,), epochs=15, patience=5, seed=3),
    )
    path = model.save_npz(tmp_path / "model.npz")
    restored = NumpyMLPRegressor.load_npz(path)
    assert np.array_equal(model.predict(split.test.features), restored.predict(split.test.features))
    try:
        NumpyMLPRegressor.load_npz(path, feature_names=("x2", "x1"))
    except ValueError as exc:
        assert "Feature names" in str(exc)
    else:  # pragma: no cover
        raise AssertionError("Expected mismatched feature order to be rejected")

    with np.load(path, allow_pickle=False) as data:
        legacy_path = tmp_path / "legacy.npz"
        np.savez_compressed(
            legacy_path,
            **{key: data[key] for key in data.files if key not in {"feature_names", "target_names"}},
        )
    legacy = NumpyMLPRegressor.load_npz(
        legacy_path, feature_names=model.feature_names, target_names=model.target_names,
    )
    assert np.array_equal(model.predict(split.test.features), legacy.predict(split.test.features))
