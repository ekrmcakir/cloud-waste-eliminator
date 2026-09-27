from src.models import (
    ActionType,
    ApprovalStatus,
    ResourceType,
    RiskLevel,
    WasteFinding,
)
from src.safety.guardrails import FinOpsGuardrail


def test_guardrail_blocks_exclusion_tags():
    guardrail = FinOpsGuardrail()
    finding = WasteFinding(
        finding_id="ebs-1",
        resource_id="vol-test",
        resource_type=ResourceType.EBS_VOLUME,
        monthly_cost_usd=20.0,
        waste_reason="idle",
        recommended_action=ActionType.DELETE_EBS_WITH_SNAPSHOT,
        tags={"DoNotDelete": "true"},
    )

    is_safe, reason = guardrail.evaluate(finding)
    assert not is_safe
    assert "Protected by tag" in reason
    assert finding.status == ApprovalStatus.EXCLUDED


def test_guardrail_blocks_production_environments():
    guardrail = FinOpsGuardrail()
    finding = WasteFinding(
        finding_id="rds-1",
        resource_id="prod-db",
        resource_type=ResourceType.RDS_INSTANCE,
        monthly_cost_usd=100.0,
        waste_reason="low cpu",
        recommended_action=ActionType.STOP_RDS_INSTANCE,
        tags={"Environment": "production"},
    )

    is_safe, reason = guardrail.evaluate(finding)
    assert not is_safe
    assert "Production environment tag detected" in reason
    assert finding.risk_level == RiskLevel.HIGH


def test_guardrail_passes_clean_dev_resource():
    guardrail = FinOpsGuardrail()
    finding = WasteFinding(
        finding_id="eip-1",
        resource_id="eipalloc-1234",
        resource_type=ResourceType.ELASTIC_IP,
        monthly_cost_usd=3.65,
        waste_reason="unattached",
        recommended_action=ActionType.RELEASE_EIP,
        tags={"Env": "dev"},
    )

    is_safe, reason = guardrail.evaluate(finding)
    assert is_safe
    assert reason == "Passed safety guardrails"
