import asyncio
import pytest
from src.agent.workflow import AgentExecutionWorkflow
from src.sandbox.exceptions import (
    CleanupFailedError,
    CommandBlockedError,
    GuestTimeoutError,
    ProviderConfigurationError,
)
from src.sandbox.factory import get_sandbox_provider
from src.sandbox.fake_adapter import FakeCelestoProvider


@pytest.mark.asyncio
async def test_workflow_successful_execution():
    """Workflow successfully provisions, executes commands, and tears down."""
    fake_provider = FakeCelestoProvider()
    workflow = AgentExecutionWorkflow(provider=fake_provider, record_ledger=False)

    summary = await workflow.execute_task(
        task_id="task-01-success",
        commands=["id", "uname -a", "pytest"],
        files={"/workspace/main.py": "print('hello world')"},
    )

    assert summary.success is True
    assert len(summary.results) == 3
    assert summary.cleaned_up is True
    assert fake_provider.created_sandboxes[0].state == "deleted"


@pytest.mark.asyncio
async def test_workflow_cleans_up_on_command_failure():
    """Workflow cleans up sandbox even if command fails."""
    fake_provider = FakeCelestoProvider()
    workflow = AgentExecutionWorkflow(provider=fake_provider, record_ledger=False)

    # Command that fails in fake (cat non_existent)
    summary = await workflow.execute_task(
        task_id="task-02-fail",
        commands=["cat /nonexistent/file.txt"],
    )

    assert summary.success is False
    assert summary.cleaned_up is True
    assert fake_provider.created_sandboxes[0].state == "deleted"


@pytest.mark.asyncio
async def test_workflow_cleans_up_on_policy_block():
    """Workflow catches CommandBlockedError and still guarantees cleanup."""
    fake_provider = FakeCelestoProvider()
    workflow = AgentExecutionWorkflow(provider=fake_provider, record_ledger=False)

    with pytest.raises(CommandBlockedError):
        await workflow.execute_task(
            task_id="task-03-blocked",
            commands=["id", "rm -rf /"],
        )

    assert len(fake_provider.created_sandboxes) == 1
    assert fake_provider.created_sandboxes[0].state == "deleted"


@pytest.mark.asyncio
async def test_workflow_cleans_up_on_readiness_timeout():
    """Workflow catches timeout and still triggers teardown."""
    fake_provider = FakeCelestoProvider(simulate_ready_timeout=True)
    workflow = AgentExecutionWorkflow(
        provider=fake_provider,
        record_ledger=False,
        ready_timeout_seconds=0.1,
    )

    with pytest.raises(GuestTimeoutError):
        await workflow.execute_task(
            task_id="task-04-timeout",
            commands=["id"],
        )

    assert len(fake_provider.created_sandboxes) == 1
    assert fake_provider.created_sandboxes[0].state == "deleted"


@pytest.mark.asyncio
async def test_workflow_makes_cleanup_failure_visible():
    """If cleanup fails, workflow records error and raises CleanupFailedError."""
    fake_provider = FakeCelestoProvider(simulate_cleanup_failure=True)
    workflow = AgentExecutionWorkflow(provider=fake_provider, record_ledger=False)

    with pytest.raises(CleanupFailedError):
        await workflow.execute_task(
            task_id="task-05-cleanfail",
            commands=["id"],
        )


def test_lazy_provider_resolution(monkeypatch):
    """Provider initialization is lazy and doesn't fail at startup."""
    # When CELESTO_PROVIDER=mock, get_sandbox_provider returns mock provider without credentials
    monkeypatch.setenv("CELESTO_PROVIDER", "mock")
    provider = get_sandbox_provider()
    assert provider.provider_name == "fake"

    # Unsupported provider raises ProviderConfigurationError
    monkeypatch.setenv("CELESTO_PROVIDER", "unsupported_provider")
    with pytest.raises(ProviderConfigurationError):
        get_sandbox_provider()
