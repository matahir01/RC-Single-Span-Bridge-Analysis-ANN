from __future__ import annotations

from dataclasses import dataclass

import numpy as np


@dataclass(frozen=True)
class GaussianCopula:
    """Gaussian-copula dependence model for the research basic variables.

    The matrix is the correlation matrix in latent standard-normal space. This
    keeps marginal distribution choices explicit while allowing dependence to
    be propagated consistently through LHS, Monte Carlo and FORM transforms.
    """

    names: tuple[str, ...]
    correlation: np.ndarray

    def __post_init__(self) -> None:
        if not self.names:
            raise ValueError("Gaussian copula requires at least one variable name.")
        if len(set(self.names)) != len(self.names):
            raise ValueError("Gaussian-copula variable names must be unique.")

        matrix = np.asarray(self.correlation, dtype=float)
        dimension = len(self.names)
        if matrix.shape != (dimension, dimension):
            raise ValueError("Correlation matrix shape must match the variable-name count.")
        if not np.all(np.isfinite(matrix)):
            raise ValueError("Correlation matrix contains non-finite values.")
        if not np.allclose(matrix, matrix.T, atol=1.0e-12, rtol=0.0):
            raise ValueError("Correlation matrix must be symmetric.")
        if not np.allclose(np.diag(matrix), 1.0, atol=1.0e-12, rtol=0.0):
            raise ValueError("Correlation matrix diagonal entries must equal 1.0.")
        if np.any(np.abs(matrix) > 1.0 + 1.0e-12):
            raise ValueError("Correlation coefficients must lie in [-1, 1].")
        try:
            np.linalg.cholesky(matrix)
        except np.linalg.LinAlgError as exc:
            raise ValueError("Correlation matrix must be positive definite.") from exc
        object.__setattr__(self, "correlation", matrix)

    @property
    def cholesky(self) -> np.ndarray:
        return np.linalg.cholesky(self.correlation)

    def validate_names(self, names: tuple[str, ...]) -> None:
        if names != self.names:
            raise ValueError(
                "Gaussian-copula names/order must exactly match the random variables."
            )

    def correlate_standard_normals(self, values: np.ndarray) -> np.ndarray:
        """Map independent N(0,1) coordinates into correlated normal space."""

        array = np.asarray(values, dtype=float)
        if array.shape[-1] != len(self.names):
            raise ValueError("Standard-normal array has the wrong final dimension.")
        return np.matmul(array, self.cholesky.T)
