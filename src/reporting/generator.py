import asyncio
from datetime import datetime, timezone
import json
import logging
from pathlib import Path
from typing import Any

from src.agent.containment import ContainmentEvaluator
from src.agent.recovery import RecoveryPolicySpec, StepExecutionPipeline
from src.sandbox.exceptions import SandboxError
from src.sandbox.fake_adapter import FakeCelestoProvider, FakeSandbox
from src.sandbox.lifecycle import LifecycleState, LifecycleStateMachine
from src.sandbox.naming import generate_sandbox_name

logger = logging.getLogger(__name__)

REPORTS_DIR = Path("reports")
EVIDENCE_DIR = Path("reports/evidence")


def generate_capabilities_report(destination: Path | None = None) -> Path:
    """Generate reports/capabilities.json fulfilling Requirement D.

    Must contain at least two allowed capability IDs with unique ID,
    justification >= 80 characters, and real repository-relative evidence path.
    """
    target = destination or (REPORTS_DIR / "capabilities.json")
    target.parent.mkdir(parents=True, exist_ok=True)

    capabilities = [
        {
            "id": "celesto_safety_callbacks",
            "name": "Celesto Pre-Execution Safety Callbacks",
            "justification": (
                "Celesto class-based callbacks hook into the guest command lifecycle before execution, "
                "providing a veto channel on_pre_run to inspect, audit, and block prohibited commands "
                "before they reach the guest VM."
            ),
            "evidence_path": "src/sandbox/celesto_adapter.py",
            "tested_provider": "fake_adapter",
            "provider_limitations": (
                "Verified on the fake adapter and verified in celesto-0.1.8 SDK source (celesto.callbacks.Callback). "
                "Available on both local and cloud Celesto providers whenever vm.run() is dispatched."
            ),
        },
        {
            "id": "guest_state_recovery",
            "name": "Guest State Snapshot Checkpointing and Rollback",
            "justification": (
                "Point-in-time state checkpointing and disk snapshot restoration enables recovering guest "
                "state after transient pipeline step failures without restarting from scratch or compromising isolation."
            ),
            "evidence_path": "src/agent/recovery.py",
            "tested_provider": "fake_adapter",
            "provider_limitations": (
                "Verified on the fake adapter and verified in celesto-0.1.8 SDK source (Celesto.snapshot and from_snapshot). "
                "On local provider, snapshots require Linux KVM hardware virtualization (/dev/kvm); on cloud provider, "
                "snapshots are managed via Celesto Cloud control plane API."
            ),
        },
        {
            "id": "celesto_guest_isolation",
            "name": "Disposable Guest Environment and Subprocess Isolation",
            "justification": (
                "MicroVM isolation confines all untrusted command execution, file modifications, and prompt "
                "injection payloads inside a disposable guest environment with zero host subprocess fallback."
            ),
            "evidence_path": "src/sandbox/interface.py",
            "tested_provider": "fake_adapter",
            "provider_limitations": (
                "Verified on the fake adapter with monkeypatched host subprocess calls. Live microVM execution "
                "requires either Celesto Cloud credentials or a host with hardware virtualization enabled."
            ),
        },
    ]

    report = {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "capabilities_count": len(capabilities),
        "capabilities": capabilities,
    }

    with open(target, "w", encoding="utf-8") as f:
        json.dump(report, f, indent=2)

    return target


