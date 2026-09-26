from __future__ import annotations

import csv
from dataclasses import dataclass
from pathlib import Path
from typing import Protocol

import numpy as np

from rc_single_span.research.evaluator import LimitStateEvaluation
from rc_single_span.research.sampling import RandomVariable, latin_hypercube


class DatasetEvaluator(Protocol):
    feature_names: tuple[str, ...]
    target_names: tuple[str, ...]

    def evaluate(self, sample: dict[str, float]) -> LimitStateEvaluation: ...


@dataclass(frozen=True)
class ReliabilityDataset:
    feature_names: tuple[str, ...]
    target_names: tuple[str, ...]
    features: np.ndarray
    targets: np.ndarray
    sampling_method: str = "unknown"
    seed: int | None = None
    invalid_samples: int = 0

    def __post_init__(self) -> None:
        x = np.asarray(self.features, dtype=float)
        y = np.asarray(self.targets, dtype=float)
        if x.ndim != 2 or y.ndim != 2:
            raise ValueError("Dataset features and targets must be two-dimensional.")
        if x.shape[0] != y.shape[0]:
            raise ValueError("Dataset feature/target row counts must match.")
        if x.shape[1] != len(self.feature_names):
            raise ValueError("Dataset feature column count does not match feature_names.")
        if y.shape[1] != len(self.target_names):
            raise ValueError("Dataset target column count does not match target_names.")
        if x.shape[0] == 0:
            raise ValueError("Reliability dataset cannot be empty.")
        if not np.all(np.isfinite(x)) or not np.all(np.isfinite(y)):
            raise ValueError("Reliability dataset contains non-finite values.")
        if len(set(self.feature_names + self.target_names)) != (
            len(self.feature_names) + len(self.target_names)
        ):
            raise ValueError("Dataset feature and target names must be unique.")
        if self.invalid_samples < 0:
            raise ValueError("invalid_samples cannot be negative.")
        object.__setattr__(self, "features", x)
        object.__setattr__(self, "targets", y)

    @property
    def size(self) -> int:
        return int(self.features.shape[0])

    def target_index(self, name: str) -> int:
        try:
            return self.target_names.index(name)
        except ValueError as exc:
            raise KeyError(name) from exc

    def feature_index(self, name: str) -> int:
        try:
            return self.feature_names.index(name)
        except ValueError as exc:
            raise KeyError(name) from exc

    def write_csv(self, path: str | Path) -> Path:
        destination = Path(path)
        destination.parent.mkdir(parents=True, exist_ok=True)
        with destination.open("w", newline="", encoding="utf-8") as handle:
            writer = csv.writer(handle)
            writer.writerow((*self.feature_names, *self.target_names))
            for x_row, y_row in zip(self.features, self.targets, strict=True):
                writer.writerow((*map(float, x_row), *map(float, y_row)))
        return destination

    @classmethod
    def read_csv(
        cls,
        path: str | Path,
        *,
        feature_names: tuple[str, ...],
        target_names: tuple[str, ...],
    ) -> ReliabilityDataset:
        source = Path(path)
        with source.open("r", newline="", encoding="utf-8") as handle:
            reader = csv.DictReader(handle)
            if reader.fieldnames is None:
                raise ValueError("Dataset CSV has no header.")
            required = set(feature_names + target_names)
            missing = required - set(reader.fieldnames)
            if missing:
                raise ValueError(f"Dataset CSV is missing columns: {sorted(missing)}")
            rows = list(reader)
        if not rows:
            raise ValueError("Dataset CSV contains no data rows.")
        x = np.asarray(
            [[float(row[name]) for name in feature_names] for row in rows],
            dtype=float,
        )
        y = np.asarray(
            [[float(row[name]) for name in target_names] for row in rows],
            dtype=float,
        )
        return cls(feature_names, target_names, x, y, sampling_method="csv")


@dataclass(frozen=True)
class DatasetSplit:
    train: ReliabilityDataset
    validation: ReliabilityDataset
    test: ReliabilityDataset


def generate_dataset(
    evaluator: DatasetEvaluator,
    variables: tuple[RandomVariable, ...],
    sample_count: int,
    *,
    seed: int | None = None,
    invalid_policy: str = "raise",
) -> ReliabilityDataset:
    """Generate one LHS dataset from an explicit deterministic evaluator.

    ``invalid_policy='raise'`` is the recommended research setting because it
    exposes infeasible bounds immediately. ``'skip'`` is available for exploratory
    bound-finding and records how many points were discarded.
    """

    if invalid_policy not in {"raise", "skip"}:
        raise ValueError("invalid_policy must be 'raise' or 'skip'.")
    variable_names = tuple(variable.name for variable in variables)
    if variable_names != evaluator.feature_names:
        raise ValueError(
            "Random-variable order/names must exactly match evaluator.feature_names."
        )

    samples = latin_hypercube(variables, sample_count, seed=seed)
    feature_rows: list[tuple[float, ...]] = []
    target_rows: list[tuple[float, ...]] = []
    invalid = 0

    for row_index, sample in enumerate(samples.records()):
        result = evaluator.evaluate(sample)
        if not result.valid:
            invalid += 1
            if invalid_policy == "raise":
                raise ValueError(
                    f"Invalid deterministic sample at row {row_index}: {result.message}"
                )
            continue
        feature_rows.append(tuple(sample[name] for name in evaluator.feature_names))
        target_rows.append(result.target_vector(evaluator.target_names))

    if not feature_rows:
        raise ValueError("No valid samples remain after deterministic evaluation.")
    return ReliabilityDataset(
        evaluator.feature_names,
        evaluator.target_names,
        np.asarray(feature_rows, dtype=float),
        np.asarray(target_rows, dtype=float),
        sampling_method=samples.method,
        seed=seed,
        invalid_samples=invalid,
    )


def split_dataset(
    dataset: ReliabilityDataset,
    *,
    train_fraction: float = 0.70,
    validation_fraction: float = 0.15,
    seed: int | None = None,
) -> DatasetSplit:
    """Randomly split rows once, preserving a completely held-out test set."""

    if not 0.0 < train_fraction < 1.0:
        raise ValueError("train_fraction must lie in (0, 1).")
    if not 0.0 < validation_fraction < 1.0:
        raise ValueError("validation_fraction must lie in (0, 1).")
    if train_fraction + validation_fraction >= 1.0:
        raise ValueError("Train + validation fractions must leave a positive test fraction.")
    if dataset.size < 3:
        raise ValueError("At least three rows are required to split a dataset.")

    rng = np.random.default_rng(seed)
    indices = rng.permutation(dataset.size)
    n_train = max(1, round(dataset.size * train_fraction))
    n_val = max(1, round(dataset.size * validation_fraction))
    if n_train + n_val >= dataset.size:
        n_val = max(1, dataset.size - n_train - 1)
    n_test_start = n_train + n_val
    train_idx = indices[:n_train]
    val_idx = indices[n_train:n_test_start]
    test_idx = indices[n_test_start:]

    def subset(rows: np.ndarray, label: str) -> ReliabilityDataset:
        return ReliabilityDataset(
            dataset.feature_names,
            dataset.target_names,
            dataset.features[rows],
            dataset.targets[rows],
            sampling_method=f"{dataset.sampling_method}:{label}",
            seed=seed,
        )

    return DatasetSplit(
        subset(train_idx, "train"),
        subset(val_idx, "validation"),
        subset(test_idx, "test"),
    )
