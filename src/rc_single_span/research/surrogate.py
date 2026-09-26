from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

import numpy as np

from rc_single_span.research.dataset import DatasetSplit, ReliabilityDataset


@dataclass(frozen=True)
class MLPConfig:
    hidden_layers: tuple[int, ...] = (64, 64)
    learning_rate: float = 1.0e-3
    batch_size: int = 64
    epochs: int = 1000
    patience: int = 60
    minimum_delta: float = 1.0e-7
    l2: float = 1.0e-6
    seed: int = 42

    def __post_init__(self) -> None:
        if not self.hidden_layers or any(width <= 0 for width in self.hidden_layers):
            raise ValueError("hidden_layers must contain positive widths.")
        if self.learning_rate <= 0.0:
            raise ValueError("learning_rate must be positive.")
        if min(self.batch_size, self.epochs, self.patience) <= 0:
            raise ValueError("batch_size, epochs and patience must be positive.")
        if self.minimum_delta < 0.0 or self.l2 < 0.0:
            raise ValueError("minimum_delta and l2 cannot be negative.")


@dataclass(frozen=True)
class TrainingHistory:
    train_loss: tuple[float, ...]
    validation_loss: tuple[float, ...]
    best_epoch: int
    stopped_epoch: int


@dataclass(frozen=True)
class RegressionMetrics:
    target_names: tuple[str, ...]
    rmse: tuple[float, ...]
    mae: tuple[float, ...]
    r2: tuple[float, ...]

    @property
    def mean_r2(self) -> float:
        return float(np.mean(self.r2))


@dataclass(frozen=True)
class Standardizer:
    mean: np.ndarray
    scale: np.ndarray

    @classmethod
    def fit(cls, values: np.ndarray) -> Standardizer:
        array = np.asarray(values, dtype=float)
        if array.ndim != 2 or array.shape[0] == 0:
            raise ValueError("Standardizer requires a non-empty 2D array.")
        mean = np.mean(array, axis=0)
        scale = np.std(array, axis=0, ddof=0)
        scale = np.where(scale <= 1.0e-12, 1.0, scale)
        return cls(mean, scale)

    def transform(self, values: np.ndarray) -> np.ndarray:
        return (np.asarray(values, dtype=float) - self.mean) / self.scale

    def inverse_transform(self, values: np.ndarray) -> np.ndarray:
        return np.asarray(values, dtype=float) * self.scale + self.mean


def regression_metrics(
    truth: np.ndarray,
    prediction: np.ndarray,
    target_names: tuple[str, ...],
) -> RegressionMetrics:
    y = np.asarray(truth, dtype=float)
    p = np.asarray(prediction, dtype=float)
    if y.shape != p.shape or y.ndim != 2:
        raise ValueError("Truth/prediction arrays must have the same 2D shape.")
    if y.shape[1] != len(target_names):
        raise ValueError("target_names do not match regression output columns.")
    error = p - y
    rmse = np.sqrt(np.mean(error * error, axis=0))
    mae = np.mean(np.abs(error), axis=0)
    ss_res = np.sum(error * error, axis=0)
    centred = y - np.mean(y, axis=0)
    ss_tot = np.sum(centred * centred, axis=0)
    r2 = np.where(ss_tot > 1.0e-15, 1.0 - ss_res / ss_tot, 1.0)
    return RegressionMetrics(
        target_names,
        tuple(map(float, rmse)),
        tuple(map(float, mae)),
        tuple(map(float, r2)),
    )


