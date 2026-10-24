import pytest
from src.sandbox.exceptions import (
    CleanupFailedError,
    CommandBlockedError,
    GuestTimeoutError,
)
from src.sandbox.fake_adapter import FakeCelestoProvider, FakeSandbox
from src.sandbox.audit import read_command_audit_records


@pytest.mark.asyncio
async def test_fake_sandbox_lifecycle():
    """Verify in-memory fake sandbox implements full lifecycle cleanly."""
    provider = FakeCelestoProvider()
    sandbox = await provider.create_sandbox("sbx-faketest01")

    assert sandbox.is_fake is True
    assert sandbox.execution_target == "celesto_sandbox"
    assert sandbox.state == "provisioning"

    # Wait ready
    ready = await sandbox.wait_until_ready(timeout_seconds=5.0)
    assert ready is True
    assert sandbox.state == "ready"

    # Write file to virtual guest filesystem
    await sandbox.write_file("/workspace/hello.py", "print('hello')")
    content = await sandbox.read_file("/workspace/hello.py")
    assert content == b"print('hello')"

    # Run allowed command
    res = await sandbox.run_command("cat /workspace/hello.py")
    assert res.ok is True
    assert "print('hello')" in res.stdout

    # Clean up
    await sandbox.delete()
    assert sandbox.state == "deleted"


@pytest.mark.asyncio
async def test_fake_sandbox_blocks_prohibited_command():
    """Verify safety policy blocks prohibited commands in fake sandbox."""
    sandbox = FakeSandbox("sbx-prohibited01")
    await sandbox.wait_until_ready()

    with pytest.raises(CommandBlockedError):
        await sandbox.run_command("rm -rf /")

    # Verify audit record was written
    audit_records = read_command_audit_records()
    matching = [r for r in audit_records if r["sandbox_name"] == "sbx-prohibited01"]
    assert len(matching) >= 1
    assert matching[-1]["decision"] == "blocked"
    assert matching[-1]["command"] == "rm -rf /"
    assert matching[-1]["execution_target"] == "celesto_sandbox"


@pytest.mark.asyncio
async def test_fake_sandbox_readiness_timeout():
    """Verify bounded timeout triggers GuestTimeoutError."""
    sandbox = FakeSandbox("sbx-timeout01", simulate_ready_timeout=True)
    with pytest.raises(GuestTimeoutError):
        await sandbox.wait_until_ready(timeout_seconds=0.1)
    assert sandbox.state == "failed"


@pytest.mark.asyncio
async def test_fake_sandbox_cleanup_failure():
    """Verify simulated teardown failure raises CleanupFailedError."""
    sandbox = FakeSandbox("sbx-cleanfail01", simulate_cleanup_failure=True)
    await sandbox.wait_until_ready()
    with pytest.raises(CleanupFailedError):
        await sandbox.delete()
    assert sandbox.state == "failed"
