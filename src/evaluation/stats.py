import math
from typing import Sequence


def calculate_median(values: Sequence[float]) -> float:
    """Calculate median correctly for odd and even sample counts.

    - If n is odd: middle element at index n // 2.
    - If n is even: average of middle two elements at n // 2 - 1 and n // 2.
    """
    if not values:
        return 0.0
    sorted_vals = sorted(values)
    n = len(sorted_vals)
    if n % 2 == 1:
        return float(sorted_vals[n // 2])
    else:
        return float((sorted_vals[n // 2 - 1] + sorted_vals[n // 2]) / 2.0)


def calculate_p90(values: Sequence[float]) -> float:
    """Calculate p90 using rank ceil(0.90 * n).

    For exactly 20 values, rank = ceil(18.0) = 18 (1-indexed), which corresponds
    to the 18th sorted value (index 17 in 0-indexed Python).
    """
    if not values:
        return 0.0
    sorted_vals = sorted(values)
    n = len(sorted_vals)
    rank = math.ceil(0.90 * n)
    # Clamp rank between 1 and n
    index = max(0, min(n - 1, rank - 1))
    return float(sorted_vals[index])


def calculate_success_rate(successful_count: int, total_count: int) -> float:
    """Calculate success rate as successful runs divided by total runs."""
    if total_count <= 0:
        return 0.0
    return round(float(successful_count / total_count), 4)


# Celesto compute pricing model:
# MicroVM Standard Tier 1 (1 vCPU, 2GB RAM): $0.05 / hour (~$0.0000138889 / s)
# Ephemeral root disk provisioning: $0.00005 / instance
HOURLY_RATE_USD = 0.05
PER_SECOND_RATE_USD = HOURLY_RATE_USD / 3600.0
DISK_PROVISIONING_USD = 0.00005
COST_MODEL_NAME = "celesto_microvm_tier1_estimate_0.05_usd_per_hour"


def estimate_run_cost_usd(duration_s: float) -> float:
    """Calculate reproducible cost in USD for a microVM run duration.

    Uses documented Celesto MicroVM Tier 1 compute rates ($0.05/hour) +
    ephemeral disk provisioning ($0.00005).
    """
    if duration_s < 0:
        duration_s = 0.0
    cost = DISK_PROVISIONING_USD + (duration_s * PER_SECOND_RATE_USD)
    return round(cost, 6)
