import numpy as np

from rc_single_span.research.rbdo import (
    DesignVariable,
    ReliabilityConstraint,
    optimize_surrogate_rbdo,
)
from rc_single_span.research.sampling import RandomVariable


class _LinearSurrogate:
    feature_names = ("resistance", "load")
    target_names = ("g",)

    def predict(self, features: np.ndarray) -> np.ndarray:
        values = np.asarray(features, dtype=float)
        one = values.ndim == 1
        if one:
            values = values.reshape(1, -1)
        prediction = (values[:, 0] - values[:, 1]).reshape(-1, 1)
        return prediction[0] if one else prediction


def test_rbdo_moves_design_to_minimum_reliable_mean() -> None:
    base_variables = (
        RandomVariable("resistance", "normal", mean=100.0, cov=0.10),
        RandomVariable("load", "normal", mean=70.0, std=8.0),
    )
    result = optimize_surrogate_rbdo(
        _LinearSurrogate(),
        base_variables,
        (DesignVariable("resistance", 85.0, 130.0, 105.0),),
        (ReliabilityConstraint("g", 2.0),),
        lambda design: design["resistance"],
        maximum_iterations=40,
        form_kwargs={"maximum_iterations": 40},
    )
    assert result.success, result.message
    assert result.reliability["g"].converged
    assert result.reliability["g"].beta >= 1.999
    assert 90.0 < result.design["resistance"] < 120.0
