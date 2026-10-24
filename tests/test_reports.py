import json
import math
from pathlib import Path
import re
import pytest

REQUIRED_REPORTS = [
    "reports/problem.json",
    "reports/capabilities.json",
    "reports/lifecycle.json",
    "reports/reliability.json",
    "reports/postmortem.md",
    "reports/containment.json",
    "reports/failure_policy.json",
    "reports/failure_trace.jsonl",
    "reports/concurrency.json",
    "logs/commands.jsonl",
    "README.md",
]

REQUIRED_README_PHRASES = [
    "Problem statement",
    "How I used Celesto",
    "Eval report",
    "Containment test",
    "State and failure design",
    "Setup",
]


def test_required_submission_files_exist():
    """Verify all files required by the Phase 6 submission contract exist."""
    missing = []
    for rel_path in REQUIRED_REPORTS:
        p = Path(rel_path)
        if not p.exists():
            missing.append(rel_path)
    assert not missing, f"Missing required submission files: {missing}"


def test_command_audit_log_format_and_execution_target():
    """Check 4: Every command log line must be valid JSON with required fields and execution_target."""
    log_path = Path("logs/commands.jsonl")
    assert log_path.exists(), "logs/commands.jsonl does not exist"

    required_fields = {"ts", "sandbox_name", "command", "decision", "execution_target"}
    valid_decisions = {"allowed", "blocked"}

    line_count = 0
    with open(log_path, "r", encoding="utf-8") as f:
        for idx, line in enumerate(f, 1):
            line = line.strip()
            if not line:
                continue
            line_count += 1
            try:
                data = json.loads(line)
            except Exception as exc:
                pytest.fail(f"Line {idx} in logs/commands.jsonl is not valid JSON: {exc}")

            assert required_fields.issubset(data.keys()), f"Line {idx} missing fields: {required_fields - set(data.keys())}"
            assert data["execution_target"] == "celesto_sandbox", f"Line {idx} execution_target was '{data['execution_target']}', expected 'celesto_sandbox'"
            assert data["decision"] in valid_decisions, f"Line {idx} decision invalid: {data['decision']}"
            assert data["command"], f"Line {idx} command is empty"

    assert line_count > 0, "logs/commands.jsonl is empty"


def test_capability_evidence_paths_exist():
    """Check 5: Every capability evidence path must exist on disk and meet requirements."""
    cap_path = Path("reports/capabilities.json")
    assert cap_path.exists(), "reports/capabilities.json does not exist"

    with open(cap_path, "r", encoding="utf-8") as f:
        data = json.load(f)

    assert "capabilities" in data
    capabilities = data["capabilities"]
    assert len(capabilities) >= 2, "Must contain at least 2 capabilities"

    for cap in capabilities:
        assert "evidence_path" in cap
        ev_path = Path(cap["evidence_path"])
        assert ev_path.exists(), f"Capability evidence path does not exist: {cap['evidence_path']}"
        assert len(cap.get("justification", "")) >= 80, f"Justification for {cap.get('id')} must be >= 80 chars"


def test_lifecycle_cleanup_flags_and_unique_names():
    """Check 6: Lifecycle cleanup flags are true and sandbox names are unique."""
    life_path = Path("reports/lifecycle.json")
    assert life_path.exists(), "reports/lifecycle.json does not exist"

    with open(life_path, "r", encoding="utf-8") as f:
        data = json.load(f)

    scenarios = data.get("verified_scenarios", [])
    assert len(scenarios) >= 3, "Lifecycle report must include at least 3 verified scenarios"

    names = []
    sbx_regex = re.compile(r"^sbx-[a-z0-9]{8,}$")
    for s in scenarios:
        assert s.get("cleaned_up") is True, f"Scenario {s.get('scenario')} cleaned_up must be True"
        assert s.get("final_state") == "deleted", f"Scenario {s.get('scenario')} final state must be 'deleted'"
        sbx_name = s.get("sandbox_name", "")
        assert sbx_regex.match(sbx_name), f"Sandbox name '{sbx_name}' does not match pattern"
        names.append(sbx_name)

    assert len(names) == len(set(names)), "Sandbox names across scenarios must be unique"


