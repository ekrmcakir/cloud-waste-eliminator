from src.advisor.bedrock_advisor import FinOpsAIAdvisor
from src.models import (
    ActionType,
    ResourceType,
    WasteFinding,
    WasteReport,
)


def test_heuristic_advisor_analyzes_ebs():
    advisor = FinOpsAIAdvisor()
    advisor.bedrock = None  # Explicitly force heuristic path

    finding = WasteFinding(
        finding_id="ebs-1",
        resource_id="vol-012345",
        resource_type=ResourceType.EBS_VOLUME,
        monthly_cost_usd=40.0,
        waste_reason="unattached",
        recommended_action=ActionType.DELETE_EBS_WITH_SNAPSHOT,
        action_details={"size_gb": 400},
    )

    analysis = advisor.analyze_finding(finding)
    assert "safety snapshot" in analysis
    assert "$40.00/month" in analysis


def test_heuristic_advisor_generates_summary():
    advisor = FinOpsAIAdvisor()
    advisor.bedrock = None  # Explicitly force heuristic path

    finding = WasteFinding(
        finding_id="ebs-1",
        resource_id="vol-012345",
        resource_type=ResourceType.EBS_VOLUME,
        monthly_cost_usd=120.0,
        waste_reason="unattached",
        recommended_action=ActionType.DELETE_EBS_WITH_SNAPSHOT,
    )

    report = WasteReport(
        scan_id="test-scan",
        region="us-east-1",
        total_monthly_waste_usd=120.0,
        estimated_annual_savings_usd=1440.0,
        findings_count=1,
        findings=[finding],
    )

    summary = advisor.generate_executive_summary(report)
    assert "$120.00" in summary
    assert "human approval" in summary


def test_summary_empty_findings():
    advisor = FinOpsAIAdvisor()
    advisor.bedrock = None

    report = WasteReport(
        scan_id="empty-scan",
        region="us-east-1",
        total_monthly_waste_usd=0.0,
        estimated_annual_savings_usd=0.0,
        findings_count=0,
        findings=[],
    )

    summary = advisor.generate_executive_summary(report)
    assert "nominal cost thresholds" in summary
