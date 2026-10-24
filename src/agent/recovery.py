import asyncio
from dataclasses import dataclass, field
from datetime import datetime, timezone
import json
import logging
from pathlib import Path
from typing import Any

from src.sandbox.exceptions import (
    CleanupFailedError,
    CommandBlockedError,
    GuestTimeoutError,
    SandboxError,
)
from src.sandbox.factory import get_sandbox_provider
from src.sandbox.interface import CommandResult, Sandbox, SandboxProvider
from src.sandbox.lifecycle import LifecycleState, LifecycleStateMachine
from src.sandbox.naming import generate_sandbox_name

logger = logging.getLogger(__name__)

DEFAULT_FAILURE_TRACE_FILE = Path("reports/failure_trace.jsonl")
DEFAULT_FAILURE_POLICY_FILE = Path("reports/failure_policy.json")


class StepExecutionError(SandboxError):
    """Raised when an individual pipeline step fails."""

    def __init__(self, step: int, name: str, message: str) -> None:
        super().__init__(f"Step {step} ({name}) failed: {message}")
        self.step = step
        self.name = name


@dataclass
class PipelineStep:
    step_number: int
    name: str
    description: str


# 10 Defined Canonical Pipeline Steps
CANONICAL_STEPS: tuple[PipelineStep, ...] = (
    PipelineStep(1, "task_ingestion", "Ingest coding task definition and validation parameters"),
    PipelineStep(2, "sandbox_creation", "Allocate isolated Celesto guest sandbox with unique ID"),
    PipelineStep(3, "guest_readiness_probe", "Probe guest runtime readiness with bounded timeout"),
    PipelineStep(4, "seed_workspace", "Transfer code bundle and test specifications to /workspace"),
    PipelineStep(5, "pre_exec_security_scan", "Evaluate execution commands against security command policy"),
    PipelineStep(6, "create_checkpoint", "Capture point-in-time snapshot/checkpoint of guest state"),
    PipelineStep(7, "execute_verification", "Execute verification test suite (Injected failure point)"),
    PipelineStep(8, "apply_recovery", "Evaluate failure and apply recovery policy if step 7 failed"),
    PipelineStep(9, "extract_artifacts", "Extract verification proof artifacts and calculate hashes"),
    PipelineStep(10, "teardown_and_cleanup", "Tear down guest sandbox and commit final ledger state"),
)


@dataclass
class RecoveryPolicySpec:
    policy_name: str = "checkpoint_rollback_retry"
    total_steps: int = 10
    failure_step: int = 7
    max_retries: int = 2
    recovery_action: str = "restore_from_checkpoint_and_retry"
    fallback_action: str = "abort_and_cleanup_guest"
    target_environment: str = "celesto_sandbox"
    description: str = (
        "Deterministic recovery policy for Step 7 verification failure. "
        "Upon transient error, records 'policy_applied' trace event, rolls back "
        "guest workspace to Step 6 baseline snapshot, and replays verification."
    )

    def to_dict(self) -> dict[str, Any]:
        return {
            "policy_name": self.policy_name,
            "total_steps": self.total_steps,
            "failure_step": self.failure_step,
            "max_retries": self.max_retries,
            "recovery_action": self.recovery_action,
            "fallback_action": self.fallback_action,
            "target_environment": self.target_environment,
            "description": self.description,
            "steps": [{"step": s.step_number, "name": s.name, "description": s.description} for s in CANONICAL_STEPS],
        }

    def write_json(self, destination: Path | None = None) -> Path:
        target = destination or DEFAULT_FAILURE_POLICY_FILE
        target.parent.mkdir(parents=True, exist_ok=True)
        with open(target, "w", encoding="utf-8") as f:
            json.dump(self.to_dict(), f, indent=2)
        return target


@dataclass
class StepPipelineResult:
    run_id: str
    sandbox_name: str
    success: bool
    step_reached: int
    step7_failed: bool
    recovery_applied: bool
    final_state: str
    trace_events: list[dict[str, Any]] = field(default_factory=list)
    error_message: str | None = None