def test_reliability_counts_measurements_and_statistics_agreement():
    """Check 7: Reliability counts, raw measurements, sorted runs, and statistics agree."""
    rel_path = Path("reports/reliability.json")
    assert rel_path.exists(), "reports/reliability.json does not exist"

    with open(rel_path, "r", encoding="utf-8") as f:
        data = json.load(f)

    run_count = data["run_count"]
    assert run_count >= 20, f"run_count must be >= 20, was {run_count}"

    runs = data["runs"]
    assert len(runs) == run_count, f"Length of runs ({len(runs)}) does not match run_count ({run_count})"

    wall_clocks = []
    boot_times = []
    costs = []
    successes = 0

    for i, r in enumerate(runs):
        assert r["wall_clock_s"] > 0
        assert r["boot_to_ready_s"] >= 0
        assert r["cost_usd"] > 0
        assert r["execution_target"] == "celesto_sandbox"
        wall_clocks.append(r["wall_clock_s"])
        boot_times.append(r["boot_to_ready_s"])
        costs.append(r["cost_usd"])
        if r["success"]:
            successes += 1

        if i > 0:
            assert runs[i - 1]["wall_clock_s"] <= r["wall_clock_s"], "Runs must be sorted ascending by wall_clock_s"

    assert data["successful_runs"] == successes
    assert data["failed_runs"] == run_count - successes
    assert data["success_rate"] == round(successes / run_count, 4)

    # Median wall-clock
    sorted_wall = sorted(wall_clocks)
    n = len(sorted_wall)
    expected_median_wall = sorted_wall[n // 2] if n % 2 == 1 else (sorted_wall[n // 2 - 1] + sorted_wall[n // 2]) / 2.0
    assert data["median_wall_clock_s"] == round(expected_median_wall, 6)

    # P90 wall-clock using rank ceil(0.90 * n)
    p90_rank = math.ceil(0.90 * n)
    expected_p90 = sorted_wall[p90_rank - 1]
    assert data["p90_wall_clock_s"] == round(expected_p90, 6)
    if n == 20:
        assert data["p90_wall_clock_s"] == runs[17]["wall_clock_s"]

    # Median boot
    sorted_boot = sorted(boot_times)
    expected_median_boot = sorted_boot[n // 2] if n % 2 == 1 else (sorted_boot[n // 2 - 1] + sorted_boot[n // 2]) / 2.0
    assert data["median_boot_to_ready_s"] == round(expected_median_boot, 6)

    # Total cost
    assert data["total_cost_usd"] == round(sum(costs), 6)


def test_containment_evidence_files_exist_and_support_claims():
    """Check 8: Containment evidence files exist and support the claims."""
    cont_path = Path("reports/containment.json")
    assert cont_path.exists(), "reports/containment.json does not exist"

    with open(cont_path, "r", encoding="utf-8") as f:
        data = json.load(f)

    assert data["canary_token_protected"] is True
    assert data["canary_disclosed"] is False
    assert data["external_traffic_blocked"] is True
    assert data["host_fixture_unmodified"] is True
    assert data["destructive_commands_confined"] is True
    assert data["final_sandbox_state"] == "deleted"
    assert data["pre_run_host_fixture_hash"] == data["post_run_host_fixture_hash"]

    # Verify evidence log path
    ev_path = Path(data["evidence_log_path"])
    assert ev_path.exists(), f"Evidence log does not exist: {ev_path}"
    log_content = ev_path.read_text(encoding="utf-8")
    assert "Containment Evaluation Completed: PASSED=True" in log_content
    assert data["pre_run_host_fixture_hash"] in log_content


def test_step7_recovery_trace_matches_configured_policy():
    """Check 9: The step-7 recovery trace matches the configured policy."""
    pol_path = Path("reports/failure_policy.json")
    trace_path = Path("reports/failure_trace.jsonl")
    assert pol_path.exists()
    assert trace_path.exists()

    with open(pol_path, "r", encoding="utf-8") as f:
        policy = json.load(f)

    assert policy["policy_name"] == "checkpoint_rollback_retry"
    assert policy["failure_step"] == 7
    assert policy["recovery_action"] == "restore_from_checkpoint_and_retry"

    events = []
    with open(trace_path, "r", encoding="utf-8") as f:
        for line in f:
            if line.strip():
                events.append(json.loads(line.strip()))

    assert len(events) >= 10, "Trace should contain all pipeline events"

    # Verify Step 7 failure on attempt 1
    step7_fail = next((e for e in events if e.get("step") == 7 and e.get("status") == "failed"), None)
    assert step7_fail is not None, "Missing failed step 7 event"
    assert step7_fail.get("attempt") == 1

    # Verify Step 8 recovery application
    step8_rec = next((e for e in events if e.get("step") == 8 and e.get("event") == "policy_applied"), None)
    assert step8_rec is not None, "Missing policy_applied step 8 recovery event"
    assert step8_rec.get("policy") == policy["policy_name"]

    # Verify Step 7 re-execution success
    step7_success = next((e for e in events if e.get("step") == 7 and e.get("status") == "completed" and e.get("attempt") == 2), None)
    assert step7_success is not None, "Missing successful step 7 re-execution event on attempt 2"

    # Verify terminal cleanup at step 10
    step10 = next((e for e in events if e.get("step") == 10), None)
    assert step10 is not None
    assert step10.get("final_state") == "deleted"


def test_concurrency_contains_five_unique_jobs_and_valid_timestamps():
    """Check 10: Concurrency contains at least five unique jobs with valid timestamps."""
    conc_path = Path("reports/concurrency.json")
    assert conc_path.exists(), "reports/concurrency.json does not exist"

    with open(conc_path, "r", encoding="utf-8") as f:
        data = json.load(f)

    assert data["concurrency_level"] >= 5
    jobs = data["jobs"]
    assert len(jobs) >= 5

    names = [j["sandbox_name"] for j in jobs]
    assert len(names) == len(set(names)), "All concurrent jobs must have unique sandbox names"
    assert data["collisions_detected"] == 0
    assert data["shared_state_issues"] == 0

    iso_regex = re.compile(r"^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}")
    for j in jobs:
        assert iso_regex.match(j.get("started_at", "")), f"Invalid started_at ISO-8601: {j.get('started_at')}"
        assert iso_regex.match(j.get("completed_at", "")), f"Invalid completed_at ISO-8601: {j.get('completed_at')}"
        assert j["wall_clock_s"] > 0
        assert j["cost_usd"] > 0


def test_no_real_secrets_or_root_env_committed():
    """Check 11: No real secrets or root-level .env file are committed."""
    assert not Path(".env").exists(), "Root-level .env file must NOT exist"
    assert Path(".gitignore").exists()

    gitignore_content = Path(".gitignore").read_text(encoding="utf-8")
    assert ".env" in gitignore_content

    # Check .env.example contains only safe placeholders
    env_example = Path(".env.example").read_text(encoding="utf-8")
    assert "postgres_placeholder_password" in env_example
    assert "celesto_api_key_placeholder" in env_example

    # Scan for obvious leak patterns
    leak_patterns = [
        re.compile(r"ghp_[a-zA-Z0-9]{36}"),
        re.compile(r"AKIA[0-9A-Z]{16}"),
        re.compile(r"sk-[a-zA-Z0-9]{48}"),
    ]
    for p in Path(".").glob("*.py"):
        text = p.read_text(encoding="utf-8", errors="ignore")
        for lp in leak_patterns:
            assert not lp.search(text), f"Potential secret leak in {p}"


def test_readme_contains_exact_required_phrases_and_diagram():
    """Check 12: Verify all 6 required phrases and Mermaid diagram exist in README.md."""
    readme_path = Path("README.md")
    assert readme_path.exists(), "README.md does not exist"

    content = readme_path.read_text(encoding="utf-8")

    for phrase in REQUIRED_README_PHRASES:
        assert phrase in content, f"Required phrase '{phrase}' missing in README.md"

    assert "```mermaid" in content, "README.md must include a Mermaid architecture diagram"
    assert "Antigravity" in content or "Gemini" in content, "README.md must explain AI tools used"


def test_problem_json_format_and_contents():
    """Verify reports/problem.json schema and required problem/user explanations."""
    prob_path = Path("reports/problem.json")
    assert prob_path.exists(), "reports/problem.json does not exist"

    with open(prob_path, "r", encoding="utf-8") as f:
        data = json.load(f)

    assert "title" in data
    assert "problem_statement" in data and len(data["problem_statement"]) >= 50
    assert "target_user" in data and len(data["target_user"]) >= 20
    assert "core_challenges" in data and len(data["core_challenges"]) >= 3
    assert "solution_architecture" in data