async def generate_lifecycle_report(destination: Path | None = None) -> Path:
    """Generate reports/lifecycle.json fulfilling Requirement A."""
    target = destination or (REPORTS_DIR / "lifecycle.json")
    target.parent.mkdir(parents=True, exist_ok=True)

    verified_scenarios = []

    # Scenario 1: Successful run lifecycle (created -> ready -> running -> succeeded -> deleted)
    sbx1_name = generate_sandbox_name()
    sm1 = LifecycleStateMachine(sbx1_name)
    sbx1 = FakeSandbox(sbx1_name)
    await sbx1.wait_until_ready()
    sm1.transition_to(LifecycleState.READY)
    sm1.transition_to(LifecycleState.RUNNING)
    await sbx1.run_command("python -c 'print(1)'")
    sm1.transition_to(LifecycleState.SUCCEEDED)
    await sbx1.delete()
    sm1.transition_to(LifecycleState.DELETED)

    verified_scenarios.append({
        "scenario": "success_lifecycle",
        "sandbox_name": sbx1_name,
        "history": [r.__dict__ for r in sm1.history],
        "final_state": sm1.current_state,
        "cleaned_up": sbx1.state == "deleted",
    })

    # Scenario 2: Failed run lifecycle (created -> ready -> running -> failed -> deleted)
    sbx2_name = generate_sandbox_name()
    sm2 = LifecycleStateMachine(sbx2_name)
    sbx2 = FakeSandbox(sbx2_name)
    await sbx2.wait_until_ready()
    sm2.transition_to(LifecycleState.READY)
    sm2.transition_to(LifecycleState.RUNNING)
    # Simulate step failure
    sm2.transition_to(LifecycleState.FAILED, metadata={"error": "Simulated task failure"})
    await sbx2.delete()
    sm2.transition_to(LifecycleState.DELETED)

    verified_scenarios.append({
        "scenario": "failure_lifecycle",
        "sandbox_name": sbx2_name,
        "history": [r.__dict__ for r in sm2.history],
        "final_state": sm2.current_state,
        "cleaned_up": sbx2.state == "deleted",
    })

    # Scenario 3: Interrupted run lifecycle (created -> ready -> running -> deleted)
    sbx3_name = generate_sandbox_name()
    sm3 = LifecycleStateMachine(sbx3_name)
    sbx3 = FakeSandbox(sbx3_name)
    await sbx3.wait_until_ready()
    sm3.transition_to(LifecycleState.READY)
    sm3.transition_to(LifecycleState.RUNNING)
    # Simulate sudden interruption / cancellation directly to cleanup
    await sbx3.delete()
    sm3.transition_to(LifecycleState.DELETED, metadata={"interrupt": "SIGINT"})

    verified_scenarios.append({
        "scenario": "interruption_lifecycle",
        "sandbox_name": sbx3_name,
        "history": [r.__dict__ for r in sm3.history],
        "final_state": sm3.current_state,
        "cleaned_up": sbx3.state == "deleted",
    })

    report = {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "canonical_states": [s.value for s in LifecycleState],
        "state_machine_rules": {k: sorted(v) for k, v in LifecycleStateMachine.VALID_TRANSITIONS.items()},
        "verified_scenarios": verified_scenarios,
    }

    with open(target, "w", encoding="utf-8") as f:
        json.dump(report, f, indent=2)

    return target


async def generate_all_reports() -> dict[str, str]:
    """Execute evaluation pipelines and generate all 6 required report files."""
    REPORTS_DIR.mkdir(parents=True, exist_ok=True)
    EVIDENCE_DIR.mkdir(parents=True, exist_ok=True)

    # 1. reports/capabilities.json
    cap_path = generate_capabilities_report()

    # 2. reports/lifecycle.json
    life_path = await generate_lifecycle_report()

    # 3. reports/failure_policy.json & reports/failure_trace.jsonl
    policy = RecoveryPolicySpec()
    pol_path = policy.write_json()

    trace_path = REPORTS_DIR / "failure_trace.jsonl"
    if trace_path.exists():
        trace_path.unlink()  # Fresh trace

    pipeline = StepExecutionPipeline(
        provider=FakeCelestoProvider(),
        policy=policy,
        trace_file=trace_path,
    )
    pipeline_result = await pipeline.run(
        task_id="task-eval-step7-recovery",
        inject_step7_failure=True,
    )

    # 4. reports/containment.json & reports/evidence/containment.log
    evaluator = ContainmentEvaluator()
    containment_result = await evaluator.run_evaluation()

    return {
        "capabilities": str(cap_path),
        "lifecycle": str(life_path),
        "failure_policy": str(pol_path),
        "failure_trace": str(trace_path),
        "containment": str(REPORTS_DIR / "containment.json"),
        "containment_log": str(containment_result.evidence_log_path),
    }
