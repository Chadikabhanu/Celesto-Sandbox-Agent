import json
from pathlib import Path
import pytest
from src.agent.recovery import (
    DEFAULT_FAILURE_POLICY_FILE,
    DEFAULT_FAILURE_TRACE_FILE,
    RecoveryPolicySpec,
    StepExecutionPipeline,
)
from src.sandbox.fake_adapter import FakeCelestoProvider


@pytest.mark.asyncio
async def test_step7_deterministic_failure_and_recovery(tmp_path):
    """Verify deterministic failure at step 7, policy_applied event, and clean deletion."""
    test_trace_file = tmp_path / "test_failure_trace.jsonl"
    policy = RecoveryPolicySpec()

    pipeline = StepExecutionPipeline(
        provider=FakeCelestoProvider(),
        policy=policy,
        trace_file=test_trace_file,
    )

    result = await pipeline.run(
        task_id="task-test-step7-determinism",
        inject_step7_failure=True,
    )

    assert result.success is True
    assert result.step7_failed is True
    assert result.recovery_applied is True
    assert result.final_state == "deleted"

    # Read back and inspect the JSONL trace
    assert test_trace_file.exists()
    lines = [json.loads(line) for line in test_trace_file.read_text(encoding="utf-8").splitlines() if line.strip()]

    # 1. Verify failure at step 7 was recorded
    step7_failures = [evt for evt in lines if evt.get("step") == 7 and evt.get("status") == "failed"]
    assert len(step7_failures) == 1
    assert "Injected deterministic failure at step 7" in step7_failures[0]["error"]

    # 2. Verify trace contains event="policy_applied" with matching policy
    policy_applied_events = [evt for evt in lines if evt.get("event") == "policy_applied"]
    assert len(policy_applied_events) == 1
    applied_evt = policy_applied_events[0]
    assert applied_evt["policy"] == policy.policy_name
    assert applied_evt["action"] == policy.recovery_action
    assert "checkpoint_id" in applied_evt

    # 3. Verify step 7 completed successfully on retry attempt 2
    step7_successes = [evt for evt in lines if evt.get("step") == 7 and evt.get("status") == "completed" and evt.get("attempt") == 2]
    assert len(step7_successes) == 1

    # 4. Verify guest ended in deleted state
    cleanup_events = [evt for evt in lines if evt.get("step") == 10 and evt.get("status") == "completed"]
    assert len(cleanup_events) == 1
    assert cleanup_events[0]["final_state"] == "deleted"


def test_failure_policy_json_spec():
    """Verify reports/failure_policy.json matches the documented recovery specification."""
    policy = RecoveryPolicySpec()
    data = policy.to_dict()

    assert data["policy_name"] == "checkpoint_rollback_retry"
    assert data["total_steps"] == 10
    assert data["failure_step"] == 7
    assert data["max_retries"] >= 1
    assert data["target_environment"] == "celesto_sandbox"
    assert len(data["steps"]) == 10
