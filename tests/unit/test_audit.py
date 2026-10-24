from datetime import datetime
import json
from pathlib import Path
import pytest
from src.sandbox.audit import record_command_audit, read_command_audit_records


@pytest.fixture
def temp_audit_file(tmp_path):
    return tmp_path / "test_commands.jsonl"


def test_record_command_audit_fields(temp_audit_file):
    """Each audit record must contain ts, sandbox_name, command, decision, and execution_target='celesto_sandbox'."""
    record = record_command_audit(
        sandbox_name="sbx-test001122",
        command="python -m pytest",
        decision="allowed",
        log_file=temp_audit_file,
    )

    # 1. Assert return record contains all 5 mandatory fields
    assert "ts" in record
    assert record["sandbox_name"] == "sbx-test001122"
    assert record["command"] == "python -m pytest"
    assert record["decision"] == "allowed"
    assert record["execution_target"] == "celesto_sandbox"

    # 2. Assert ts is valid ISO 8601 string
    parsed_ts = datetime.fromisoformat(record["ts"])
    assert parsed_ts is not None

    # 3. Read back from file and verify JSON formatting
    records_from_file = read_command_audit_records(temp_audit_file)
    assert len(records_from_file) == 1
    stored = records_from_file[0]
    assert stored["sandbox_name"] == "sbx-test001122"
    assert stored["command"] == "python -m pytest"
    assert stored["decision"] == "allowed"
    assert stored["execution_target"] == "celesto_sandbox"


def test_record_blocked_command_in_audit(temp_audit_file):
    """Blocked commands must also be recorded in the audit log with decision='blocked'."""
    record = record_command_audit(
        sandbox_name="sbx-blocked01",
        command="rm -rf /",
        decision="blocked",
        log_file=temp_audit_file,
        extra={"reason": "Prohibited root deletion"},
    )

    assert record["decision"] == "blocked"
    assert record["command"] == "rm -rf /"
    assert record["execution_target"] == "celesto_sandbox"

    records = read_command_audit_records(temp_audit_file)
    assert len(records) == 1
    assert records[0]["decision"] == "blocked"
    assert records[0]["details"]["reason"] == "Prohibited root deletion"
