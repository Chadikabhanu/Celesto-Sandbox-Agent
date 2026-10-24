import json
import math
from pathlib import Path
import re
import pytest
from src.evaluation.runner import EvaluationRunner, RunRecord
from src.evaluation.stats import (
    COST_MODEL_NAME,
    calculate_median,
    calculate_p90,
    calculate_success_rate,
    estimate_run_cost_usd,
)
from src.sandbox.fake_adapter import FakeCelestoProvider


def test_calculate_median_odd_and_even():
    """Verify median calculation correctly handles odd, even, single, and empty lists."""
    assert calculate_median([]) == 0.0
    assert calculate_median([42.0]) == 42.0

    # Odd count: middle element
    assert calculate_median([1.0, 5.0, 3.0]) == 3.0
    assert calculate_median([10.0, 20.0, 30.0, 40.0, 50.0]) == 30.0

    # Even count: average of two middle elements
    assert calculate_median([1.0, 2.0, 3.0, 4.0]) == 2.5
    assert calculate_median([10.0, 20.0]) == 15.0

    # Even count with identical middle elements
    assert calculate_median([5.0, 5.0, 5.0, 5.0]) == 5.0


def test_calculate_p90_ceil_rank():
    """Verify p90 calculation uses rank ceil(0.90 * n).

    For exactly 20 values, rank = ceil(18.0) = 18 (1-indexed), which must yield
    the 18th sorted value (index 17 in 0-indexed list).
    """
    assert calculate_p90([]) == 0.0

    # Exactly 20 sorted values: 1.0, 2.0, ..., 20.0
    vals_20 = [float(i) for i in range(1, 21)]
    assert calculate_p90(vals_20) == 18.0

    # 10 values: rank = ceil(9.0) = 9th value
    vals_10 = [float(i) for i in range(1, 11)]
    assert calculate_p90(vals_10) == 9.0

    # Unsorted 20 values
    import random
    rng = random.Random(42)
    shuffled_20 = list(vals_20)
    rng.shuffle(shuffled_20)
    assert calculate_p90(shuffled_20) == 18.0


def test_calculate_success_rate():
    """Verify success rate computation and edge cases."""
    assert calculate_success_rate(0, 0) == 0.0
    assert calculate_success_rate(20, 20) == 1.0
    assert calculate_success_rate(19, 20) == 0.95
    assert calculate_success_rate(18, 20) == 0.90
    assert calculate_success_rate(0, 20) == 0.0


def test_cost_model_documented_estimates():
    """Verify reproducible cost calculation using documented Celesto rates."""
    assert estimate_run_cost_usd(0.0) == 0.00005  # Base ephemeral disk provisioning
    # 3600 seconds = 1 hour = $0.05 compute + $0.00005 disk = $0.05005
    assert estimate_run_cost_usd(3600.0) == 0.05005
    assert COST_MODEL_NAME == "celesto_microvm_tier1_estimate_0.05_usd_per_hour"


@pytest.mark.asyncio
async def test_evaluation_resumption_without_fabrication(tmp_path: Path):
    """Verify evaluation runner resumes incomplete runs without fabricating missing results."""
    reports_dir = tmp_path / "reports"
    cache_dir = tmp_path / "cache"

    provider = FakeCelestoProvider()
    runner = EvaluationRunner(provider=provider, reports_dir=reports_dir, cache_dir=cache_dir)

    # 1. Run first batch of 5 runs
    first_report = await runner.run_reliability_evaluation(target_runs=5, resume=False)
    assert first_report["run_count"] == 5
    assert len(provider.created_sandboxes) == 5

    # Verify cache contains exactly 5 raw records
    cache_file = cache_dir / "reliability_raw.jsonl"
    assert cache_file.exists()
    with open(cache_file, "r", encoding="utf-8") as f:
        lines = [line.strip() for line in f if line.strip()]
    assert len(lines) == 5

    # 2. Resume to complete 10 runs
    second_report = await runner.run_reliability_evaluation(target_runs=10, resume=True)
    assert second_report["run_count"] == 10
    # Exactly 5 additional sandboxes created, not 10
    assert len(provider.created_sandboxes) == 10

    # Verify cache now contains exactly 10 raw records
    with open(cache_file, "r", encoding="utf-8") as f:
        resumed_lines = [line.strip() for line in f if line.strip()]
    assert len(resumed_lines) == 10


