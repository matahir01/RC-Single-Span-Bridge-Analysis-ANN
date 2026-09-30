"""Framework-neutral progress and cooperative cancellation for bridge analysis."""

from collections.abc import Callable
from dataclasses import dataclass


class AnalysisCancelled(RuntimeError):
    """The caller requested that the active analysis stop without publishing results."""


@dataclass(frozen=True)
class AnalysisControl:
    callback: Callable[[str, int, int], None] | None = None
    is_cancelled: Callable[[], bool] | None = None

    def report(self, phase: str, completed: int = 0, total: int = 1) -> None:
        if self.is_cancelled is not None and self.is_cancelled():
            raise AnalysisCancelled("Analysis cancelled by user.")
        if self.callback is not None:
            self.callback(phase, completed, total)