class NumpyMLPRegressor:
    """Small deterministic multi-output ANN with Adam and early stopping.

    This backend keeps the repository's core CI lightweight. A TensorFlow/Keras
    adapter is provided separately for thesis production runs, while this model
    gives the same pipeline a dependency-light ANN implementation for regression
    tests and reproducible CPU experiments.
    """

    def __init__(
        self,
        feature_names: tuple[str, ...],
        target_names: tuple[str, ...],
        *,
        config: MLPConfig | None = None,
    ) -> None:
        if not feature_names or not target_names:
            raise ValueError("ANN requires at least one feature and one target.")
        self.feature_names = feature_names
        self.target_names = target_names
        self.config = config or MLPConfig()
        self.x_scaler: Standardizer | None = None
        self.y_scaler: Standardizer | None = None
        self.weights: list[np.ndarray] = []
        self.biases: list[np.ndarray] = []
        self.history: TrainingHistory | None = None

    @staticmethod
    def _relu(value: np.ndarray) -> np.ndarray:
        return np.maximum(value, 0.0)

    @staticmethod
    def _relu_gradient(value: np.ndarray) -> np.ndarray:
        return (value > 0.0).astype(float)

    def _initialise(self, input_count: int, output_count: int) -> None:
        rng = np.random.default_rng(self.config.seed)
        widths = (input_count, *self.config.hidden_layers, output_count)
        self.weights = []
        self.biases = []
        for left, right in zip(widths[:-1], widths[1:], strict=True):
            scale = np.sqrt(2.0 / left)
            self.weights.append(rng.normal(0.0, scale, size=(left, right)))
            self.biases.append(np.zeros((1, right), dtype=float))

    def _forward(
        self,
        x: np.ndarray,
    ) -> tuple[np.ndarray, list[np.ndarray], list[np.ndarray]]:
        activations = [x]
        preactivations: list[np.ndarray] = []
        current = x
        for index, (weight, bias) in enumerate(zip(self.weights, self.biases, strict=True)):
            z = current @ weight + bias
            preactivations.append(z)
            current = z if index == len(self.weights) - 1 else self._relu(z)
            activations.append(current)
        return current, activations, preactivations

    def _loss(self, prediction: np.ndarray, truth: np.ndarray) -> float:
        mse = float(np.mean((prediction - truth) ** 2))
        penalty = self.config.l2 * sum(float(np.sum(weight * weight)) for weight in self.weights)
        return mse + penalty

    def fit(
        self,
        train_x: np.ndarray,
        train_y: np.ndarray,
        validation_x: np.ndarray,
        validation_y: np.ndarray,
    ) -> TrainingHistory:
        x = np.asarray(train_x, dtype=float)
        y = np.asarray(train_y, dtype=float)
        vx = np.asarray(validation_x, dtype=float)
        vy = np.asarray(validation_y, dtype=float)
        if x.ndim != 2 or y.ndim != 2 or vx.ndim != 2 or vy.ndim != 2:
            raise ValueError("ANN train/validation inputs must be two-dimensional.")
        if x.shape[0] != y.shape[0] or vx.shape[0] != vy.shape[0]:
            raise ValueError("ANN feature/target row counts must match.")
        if x.shape[1] != len(self.feature_names) or y.shape[1] != len(self.target_names):
            raise ValueError("ANN train arrays do not match feature/target names.")
        if vx.shape[1] != x.shape[1] or vy.shape[1] != y.shape[1]:
            raise ValueError("ANN validation dimensions must match training dimensions.")
        if x.shape[0] == 0 or vx.shape[0] == 0:
            raise ValueError("ANN requires non-empty train and validation sets.")

        self.x_scaler = Standardizer.fit(x)
        self.y_scaler = Standardizer.fit(y)
        xs = self.x_scaler.transform(x)
        ys = self.y_scaler.transform(y)
        vxs = self.x_scaler.transform(vx)
        vys = self.y_scaler.transform(vy)
        self._initialise(xs.shape[1], ys.shape[1])

        mw = [np.zeros_like(weight) for weight in self.weights]
        vw = [np.zeros_like(weight) for weight in self.weights]
        mb = [np.zeros_like(bias) for bias in self.biases]
        vb = [np.zeros_like(bias) for bias in self.biases]
        beta1 = 0.9
        beta2 = 0.999
        epsilon = 1.0e-8
        step = 0
        rng = np.random.default_rng(self.config.seed + 1)
        best_validation = float("inf")
        best_epoch = 0
        best_weights = [weight.copy() for weight in self.weights]
        best_biases = [bias.copy() for bias in self.biases]
        stale = 0
        train_losses: list[float] = []
        validation_losses: list[float] = []

        for epoch in range(1, self.config.epochs + 1):
            permutation = rng.permutation(xs.shape[0])
            for start in range(0, xs.shape[0], self.config.batch_size):
                batch = permutation[start : start + self.config.batch_size]
                xb = xs[batch]
                yb = ys[batch]
                prediction, activations, preactivations = self._forward(xb)
                grad = 2.0 * (prediction - yb) / prediction.size
                grad_w = [np.zeros_like(weight) for weight in self.weights]
                grad_b = [np.zeros_like(bias) for bias in self.biases]

                for layer in range(len(self.weights) - 1, -1, -1):
                    grad_w[layer] = activations[layer].T @ grad + 2.0 * self.config.l2 * self.weights[layer]
                    grad_b[layer] = np.sum(grad, axis=0, keepdims=True)
                    if layer > 0:
                        grad = (grad @ self.weights[layer].T) * self._relu_gradient(
                            preactivations[layer - 1]
                        )

                step += 1
                for layer in range(len(self.weights)):
                    mw[layer] = beta1 * mw[layer] + (1.0 - beta1) * grad_w[layer]
                    vw[layer] = beta2 * vw[layer] + (1.0 - beta2) * grad_w[layer] ** 2
                    mb[layer] = beta1 * mb[layer] + (1.0 - beta1) * grad_b[layer]
                    vb[layer] = beta2 * vb[layer] + (1.0 - beta2) * grad_b[layer] ** 2
                    mw_hat = mw[layer] / (1.0 - beta1**step)
                    vw_hat = vw[layer] / (1.0 - beta2**step)
                    mb_hat = mb[layer] / (1.0 - beta1**step)
                    vb_hat = vb[layer] / (1.0 - beta2**step)
                    self.weights[layer] -= self.config.learning_rate * mw_hat / (
                        np.sqrt(vw_hat) + epsilon
                    )
                    self.biases[layer] -= self.config.learning_rate * mb_hat / (
                        np.sqrt(vb_hat) + epsilon
                    )

            train_prediction, _, _ = self._forward(xs)
            validation_prediction, _, _ = self._forward(vxs)
            train_loss = self._loss(train_prediction, ys)
            validation_loss = self._loss(validation_prediction, vys)
            train_losses.append(train_loss)
            validation_losses.append(validation_loss)

            if validation_loss < best_validation - self.config.minimum_delta:
                best_validation = validation_loss
                best_epoch = epoch
                best_weights = [weight.copy() for weight in self.weights]
                best_biases = [bias.copy() for bias in self.biases]
                stale = 0
            else:
                stale += 1
                if stale >= self.config.patience:
                    break

        self.weights = best_weights
        self.biases = best_biases
        self.history = TrainingHistory(
            tuple(train_losses),
            tuple(validation_losses),
            best_epoch=best_epoch,
            stopped_epoch=len(train_losses),
        )
        return self.history

    def fit_split(self, split: DatasetSplit) -> TrainingHistory:
        if split.train.feature_names != self.feature_names or split.train.target_names != self.target_names:
            raise ValueError("Dataset split does not match ANN feature/target names.")
        return self.fit(
            split.train.features,
            split.train.targets,
            split.validation.features,
            split.validation.targets,
        )

    @property
    def fitted(self) -> bool:
        return bool(self.weights) and self.x_scaler is not None and self.y_scaler is not None

    def predict(self, features: np.ndarray) -> np.ndarray:
        if not self.fitted:
            raise RuntimeError("ANN must be fitted before prediction.")
        x = np.asarray(features, dtype=float)
        one_row = x.ndim == 1
        if one_row:
            x = x.reshape(1, -1)
        if x.ndim != 2 or x.shape[1] != len(self.feature_names):
            raise ValueError("Prediction features have the wrong shape.")
        assert self.x_scaler is not None and self.y_scaler is not None
        prediction, _, _ = self._forward(self.x_scaler.transform(x))
        physical = self.y_scaler.inverse_transform(prediction)
        return physical[0] if one_row else physical

    def evaluate(self, dataset: ReliabilityDataset) -> RegressionMetrics:
        if dataset.feature_names != self.feature_names or dataset.target_names != self.target_names:
            raise ValueError("Dataset does not match ANN feature/target names.")
        return regression_metrics(dataset.targets, self.predict(dataset.features), self.target_names)

    def save_npz(self, path: str | Path) -> Path:
        if not self.fitted:
            raise RuntimeError("Cannot save an unfitted ANN.")
        assert self.x_scaler is not None and self.y_scaler is not None
        destination = Path(path)
        destination.parent.mkdir(parents=True, exist_ok=True)
        payload: dict[str, np.ndarray] = {
            "x_mean": self.x_scaler.mean,
            "x_scale": self.x_scaler.scale,
            "y_mean": self.y_scaler.mean,
            "y_scale": self.y_scaler.scale,
            "hidden_layers": np.asarray(self.config.hidden_layers, dtype=int),
        }
        for index, (weight, bias) in enumerate(zip(self.weights, self.biases, strict=True)):
            payload[f"weight_{index}"] = weight
            payload[f"bias_{index}"] = bias
        np.savez_compressed(destination, **payload)
        return destination


def train_numpy_ann(
    split: DatasetSplit,
    *,
    config: MLPConfig | None = None,
) -> tuple[NumpyMLPRegressor, TrainingHistory, RegressionMetrics]:
    model = NumpyMLPRegressor(
        split.train.feature_names,
        split.train.target_names,
        config=config,
    )
    history = model.fit_split(split)
    test_metrics = model.evaluate(split.test)
    return model, history, test_metrics
