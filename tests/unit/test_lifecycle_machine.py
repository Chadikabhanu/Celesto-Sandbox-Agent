import pytest
from src.sandbox.lifecycle import (
    InvalidLifecycleTransitionError,
    LifecycleState,
    LifecycleStateMachine,
)


def test_valid_lifecycle_success_path():
    """Verify standard happy path: created -> ready -> running -> succeeded -> deleted."""
    sm = LifecycleStateMachine("sbx-valid01", initial_state=LifecycleState.CREATED)
    assert sm.current_state == LifecycleState.CREATED.value

    sm.transition_to(LifecycleState.READY)
    assert sm.current_state == LifecycleState.READY.value

    sm.transition_to(LifecycleState.RUNNING)
    assert sm.current_state == LifecycleState.RUNNING.value

    sm.transition_to(LifecycleState.SUCCEEDED)
    assert sm.current_state == LifecycleState.SUCCEEDED.value

    sm.transition_to(LifecycleState.DELETED)
    assert sm.current_state == LifecycleState.DELETED.value


def test_valid_lifecycle_failure_path():
    """Verify failure path: created -> ready -> running -> failed -> deleted."""
    sm = LifecycleStateMachine("sbx-fail01", initial_state=LifecycleState.CREATED)
    sm.transition_to(LifecycleState.READY)
    sm.transition_to(LifecycleState.RUNNING)
    sm.transition_to(LifecycleState.FAILED, metadata={"error": "step failed"})
    assert sm.current_state == LifecycleState.FAILED.value

    sm.transition_to(LifecycleState.DELETED)
    assert sm.current_state == LifecycleState.DELETED.value


def test_valid_lifecycle_interruption_path():
    """Verify immediate cleanup on interruption from running directly to deleted."""
    sm = LifecycleStateMachine("sbx-interrupt01", initial_state=LifecycleState.CREATED)
    sm.transition_to(LifecycleState.READY)
    sm.transition_to(LifecycleState.RUNNING)
    sm.transition_to(LifecycleState.DELETED, metadata={"interrupted": True})
    assert sm.current_state == LifecycleState.DELETED.value


@pytest.mark.parametrize(
    "current, attempted",
    [
        (LifecycleState.CREATED, LifecycleState.SUCCEEDED),  # Cannot jump straight to succeeded
        (LifecycleState.CREATED, LifecycleState.RUNNING),    # Must pass through ready
        (LifecycleState.DELETED, LifecycleState.RUNNING),    # Cannot run after deleted
        (LifecycleState.DELETED, LifecycleState.READY),      # Cannot resurrect deleted
        (LifecycleState.DELETED, LifecycleState.CREATED),    # Cannot reset deleted
        (LifecycleState.SUCCEEDED, LifecycleState.RUNNING),  # Cannot re-run after succeeded
        (LifecycleState.FAILED, LifecycleState.SUCCEEDED),   # Cannot succeed after failed
    ],
)
def test_invalid_lifecycle_transitions(current, attempted):
    """Illegal transitions must raise InvalidLifecycleTransitionError."""
    sm = LifecycleStateMachine("sbx-illegal01", initial_state=current)
    with pytest.raises(InvalidLifecycleTransitionError) as exc_info:
        sm.transition_to(attempted)
    assert current.value in str(exc_info.value)
    assert attempted.value in str(exc_info.value)


def test_lifecycle_json_report_file():
    """Verify reports/lifecycle.json was generated with correct states and scenarios."""
    import json
    from pathlib import Path

    report_path = Path("reports/lifecycle.json")
    assert report_path.exists(), "reports/lifecycle.json does not exist"
    data = json.loads(report_path.read_text(encoding="utf-8"))

    # Assert canonical states are present
    states = data.get("canonical_states", [])
    for expected_state in ["created", "ready", "running", "succeeded", "failed", "deleted"]:
        assert expected_state in states

    # Assert all verified scenarios ended in deleted state and cleaned_up is True
    scenarios = data.get("verified_scenarios", [])
    assert len(scenarios) >= 3
    for sc in scenarios:
        assert sc["final_state"] == "deleted"
        assert sc["cleaned_up"] is True

