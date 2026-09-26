from dataclasses import dataclass

from rc_single_span.research.convergence import sample_size_convergence
from rc_single_span.research.evaluator import LimitStateEvaluation
from rc_single_span.research.sampling import RandomVariable


@dataclass
class _SmoothEvaluator:
    feature_names: tuple[str, ...] = ("x", "y")
    target_names: tuple[str, ...] = ("g",)

    def evaluate(self, sample: dict[str, float]) -> LimitStateEvaluation:
        x = sample["x"]
        y = sample["y"]
        return LimitStateEvaluation(True, {"g": 3.0 + 0.5 * x - 0.25 * y})


def test_sample_size_convergence_reports_ordered_points_and_statistics() -> None:
    variables = (
        RandomVariable("x", "uniform", lower=-1.0, upper=1.0),
        RandomVariable("y", "uniform", lower=-2.0, upper=2.0),
    )
    result = sample_size_convergence(
        _SmoothEvaluator(),
        variables,
        (64, 128, 256),
        base_seed=7,
        tolerance=0.15,
    )
    assert tuple(point.sample_count for point in result.points) == (64, 128, 256)
    assert result.points[0].maximum_standardized_change is None
    assert result.points[1].maximum_standardized_change is not None
    assert result.points[-1].statistics[0].target_name == "g"
    assert result.points[-1].statistics[0].failure_fraction == 0.0
    assert result.recommended_minimum_sample_count in {128, 256, None}


def test_sample_size_convergence_rejects_unordered_sizes() -> None:
    variables = (RandomVariable("x", "uniform", lower=0.0, upper=1.0),)

    @dataclass
    class Evaluator:
        feature_names: tuple[str, ...] = ("x",)
        target_names: tuple[str, ...] = ("g",)

        def evaluate(self, sample: dict[str, float]) -> LimitStateEvaluation:
            return LimitStateEvaluation(True, {"g": sample["x"] - 0.5})

    try:
        sample_size_convergence(Evaluator(), variables, (100, 50))
    except ValueError as exc:
        assert "strictly increasing" in str(exc)
    else:  # pragma: no cover
        raise AssertionError("Expected unordered sample sizes to be rejected")
