import pytest
import asyncpg
from src.agent.workflow import AgentExecutionWorkflow
from src.config import settings
from src.db import close_db_pool, fetch_all_runs, fetch_lifecycle_events, init_db_pool
from src.sandbox.fake_adapter import FakeCelestoProvider


@pytest.mark.asyncio
async def test_workflow_ledger_integration():
    """Verify workflow records lifecycle transitions and state updates in the trusted ledger."""
    # Connect to running Docker ledger container on localhost:5432
    dsn = "postgresql://postgres:postgres_placeholder_password@localhost:5432/celesto_ledger"
    try:
        # Initialize pool against local Docker ledger
        original_dsn = settings.DATABASE_URL
        settings.DATABASE_URL = dsn
        await init_db_pool(retries=3, delay=0.5)
    except Exception as exc:
        pytest.skip(f"Docker PostgreSQL ledger not accessible on localhost:5432: {exc}")

    try:
        provider = FakeCelestoProvider()
        workflow = AgentExecutionWorkflow(provider=provider, record_ledger=True)

        summary = await workflow.execute_task(
            task_id="task-ledger-test-01",
            commands=["id", "uname -a"],
            files={"/workspace/test.py": "assert 1 == 1\n"},
        )

        assert summary.success is True
        assert summary.cleaned_up is True

        # Query ledger runs table
        all_runs = await fetch_all_runs()
        run_record = next((r for r in all_runs if r["sandbox_name"] == summary.sandbox_name), None)
        assert run_record is not None, f"Run {summary.sandbox_name} was not recorded in runs table"
        assert run_record["state"] == "completed"
        assert run_record["task_id"] == "task-ledger-test-01"
        assert run_record["execution_target"] == "celesto_sandbox"

        # Query sandbox_events table
        events = await fetch_lifecycle_events(summary.sandbox_name)
        assert len(events) >= 3
        event_types = [e["event_type"] for e in events]
        assert "transition_to_ready" in event_types
        assert "transition_to_running" in event_types
        assert "transition_to_terminating" in event_types or "transition_to_completed" in event_types

    finally:
        await close_db_pool()
        settings.DATABASE_URL = original_dsn