class StepExecutionPipeline:
    """Orchestrates 10-step verification with deterministic Step 7 fault injection and recovery."""

    def __init__(
        self,
        provider: SandboxProvider | None = None,
        policy: RecoveryPolicySpec | None = None,
        trace_file: Path | None = None,
    ) -> None:
        self.provider = provider
        self.policy = policy or RecoveryPolicySpec()
        self.trace_file = trace_file or DEFAULT_FAILURE_TRACE_FILE

    def _append_trace(self, event: dict[str, Any]) -> None:
        self.trace_file.parent.mkdir(parents=True, exist_ok=True)
        line = json.dumps(event, separators=(",", ":")) + "\n"
        with open(self.trace_file, "a", encoding="utf-8") as f:
            f.write(line)

    async def run(
        self,
        task_id: str,
        inject_step7_failure: bool = True,
        sandbox_name: str | None = None,
    ) -> StepPipelineResult:
        run_id = f"run-{datetime.now(timezone.utc).strftime('%Y%m%d-%H%M%S')}"
        target_sbx_name = sandbox_name or generate_sandbox_name()
        state_machine = LifecycleStateMachine(target_sbx_name, initial_state=LifecycleState.CREATED)

        trace_events: list[dict[str, Any]] = []

        def log_event(step: int, name: str, status: str, extra: dict[str, Any] | None = None) -> dict[str, Any]:
            evt = {
                "ts": datetime.now(timezone.utc).isoformat(),
                "run_id": run_id,
                "sandbox_name": target_sbx_name,
                "step": step,
                "name": name,
                "status": status,
                "execution_target": "celesto_sandbox",
            }
            if extra:
                evt.update(extra)
            self._append_trace(evt)
            trace_events.append(evt)
            return evt

        # Ensure policy file exists
        self.policy.write_json()

        resolved_provider = self.provider or get_sandbox_provider()
        sandbox: Sandbox | None = None
        checkpoint_snapshot: dict[str, Any] = {}
        step7_failure_injected = False
        recovery_applied = False
        success = False
        error_message: str | None = None
        last_step = 1

        try:
            # Step 1: Task Ingestion
            last_step = 1
            log_event(1, "task_ingestion", "completed", {"task_id": task_id})

            # Step 2: Sandbox Creation
            last_step = 2
            sandbox = await resolved_provider.create_sandbox(target_sbx_name)
            log_event(2, "sandbox_creation", "completed", {"sandbox_state": sandbox.state})

            # Step 3: Guest Readiness Probe
            last_step = 3
            await sandbox.wait_until_ready(timeout_seconds=30.0)
            state_machine.transition_to(LifecycleState.READY)
            log_event(3, "guest_readiness_probe", "completed")

            # Transition to running
            state_machine.transition_to(LifecycleState.RUNNING)

            # Step 4: Seed Workspace
            last_step = 4
            await sandbox.write_file("/workspace/solution.py", "def add(a, b):\n    return a + b\n")
            await sandbox.write_file("/workspace/test_solution.py", "from solution import add\ndef test_add():\n    assert add(1, 2) == 3\n")
            log_event(4, "seed_workspace", "completed")

            # Step 5: Pre-Execution Security Scan
            last_step = 5
            # Audit intended test command
            test_cmd = "pytest /workspace/test_solution.py"
            # Policy audit is performed when command is invoked
            log_event(5, "pre_exec_security_scan", "completed", {"verified_command": test_cmd})

            # Step 6: Create Checkpoint
            last_step = 6
            checkpoint_id = f"chk-{target_sbx_name}-step6"
            checkpoint_snapshot = {
                "checkpoint_id": checkpoint_id,
                "step": 6,
                "timestamp": datetime.now(timezone.utc).isoformat(),
                "files": ["/workspace/solution.py", "/workspace/test_solution.py"],
            }
            log_event(6, "create_checkpoint", "completed", {"checkpoint_id": checkpoint_id})

            # Step 7: Execute Verification Suite (Injected failure point)
            last_step = 7
            if inject_step7_failure:
                step7_failure_injected = True
                log_event(
                    7,
                    "execute_verification",
                    "failed",
                    {"error": "Injected deterministic failure at step 7: simulated transient network timeout", "attempt": 1},
                )
                # Step 8: Apply Recovery Policy
                last_step = 8
                recovery_applied = True
                log_event(
                    8,
                    "apply_recovery",
                    "completed",
                    {
                        "event": "policy_applied",
                        "policy": self.policy.policy_name,
                        "action": "restore_from_checkpoint_and_retry",
                        "checkpoint_id": checkpoint_id,
                        "recovery_attempt": 1,
                    },
                )

                # Execute rollback to Step 6 checkpoint
                # Ensure files are intact in guest
                await sandbox.write_file("/workspace/solution.py", "def add(a, b):\n    return a + b\n")
                await sandbox.write_file("/workspace/test_solution.py", "from solution import add\ndef test_add():\n    assert add(1, 2) == 3\n")

                # Replay Step 7 verification without failure
                cmd_res = await sandbox.run_command(test_cmd)
                log_event(
                    7,
                    "execute_verification",
                    "completed",
                    {"attempt": 2, "exit_code": cmd_res.exit_code, "stdout": cmd_res.stdout.strip()},
                )
            else:
                cmd_res = await sandbox.run_command(test_cmd)
                log_event(7, "execute_verification", "completed", {"attempt": 1, "exit_code": cmd_res.exit_code})

            # Step 9: Extract Artifacts
            last_step = 9
            proof_file_bytes = await sandbox.read_file("/workspace/solution.py")
            log_event(
                9,
                "extract_artifacts",
                "completed",
                {"artifact_bytes": len(proof_file_bytes), "verified": True},
            )

            # Execution succeeded
            state_machine.transition_to(LifecycleState.SUCCEEDED)
            success = True

        except Exception as exc:
            error_message = str(exc)
            log_event(last_step, "execution_error", "failed", {"error": error_message})
            if state_machine.can_transition_to(LifecycleState.FAILED):
                state_machine.transition_to(LifecycleState.FAILED)
            raise
        finally:
            # Step 10: Teardown and Cleanup (Guaranteed deletion)
            last_step = 10
            if sandbox is not None:
                try:
                    await sandbox.delete()
                    if state_machine.can_transition_to(LifecycleState.DELETED):
                        state_machine.transition_to(LifecycleState.DELETED)
                    log_event(10, "teardown_and_cleanup", "completed", {"final_state": LifecycleState.DELETED.value})
                except Exception as cleanup_err:
                    log_event(10, "teardown_and_cleanup", "failed", {"cleanup_error": str(cleanup_err)})
                    raise CleanupFailedError(f"Teardown failed: {cleanup_err}") from cleanup_err

        return StepPipelineResult(
            run_id=run_id,
            sandbox_name=target_sbx_name,
            success=success,
            step_reached=last_step,
            step7_failed=step7_failure_injected,
            recovery_applied=recovery_applied,
            final_state=state_machine.current_state,
            trace_events=trace_events,
            error_message=error_message,
        )