def test_reliability_report_schema_and_independent_statistics():
    """Load reports/reliability.json, validate schema and independently recompute all statistics."""
    report_path = Path("reports/reliability.json")
    if not report_path.exists():
        pytest.skip("reports/reliability.json does not exist yet. Run evaluation first.")

    with open(report_path, "r", encoding="utf-8") as f:
        report = json.load(f)

    # 1. Top-level schema validations
    required_keys = {
        "generated_at",
        "provider",
        "is_mock_run",
        "cost_model",
        "is_cost_estimated",
        "environment_notes",
        "run_count",
        "successful_runs",
        "failed_runs",
        "success_rate",
        "median_wall_clock_s",
        "p90_wall_clock_s",
        "median_boot_to_ready_s",
        "total_cost_usd",
        "runs",
    }
    assert required_keys.issubset(report.keys())
    assert report["run_count"] >= 20
    assert len(report["runs"]) == report["run_count"]

    # 2. Honest provider labeling
    assert isinstance(report["is_mock_run"], bool)
    assert isinstance(report["is_cost_estimated"], bool)
    assert report["is_cost_estimated"] is True

    # 3. Independent recomputations from raw runs
    runs = report["runs"]
    sbx_pattern = re.compile(r"^sbx-[a-z0-9]{8,}$")

    wall_clocks: list[float] = []
    boot_times: list[float] = []
    costs: list[float] = []
    successes = 0

    for i, r in enumerate(runs):
        assert sbx_pattern.match(r["sandbox_name"]), f"Invalid sandbox name: {r['sandbox_name']}"
        assert r["wall_clock_s"] > 0, "wall_clock_s must be monotonic positive float"
        assert r["boot_to_ready_s"] >= 0, "boot_to_ready_s must be non-negative"
        assert r["cost_usd"] > 0, "cost_usd must be positive"
        assert r["execution_target"] == "celesto_sandbox"

        wall_clocks.append(r["wall_clock_s"])
        boot_times.append(r["boot_to_ready_s"])
        costs.append(r["cost_usd"])
        if r["success"]:
            successes += 1

        # Check ascending order of wall_clock_s
        if i > 0:
            assert runs[i - 1]["wall_clock_s"] <= r["wall_clock_s"], "Runs must be sorted by wall_clock_s ascending"

    # Recompute summary statistics
    n = len(runs)
    assert report["successful_runs"] == successes
    assert report["failed_runs"] == n - successes
    assert report["success_rate"] == round(successes / n, 4)

    # Independent median recomputation
    sorted_wall = sorted(wall_clocks)
    if n % 2 == 1:
        expected_median_wall = sorted_wall[n // 2]
    else:
        expected_median_wall = (sorted_wall[n // 2 - 1] + sorted_wall[n // 2]) / 2.0
    assert report["median_wall_clock_s"] == round(expected_median_wall, 6)

    # Independent p90 recomputation using rank ceil(0.90 * n)
    p90_rank = math.ceil(0.90 * n)
    expected_p90 = sorted_wall[p90_rank - 1]
    assert report["p90_wall_clock_s"] == round(expected_p90, 6)
    if n == 20:
        assert report["p90_wall_clock_s"] == runs[17]["wall_clock_s"]

    # Independent boot time median
    sorted_boot = sorted(boot_times)
    if n % 2 == 1:
        expected_median_boot = sorted_boot[n // 2]
    else:
        expected_median_boot = (sorted_boot[n // 2 - 1] + sorted_boot[n // 2]) / 2.0
    assert report["median_boot_to_ready_s"] == round(expected_median_boot, 6)

    # Independent cost sum
    assert report["total_cost_usd"] == round(sum(costs), 6)


def test_concurrency_report_schema_and_independent_statistics():
    """Load reports/concurrency.json, validate schema and recompute collision / concurrency metrics."""
    report_path = Path("reports/concurrency.json")
    if not report_path.exists():
        pytest.skip("reports/concurrency.json does not exist yet. Run evaluation first.")

    with open(report_path, "r", encoding="utf-8") as f:
        report = json.load(f)

    # 1. Top-level keys
    required_keys = {
        "generated_at",
        "provider",
        "is_mock_run",
        "concurrency_level",
        "started_at",
        "completed_at",
        "total_concurrency_duration_s",
        "total_cost_usd",
        "successful_jobs",
        "failed_jobs",
        "collisions_detected",
        "shared_state_issues",
        "jobs",
    }
    assert required_keys.issubset(report.keys())
    assert report["concurrency_level"] >= 5
    assert len(report["jobs"]) == report["concurrency_level"]

    # 2. Namespace uniqueness and ISO-8601 timestamps
    jobs = report["jobs"]
    names = [j["sandbox_name"] for j in jobs]
    assert len(set(names)) == len(names), "All concurrent sandbox names must be unique"
    assert report["collisions_detected"] == 0

    sbx_pattern = re.compile(r"^sbx-[a-z0-9]{8,}$")
    total_job_cost = 0.0
    success_count = 0

    for j in jobs:
        assert sbx_pattern.match(j["sandbox_name"])
        assert "started_at" in j and j["started_at"]
        assert "completed_at" in j and j["completed_at"]
        assert j["wall_clock_s"] > 0
        assert j["cost_usd"] > 0
        assert j["execution_target"] == "celesto_sandbox"
        total_job_cost += j["cost_usd"]
        if j["success"]:
            success_count += 1

    assert report["successful_jobs"] == success_count
    assert report["failed_jobs"] == len(jobs) - success_count
    assert report["total_cost_usd"] == round(total_job_cost, 6)
    assert report["shared_state_issues"] == 0


def test_postmortem_markdown_validation():
    """Load reports/postmortem.md and verify length and coverage requirements."""
    postmortem_path = Path("reports/postmortem.md")
    if not postmortem_path.exists():
        pytest.skip("reports/postmortem.md does not exist yet. Run evaluation first.")

    content = postmortem_path.read_text(encoding="utf-8")
    assert len(content) >= 200, f"Postmortem must be >= 200 characters, was {len(content)}"

    # Required thematic sections
    lower = content.lower()
    assert "reliability" in lower
    assert "concurrency" in lower
    assert "failures" in lower or "failure" in lower
    assert "retry" in lower or "retries" in lower or "recovery" in lower
    assert "provider" in lower
    assert "timing" in lower or "latency" in lower or "p90" in lower
    assert "untested" in lower or "limitations" in lower
