from src.pricing import (
    calculate_ebs_monthly_waste,
    calculate_eip_monthly_waste,
    calculate_lambda_rightsizing_waste,
    calculate_rds_idle_monthly_waste,
)


def test_ebs_pricing_calculation():
    # 100 GB gp3 @ $0.08/GB
    assert calculate_ebs_monthly_waste(100, "gp3") == 8.00
    # 500 GB gp2 @ $0.10/GB
    assert calculate_ebs_monthly_waste(500, "gp2") == 50.00
    # 200 GB io1 @ $0.125/GB
    assert calculate_ebs_monthly_waste(200, "io1") == 25.00


def test_eip_pricing_calculation():
    # Standard idle EIP rate
    cost = calculate_eip_monthly_waste()
    assert cost == 3.65


def test_rds_pricing_calculation():
    # db.t3.medium compute rate
    cost = calculate_rds_idle_monthly_waste("db.t3.medium")
    assert cost == 49.64

    # Unknown instance fallback
    cost_unknown = calculate_rds_idle_monthly_waste("db.custom.heavy")
    assert cost_unknown == 30.00


def test_lambda_rightsizing_calculation():
    # Right-sizing from 1024 MB to 128 MB for 1M invocations
    savings = calculate_lambda_rightsizing_waste(
        current_memory_mb=1024,
        recommended_memory_mb=128,
        monthly_invocations=1_000_000,
        avg_duration_ms=400.0,
    )
    assert savings > 0.0
    # If recommended >= current, savings must be 0
    assert calculate_lambda_rightsizing_waste(128, 128) == 0.0
    assert calculate_lambda_rightsizing_waste(128, 256) == 0.0
