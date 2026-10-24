from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Any

from src.sandbox.exceptions import SandboxError


class InvalidLifecycleTransitionError(SandboxError):
    """Raised when an illegal lifecycle state transition is attempted."""

    def __init__(self, current_state: str, attempted_state: str, sandbox_name: str | None = None) -> None:
        message = (
            f"Invalid lifecycle transition for sandbox '{sandbox_name or 'unknown'}': "
            f"cannot transition from '{current_state}' to '{attempted_state}'."
        )
        super().__init__(message)
        self.current_state = current_state
        self.attempted_state = attempted_state
        self.sandbox_name = sandbox_name


class LifecycleState(str, Enum):
    CREATED = "created"
    READY = "ready"
    RUNNING = "running"
    SUCCEEDED = "succeeded"
    FAILED = "failed"
    DELETED = "deleted"


@dataclass
class StateTransitionRecord:
    from_state: str
    to_state: str
    timestamp: str
    metadata: dict[str, Any] = field(default_factory=dict)


class LifecycleStateMachine:
    """Explicit state machine enforcing valid lifecycle transitions for sandboxes.

    Allowed transitions:
      created   -> ready, failed, deleted
      ready     -> running, failed, deleted
      running   -> succeeded, failed, deleted
      succeeded -> deleted
      failed    -> deleted
      deleted   -> (terminal state; no transitions allowed)
    """

    VALID_TRANSITIONS: dict[str, set[str]] = {
        LifecycleState.CREATED.value: {
            LifecycleState.READY.value,
            LifecycleState.FAILED.value,
            LifecycleState.DELETED.value,
        },
        LifecycleState.READY.value: {
            LifecycleState.RUNNING.value,
            LifecycleState.FAILED.value,
            LifecycleState.DELETED.value,
        },
        LifecycleState.RUNNING.value: {
            LifecycleState.SUCCEEDED.value,
            LifecycleState.FAILED.value,
            LifecycleState.DELETED.value,
        },
        LifecycleState.SUCCEEDED.value: {
            LifecycleState.DELETED.value,
        },
        LifecycleState.FAILED.value: {
            LifecycleState.DELETED.value,
        },
        LifecycleState.DELETED.value: set(),  # Terminal state
    }

    def __init__(self, sandbox_name: str, initial_state: LifecycleState | str = LifecycleState.CREATED) -> None:
        self.sandbox_name = sandbox_name
        self._current_state = initial_state.value if isinstance(initial_state, LifecycleState) else initial_state
        self.history: list[StateTransitionRecord] = [
            StateTransitionRecord(
                from_state="none",
                to_state=self._current_state,
                timestamp=datetime.now(timezone.utc).isoformat(),
                metadata={"initial": True},
            )
        ]

    @property
    def current_state(self) -> str:
        return self._current_state

    def can_transition_to(self, target_state: LifecycleState | str) -> bool:
        target = target_state.value if isinstance(target_state, LifecycleState) else target_state
        allowed = self.VALID_TRANSITIONS.get(self._current_state, set())
        return target in allowed

    def transition_to(self, target_state: LifecycleState | str, metadata: dict[str, Any] | None = None) -> StateTransitionRecord:
        target = target_state.value if isinstance(target_state, LifecycleState) else target_state
        if not self.can_transition_to(target):
            raise InvalidLifecycleTransitionError(
                current_state=self._current_state,
                attempted_state=target,
                sandbox_name=self.sandbox_name,
            )

        record = StateTransitionRecord(
            from_state=self._current_state,
            to_state=target,
            timestamp=datetime.now(timezone.utc).isoformat(),
            metadata=metadata or {},
        )
        self._current_state = target
        self.history.append(record)
        return record
