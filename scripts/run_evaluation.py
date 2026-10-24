import argparse
import asyncio
import logging
from pathlib import Path
import sys

# Add project root to sys.path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from src.evaluation.runner import EvaluationRunner
from src.sandbox.factory import get_sandbox_provider

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)
logger = logging.getLogger("eval_runner")


async def main() -> None:
    parser = argparse.ArgumentParser(description="Celesto Reliability and Concurrency Evaluation Runner")
    parser.add_argument("--runs", type=int, default=20, help="Number of reliability runs (default: 20)")
    parser.add_argument("--concurrency", type=int, default=5, help="Number of concurrent jobs (default: 5)")
    parser.add_argument("--fresh", action="store_true", help="Start fresh without resuming previous runs")
    parser.add_argument("--provider", type=str, default=None, help="Sandbox provider type (mock, cloud, local)")
    args = parser.parse_args()

    provider = get_sandbox_provider(args.provider) if args.provider else None
    runner = EvaluationRunner(provider=provider)

    print("================================================================================")
    print("CELESTO SANDBOX AGENT - PHASE 5 EVALUATION RUNNER")
    print("================================================================================")
    print(f"Target Reliability Runs : {args.runs}")
    print(f"Target Concurrency Jobs : {args.concurrency}")
    print(f"Resume Mode             : {'Disabled (Fresh)' if args.fresh else 'Enabled (Resumable)'}")
    print("--------------------------------------------------------------------------------")

    # 1. Run Reliability Evaluation
    print("\n[1/3] Running Reliability Evaluation...")
    reliability_report = await runner.run_reliability_evaluation(
        target_runs=args.runs,
        resume=not args.fresh,
    )
    print(f"  [OK] Completed {reliability_report['run_count']} runs.")
    print(f"       Success Rate    : {reliability_report['success_rate'] * 100:.1f}%")
    print(f"       Median Duration : {reliability_report['median_wall_clock_s']:.4f}s")
    print(f"       P90 Duration    : {reliability_report['p90_wall_clock_s']:.4f}s")
    print(f"       Total Cost (USD): ${reliability_report['total_cost_usd']:.6f}")
    print("       Report saved to : reports/reliability.json")

    # 2. Run Concurrency Evaluation
    print("\n[2/3] Running Concurrency Evaluation...")
    concurrency_report = await runner.run_concurrency_evaluation(
        job_count=args.concurrency,
    )
    print(f"  [OK] Completed {concurrency_report['concurrency_level']} simultaneous jobs.")
    print(f"       Duration        : {concurrency_report['total_concurrency_duration_s']:.4f}s")
    print(f"       Collisions      : {concurrency_report['collisions_detected']}")
    print(f"       Shared State Err: {concurrency_report['shared_state_issues']}")
    print("       Report saved to : reports/concurrency.json")

    # 3. Generate Postmortem
    print("\n[3/3] Generating Postmortem...")
    postmortem_path = runner.generate_postmortem(
        reliability_report=reliability_report,
        concurrency_report=concurrency_report,
    )
    print(f"  [OK] Generated postmortem: {postmortem_path}")

    print("\n================================================================================")
    print("EVALUATION COMPLETED SUCCESSFULLY")
    print("================================================================================")


if __name__ == "__main__":
    asyncio.run(main())
