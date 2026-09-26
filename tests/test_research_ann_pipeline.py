from dataclasses import dataclass

import numpy as np

from rc_single_span.research.dataset import generate_dataset, split_dataset
from rc_single_span.research.evaluator import LimitStateEvaluation
from rc_single_span.research.sampling import RandomVariable
from rc_single_span.research.surrogate import MLPConfig, train_numpy_ann


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
