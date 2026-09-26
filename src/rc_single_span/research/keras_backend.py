from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

import numpy as np

from rc_single_span.research.dataset import DatasetSplit, ReliabilityDataset
from rc_single_span.research.surrogate import (
    MLPConfig,
    RegressionMetrics,
    Standardizer,
    regression_metrics,
)


@dataclass
class KerasSurrogate:
    """Thin adapter exposing the same prediction contract as the NumPy ANN."""

    feature_names: tuple[str, ...]
    target_names: tuple[str, ...]
    model: object
    x_scaler: Standardizer
    y_scaler: Standardizer

    def predict(self, features: np.ndarray) -> np.ndarray:
        x = np.asarray(features, dtype=float)
        one_row = x.ndim == 1
        if one_row:
            x = x.reshape(1, -1)
        if x.ndim != 2 or x.shape[1] != len(self.feature_names):
            raise ValueError("Prediction features have the wrong shape.")
        scaled = self.x_scaler.transform(x)
        prediction = np.asarray(self.model.predict(scaled, verbose=0), dtype=float)
        physical = self.y_scaler.inverse_transform(prediction)
        return physical[0] if one_row else physical

    def evaluate(self, dataset: ReliabilityDataset) -> RegressionMetrics:
        if dataset.feature_names != self.feature_names or dataset.target_names != self.target_names:
            raise ValueError("Dataset does not match Keras surrogate feature/target names.")
        return regression_metrics(dataset.targets, self.predict(dataset.features), self.target_names)

    def save(self, path: str | Path) -> Path:
        destination = Path(path)
        destination.parent.mkdir(parents=True, exist_ok=True)
        self.model.save(destination)
        scaling_path = destination.with_suffix(destination.suffix + ".scaling.npz")
        np.savez_compressed(
            scaling_path,
            x_mean=self.x_scaler.mean,
            x_scale=self.x_scaler.scale,
            y_mean=self.y_scaler.mean,
            y_scale=self.y_scaler.scale,
        )
        return destination


def train_keras_ann(
    split: DatasetSplit,
    *,
    config: MLPConfig | None = None,
) -> tuple[KerasSurrogate, object, RegressionMetrics]:
    """Train the thesis-production TensorFlow/Keras multi-output ANN.

    TensorFlow is imported lazily so deterministic-engine CI does not require the
    very large ML runtime. Install the optional ``ann`` dependency before using
    this backend.
    """

    try:
        import tensorflow as tf
    except ImportError as exc:  # pragma: no cover - optional heavy dependency
        raise RuntimeError(
            "TensorFlow is not installed. Install the project with the optional "
            "ANN dependency, e.g. pip install -e '.[ann]'."
        ) from exc

    current = config or MLPConfig()
    tf.keras.utils.set_random_seed(current.seed)
    x_scaler = Standardizer.fit(split.train.features)
    y_scaler = Standardizer.fit(split.train.targets)
    train_x = x_scaler.transform(split.train.features)
    train_y = y_scaler.transform(split.train.targets)
    validation_x = x_scaler.transform(split.validation.features)
    validation_y = y_scaler.transform(split.validation.targets)

    model = tf.keras.Sequential(name="rc_bridge_limit_state_surrogate")
    model.add(tf.keras.layers.Input(shape=(train_x.shape[1],)))
    for width in current.hidden_layers:
        model.add(tf.keras.layers.Dense(width, activation="relu"))
    model.add(tf.keras.layers.Dense(train_y.shape[1], activation="linear"))
    model.compile(
        optimizer=tf.keras.optimizers.Adam(learning_rate=current.learning_rate),
        loss="mse",
        metrics=["mae"],
    )
    callbacks = [
        tf.keras.callbacks.EarlyStopping(
            monitor="val_loss",
            patience=current.patience,
            min_delta=current.minimum_delta,
            restore_best_weights=True,
        )
    ]
    history = model.fit(
        train_x,
        train_y,
        validation_data=(validation_x, validation_y),
        epochs=current.epochs,
        batch_size=current.batch_size,
        verbose=0,
        callbacks=callbacks,
        shuffle=True,
    )
    surrogate = KerasSurrogate(
        split.train.feature_names,
        split.train.target_names,
        model,
        x_scaler,
        y_scaler,
    )
    return surrogate, history, surrogate.evaluate(split.test)
