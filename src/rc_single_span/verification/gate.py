from __future__ import annotations

from dataclasses import dataclass
from enum import Enum


class EvidenceState(str, Enum):
    NOT_STARTED = "not_started"
    INTERNAL_TESTED = "internal_tested"
    INDEPENDENTLY_CHECKED = "independently_checked"
    ACCEPTED = "accepted"


@dataclass(frozen=True)
class CapabilityEvidence:
    capability: str
    state: EvidenceState
    evidence: str

    @property
    def accepted(self) -> bool:
        return self.state is EvidenceState.ACCEPTED


@dataclass(frozen=True)
class VerificationGate:
    """Prevent an unverified capability from masquerading as accepted."""

    items: tuple[CapabilityEvidence, ...]

    @property
    def accepted(self) -> bool:
        return bool(self.items) and all(item.accepted for item in self.items)

    @property
    def blockers(self) -> tuple[str, ...]:
        return tuple(item.capability for item in self.items if not item.accepted)
