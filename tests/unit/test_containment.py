import os
from pathlib import Path
import subprocess
import pytest
from src.agent.workflow import AgentExecutionWorkflow
from src.sandbox.fake_adapter import FakeCelestoProvider


@pytest.mark.asyncio
async def test_no_host_subprocess_fallback(monkeypatch):
    """The normal agent tool path cannot execute commands on the host machine.

    Monkeypatches all host subprocess execution vectors and verifies they are never called.
    """
    called_host_subprocess = []

    def fake_subprocess_run(*args, **kwargs):
        called_host_subprocess.append(("subprocess.run", args))
        raise RuntimeError("CRITICAL VIOLATION: Host subprocess.run invoked!")

    def fake_subprocess_popen(*args, **kwargs):
        called_host_subprocess.append(("subprocess.Popen", args))
        raise RuntimeError("CRITICAL VIOLATION: Host subprocess.Popen invoked!")

    def fake_os_system(*args, **kwargs):
        called_host_subprocess.append(("os.system", args))
        raise RuntimeError("CRITICAL VIOLATION: Host os.system invoked!")

    monkeypatch.setattr(subprocess, "run", fake_subprocess_run)
    monkeypatch.setattr(subprocess, "Popen", fake_subprocess_popen)
    monkeypatch.setattr(os, "system", fake_os_system)

    fake_provider = FakeCelestoProvider()
    workflow = AgentExecutionWorkflow(provider=fake_provider, record_ledger=False)

    summary = await workflow.execute_task(
        task_id="task-containment-check",
        commands=[
            "whoami",
            "uname -a",
            "pytest",
        ],
        files={"/workspace/agent_code.py": "x = 42\n"},
    )

    assert summary.success is True
    # Assert zero invocations of host subprocess functions
    assert len(called_host_subprocess) == 0, f"Host subprocess was called: {called_host_subprocess}"


@pytest.mark.asyncio
async def test_filesystem_isolation():
    """Files written by the agent inside the guest do not leak onto the host filesystem."""
    fake_provider = FakeCelestoProvider()
    workflow = AgentExecutionWorkflow(provider=fake_provider, record_ledger=False)

    guest_file_path = "/workspace/untrusted_agent_output.py"
    host_candidate_path = Path("untrusted_agent_output.py")

    assert not host_candidate_path.exists()

    summary = await workflow.execute_task(
        task_id="task-fs-isolation",
        commands=["cat /workspace/untrusted_agent_output.py"],
        files={guest_file_path: "print('untrusted code execution')\n"},
    )

    assert summary.success is True
    # Assert file does NOT exist on the host filesystem
    assert not host_candidate_path.exists()
    assert not Path(guest_file_path).exists()
