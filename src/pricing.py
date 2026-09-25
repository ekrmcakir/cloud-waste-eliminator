from typing import Dict

# AWS Standard Rates (us-east-1 reference rates)
EBS_GB_MONTH_RATES: Dict[str, float] = {
    "gp3": 0.08,
    "gp2": 0.10,
    "io1": 0.125,
    "io2": 0.125,
    "standard": 0.05,
    "st1": 0.045,
    "sc1": 0.015,
}

# Idle Elastic IP cost: $0.005 / hour * 730 hours / month
EIP_IDLE_MONTHLY_COST = 3.65

# Standard Single-AZ RDS Monthly Compute Rates (USD)
RDS_INSTANCE_MONTHLY_RATES: Dict[str, float] = {
    "db.t3.micro": 12.41,
    "db.t3.small": 24.82,
    "db.t3.medium": 49.64,
    "db.t3.large": 99.28,
    "db.t4g.micro": 10.51,
    "db.t4g.small": 21.02,
    "db.t4g.medium": 42.05,
    "db.t4g.large": 84.10,
    "db.m5.large": 138.70,
    "db.m5.xlarge": 277.40,
    "db.m6g.large": 122.64,
    "db.m6g.xlarge": 245.28,
    "db.r5.large": 175.20,
    "db.r6g.large": 154.76,
}

LAMBDA_GB_SECOND_RATE = 0.0000166667  # x86 architecture standard rate


def calculate_ebs_monthly_waste(size_gb: int, volume_type: str = "gp3") -> float:
    rate = EBS_GB_MONTH_RATES.get(volume_type.lower(), 0.08)
    return round(size_gb * rate, 2)


def calculate_eip_monthly_waste() -> float:
    return round(EIP_IDLE_MONTHLY_COST, 2)


def calculate_rds_idle_monthly_waste(instance_class: str) -> float:
    # When stopped, compute cost ($12 - $200+/mo) drops to zero while storage remains.
    return round(RDS_INSTANCE_MONTHLY_RATES.get(instance_class.lower(), 30.00), 2)


def calculate_lambda_rightsizing_waste(
    current_memory_mb: int,
    recommended_memory_mb: int,
    monthly_invocations: int = 500_000,
    avg_duration_ms: float = 300.0,
) -> float:
    if recommended_memory_mb >= current_memory_mb:
        return 0.0

    duration_seconds = avg_duration_ms / 1000.0
    current_gb = current_memory_mb / 1024.0
    recommended_gb = recommended_memory_mb / 1024.0

    current_cost = monthly_invocations * duration_seconds * current_gb * LAMBDA_GB_SECOND_RATE
    recommended_cost = monthly_invocations * duration_seconds * recommended_gb * LAMBDA_GB_SECOND_RATE

    monthly_savings = max(0.0, current_cost - recommended_cost)
    return round(monthly_savings, 2)
