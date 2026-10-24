import json
from pathlib import Path
import pytest

CAPABILITIES_FILE = Path("reports/capabilities.json")


def test_capabilities_report_format():
    """Verify reports/capabilities.json fulfills Requirement D."""
    assert CAPABILITIES_FILE.exists(), f"File {CAPABILITIES_FILE} does not exist"
    data = json.loads(CAPABILITIES_FILE.read_text(encoding="utf-8"))

    capabilities = data.get("capabilities", [])
    assert len(capabilities) >= 2, "Must contain at least two capabilities"

    seen_ids = set()
    for cap in capabilities:
        # 1. Unique ID
        cap_id = cap.get("id")
        assert cap_id, "Capability missing id"
        assert cap_id not in seen_ids, f"Duplicate capability ID '{cap_id}'"
        seen_ids.add(cap_id)

        # 2. Justification of at least 80 characters
        justification = cap.get("justification", "")
        assert len(justification) >= 80, (
            f"Justification for '{cap_id}' must be at least 80 characters (got {len(justification)}): '{justification}'"
        )

        # 3. Real repository-relative evidence path
        evidence_path = cap.get("evidence_path")
        assert evidence_path, f"Capability '{cap_id}' missing evidence_path"
        resolved_path = Path(evidence_path)
        assert resolved_path.exists(), f"Evidence path '{evidence_path}' does not exist in repository"

        # 4. Documented tested provider & limitations
        assert "tested_provider" in cap
        assert "provider_limitations" in cap
