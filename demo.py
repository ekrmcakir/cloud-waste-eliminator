#!/usr/bin/env python3
"""
Interactive Demonstration Showcase for Cloud Waste Eliminator.
Runs a complete simulated scan, generates FinOps AI recommendations,
and steps through human-in-the-loop approval and safe dry-run remediation.
"""

import time
from rich.console import Console
from rich.panel import Panel
from rich.table import Table

from src.advisor.bedrock_advisor import FinOpsAIAdvisor
from src.handlers.remediation_handler import RemediationOrchestrator
from src.models import (
    ActionType,
    ResourceType,
    RiskLevel,
    WasteFinding,
    WasteReport,
)
from src.safety.state_store import WasteStateStore

console = Console()


def run_showcase():
    console.print(
        Panel.fit(
            "[bold cyan]💡 Event-Driven FinOps & Cloud Waste Eliminator[/]\n"
            "[italic white]Serverless Cloud Cost Optimization & Autonomous Rightsizing Engine[/]",
            border_style="cyan",
        )
    )

    console.print("\n[bold yellow]Step 1: Simulating EventBridge Scheduled Scan across AWS Account...[/]")
    time.sleep(1)

    # Simulated findings in an enterprise AWS account
    findings = [
        WasteFinding(
            finding_id="ebs-vol-0e3199b50fa",
            resource_id="vol-0e3199b50fa",
            resource_type=ResourceType.EBS_VOLUME,
            monthly_cost_usd=80.00,
            waste_reason="Unattached 800GB gp2 volume detached since 45 days ago.",
            recommended_action=ActionType.DELETE_EBS_WITH_SNAPSHOT,
            action_details={"size_gb": 800, "volume_type": "gp2", "require_snapshot": True},
            tags={"Environment": "staging", "Project": "legacy-migration"},
            risk_level=RiskLevel.MEDIUM,
        ),
        WasteFinding(
            finding_id="eip-eipalloc-0177fc2",
            resource_id="eipalloc-0177fc2",
            resource_type=ResourceType.ELASTIC_IP,
            monthly_cost_usd=7.30,
            waste_reason="2 unattached Elastic IPs sitting idle without active ENI association.",
            recommended_action=ActionType.RELEASE_EIP,
            action_details={"allocation_id": "eipalloc-0177fc2", "count": 2},
            tags={"Owner": "devops-team"},
            risk_level=RiskLevel.LOW,
        ),
        WasteFinding(
            finding_id="rds-test-analytics-replica",
            resource_id="test-analytics-replica",
            resource_type=ResourceType.RDS_INSTANCE,
            monthly_cost_usd=49.64,
            waste_reason="Idle db.t3.medium instance running 24/7 with average 0.4% CPU over 14 days.",
            recommended_action=ActionType.STOP_RDS_INSTANCE,
            action_details={"instance_class": "db.t3.medium", "average_cpu_percent": 0.4},
            tags={"Environment": "qa", "Purpose": "temp-load-test"},
            risk_level=RiskLevel.LOW,
        ),
        WasteFinding(
            finding_id="lambda-report-generator",
            resource_id="report-generator",
            resource_type=ResourceType.LAMBDA_FUNCTION,
            monthly_cost_usd=16.80,
            waste_reason="Provisioned with 1024 MB RAM, but actual peak utilization never exceeded 88 MB.",
            recommended_action=ActionType.RIGHTSIZE_LAMBDA_MEMORY,
            action_details={"current_memory_mb": 1024, "recommended_memory_mb": 128, "observed_peak_mb": 88},
            tags={"Tier": "backend", "Environment": "dev"},
            risk_level=RiskLevel.LOW,
        ),
    ]

    advisor = FinOpsAIAdvisor()
    store = WasteStateStore(local_fallback_path="showcase_state.json")

    for f in findings:
        f.ai_analysis = advisor.analyze_finding(f)
        store.save_finding(f)

    total_monthly = sum(f.monthly_cost_usd for f in findings)
    annual_savings = total_monthly * 12.0

    report = WasteReport(
        scan_id="showcase-run-01",
        region="us-east-1",
        total_monthly_waste_usd=round(total_monthly, 2),
        estimated_annual_savings_usd=round(annual_savings, 2),
        findings_count=len(findings),
        findings=findings,
    )
    report.ai_summary = advisor.generate_executive_summary(report)

    # Render table
    table = Table(title="AWS Waste Audit Findings (us-east-1)", show_lines=True)
    table.add_column("Finding ID", style="bold cyan")
    table.add_column("Resource", style="white")
    table.add_column("Type", style="magenta")
    table.add_column("Monthly Waste", style="bold red")
    table.add_column("Risk Level", style="yellow")
    table.add_column("Status", style="green")

    for f in findings:
        table.add_row(
            f.finding_id,
            f.resource_id,
            f.resource_type.value,
            f"${f.monthly_cost_usd:.2f}/mo",
            f.risk_level.value,
            f.status.value,
        )
    console.print(table)

    summary_panel = (
        f"[bold]Detected Waste Items:[/] {report.findings_count}\n"
        f"[bold red]Total Monthly Waste:[/] ${report.total_monthly_waste_usd:.2f} / month\n"
        f"[bold green]Recoverable Annual Savings:[/] ${report.estimated_annual_savings_usd:.2f} / year\n\n"
        f"[bold magenta]FinOps AI Summary:[/] {report.ai_summary}"
    )
    console.print(Panel(summary_panel, title="📊 FinOps Executive Summary", border_style="green"))

    console.print("\n[bold yellow]Step 2: Inspecting AI Recommendation for Top Waste Driver...[/]")
    top_finding = findings[0]
    ai_box = (
        f"[bold]Target:[/] {top_finding.resource_id} ({top_finding.resource_type.value})\n"
        f"[bold]Recommended Action:[/] {top_finding.recommended_action.value}\n"
        f"[bold]Reason:[/] {top_finding.waste_reason}\n\n"
        f"[italic cyan]AI Rationale & Safety Check:[/] {top_finding.ai_analysis}"
    )
    console.print(Panel(ai_box, title="🤖 AI Rightsizing & Safety Review", border_style="cyan"))

    console.print(
        f"\n[bold yellow]Step 3: Human-in-the-Loop Safe Remediation[/]\n"
        f"Triggering approved remediation for [bold cyan]{top_finding.finding_id}[/] (Dry-Run Safety Mode)..."
    )

    remediator = RemediationOrchestrator(state_store=store, dry_run=True)
    res = remediator.process_approval(
        finding_id=top_finding.finding_id,
        action="APPROVE",
        user="lead-finops-architect",
    )

    result_box = (
        f"[bold green]✓ Execution Completed Successfully[/]\n"
        f"Status: {res['status']}\nFinding: {res['finding_id']}\n"
        f"Details: {res['details']}"
    )
    console.print(Panel(result_box, border_style="green"))

    console.print("\n[bold green]🎉 Showcase complete! All components validated.[/]\n")


if __name__ == "__main__":
    run_showcase()
