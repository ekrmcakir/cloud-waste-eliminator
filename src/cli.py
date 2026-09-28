import json
import sys
import click
from rich.console import Console
from rich.panel import Panel
from rich.table import Table
from src.advisor.bedrock_advisor import FinOpsAIAdvisor
from src.config import default_config
from src.handlers.remediation_handler import RemediationOrchestrator
from src.handlers.scan_handler import FinOpsScanOrchestrator
from src.models import (
    ActionType,
    ApprovalStatus,
    ResourceType,
    RiskLevel,
    WasteFinding,
    WasteReport,
)
from src.safety.state_store import WasteStateStore

console = Console()


@click.group()
def cli():
    """Event-Driven FinOps & Cloud Waste Eliminator CLI."""
    pass


@cli.command()
@click.option("--region", default=default_config.aws_region, help="AWS Region to scan")
def scan(region: str):
    """Scan AWS infrastructure for unoptimized and idle resources."""
    console.print(f"[bold cyan]🔍 Initiating FinOps scan in region:[/] [yellow]{region}[/]")

    with console.status("[bold green]Querying AWS services and computing waste metrics...[/]"):
        orchestrator = FinOpsScanOrchestrator(region=region)
        report = orchestrator.run_scan()

    _display_report(report)


@cli.command("list-findings")
@click.option("--status", default=None, help="Filter by status (PENDING_APPROVAL, APPROVED, EXECUTED, etc.)")
def list_findings(status: str):
    """List findings from the state store."""
    store = WasteStateStore()
    filter_status = ApprovalStatus(status.upper()) if status else None
    findings = store.list_findings(status=filter_status)

    if not findings:
        console.print("[yellow]No findings found matching criteria.[/]")
        return

    table = Table(title="FinOps Waste Findings", show_lines=True)
    table.add_column("Finding ID", style="bold cyan")
    table.add_column("Resource", style="white")
    table.add_column("Type", style="magenta")
    table.add_column("Monthly Waste", style="bold red")
    table.add_column("Status", style="yellow")
    table.add_column("Risk", style="blue")

    for f in findings:
        table.add_row(
            f.finding_id,
            f.resource_id,
            f.resource_type.value,
            f"${f.monthly_cost_usd:.2f}/mo",
            f.status.value,
            f.risk_level.value,
        )
    console.print(table)


@cli.command()
@click.argument("finding_id")
def inspect(finding_id: str):
    """Inspect detailed information and AI analysis for a specific finding."""
    store = WasteStateStore()
    finding = store.get_finding(finding_id)
    if not finding:
        console.print(f"[bold red]Error:[/] Finding '{finding_id}' not found.")
        sys.exit(1)

    details_table = Table(show_header=False, box=None)
    details_table.add_row("[bold]Finding ID:[/]", finding.finding_id)
    details_table.add_row("[bold]Resource ID:[/]", finding.resource_id)
    details_table.add_row("[bold]Type:[/]", finding.resource_type.value)
    details_table.add_row("[bold]Monthly Waste:[/]", f"${finding.monthly_cost_usd:.2f}")
    details_table.add_row("[bold]Status:[/]", finding.status.value)
    details_table.add_row("[bold]Risk Level:[/]", finding.risk_level.value)
    details_table.add_row("[bold]Recommended Action:[/]", finding.recommended_action.value)
    details_table.add_row("[bold]Waste Reason:[/]", finding.waste_reason)
    details_table.add_row("[bold]Tags:[/]", json.dumps(finding.tags, indent=2))
    details_table.add_row("[bold]Technical Details:[/]", json.dumps(finding.action_details, indent=2))

    console.print(Panel(details_table, title=f"Finding Details: {finding.finding_id}", border_style="cyan"))

    if finding.ai_analysis:
        console.print(
            Panel(
                f"[italic]{finding.ai_analysis}[/]",
                title="🤖 AI Rightsizing Analysis & Risk Assessment",
                border_style="magenta",
            )
        )


@cli.command()
@click.argument("finding_id")
@click.option("--dry-run/--no-dry-run", default=True, help="Simulate without mutating cloud resources")
@click.option("--user", default="admin@enterprise.internal", help="Approver identity")
def approve(finding_id: str, dry_run: bool, user: str):
    """Approve and trigger remediation for a finding."""
    console.print(f"[bold green]Approving remediation for:[/] {finding_id} (Dry-Run: {dry_run})")
    orchestrator = RemediationOrchestrator(dry_run=dry_run)
    result = orchestrator.process_approval(finding_id=finding_id, action="APPROVE", user=user)

    if result.get("success"):
        res_text = f"[bold green]Remediation Successful![/]\n{json.dumps(result, indent=2)}"
        console.print(Panel(res_text, border_style="green"))
    else:
        err_text = f"[bold red]Remediation Failed or Blocked:[/]\n{json.dumps(result, indent=2)}"
        console.print(Panel(err_text, border_style="red"))


@cli.command()
@click.argument("finding_id")
@click.option("--user", default="admin@enterprise.internal", help="Rejecter identity")
def reject(finding_id: str, user: str):
    """Reject remediation for a finding."""
    orchestrator = RemediationOrchestrator()
    orchestrator.process_approval(finding_id=finding_id, action="REJECT", user=user)
    console.print(f"[yellow]Finding {finding_id} marked as REJECTED.[/]")


@cli.command()
def simulate():
    """Run an interactive offline FinOps simulation with synthetic AWS resources."""
    header = "[bold green]🚀 FinOps & Cloud Waste Eliminator Simulator[/]\nGenerating synthetic workload..."
    console.print(Panel.fit(header, border_style="cyan"))

    # Generate synthetic findings
    findings = [
        WasteFinding(
            finding_id="ebs-vol-08fa112a9b",
            resource_id="vol-08fa112a9b",
            resource_type=ResourceType.EBS_VOLUME,
            monthly_cost_usd=50.00,
            waste_reason="Unattached 500GB gp2 volume left behind after EC2 termination 32 days ago.",
            recommended_action=ActionType.DELETE_EBS_WITH_SNAPSHOT,
            action_details={"size_gb": 500, "volume_type": "gp2", "require_snapshot": True},
            tags={"Project": "AlphaDataMigration", "Env": "staging"},
            risk_level=RiskLevel.MEDIUM,
        ),
        WasteFinding(
            finding_id="eip-eipalloc-0199e8d7",
            resource_id="eipalloc-0199e8d7",
            resource_type=ResourceType.ELASTIC_IP,
            monthly_cost_usd=3.65,
            waste_reason="Unattached Elastic IP 54.210.14.88 accumulating idle reservation penalty.",
            recommended_action=ActionType.RELEASE_EIP,
            action_details={"allocation_id": "eipalloc-0199e8d7", "public_ip": "54.210.14.88"},
            tags={"Department": "Marketing"},
            risk_level=RiskLevel.LOW,
        ),
        WasteFinding(
            finding_id="rds-analytics-reporting-db",
            resource_id="analytics-reporting-db",
            resource_type=ResourceType.RDS_INSTANCE,
            monthly_cost_usd=49.64,
            waste_reason="Idle RDS db.t3.medium instance with average 0.3% CPU and 0 connections for 14 days.",
            recommended_action=ActionType.STOP_RDS_INSTANCE,
            action_details={"instance_class": "db.t3.medium", "average_cpu_percent": 0.3},
            tags={"Stage": "dev", "Team": "BI"},
            risk_level=RiskLevel.LOW,
        ),
        WasteFinding(
            finding_id="lambda-pdf-exporter-svc",
            resource_id="pdf-exporter-svc",
            resource_type=ResourceType.LAMBDA_FUNCTION,
            monthly_cost_usd=12.50,
            waste_reason="Configured with 1024 MB RAM, but CloudWatch telemetry demonstrates 74 MB peak usage.",
            recommended_action=ActionType.RIGHTSIZE_LAMBDA_MEMORY,
            action_details={"current_memory_mb": 1024, "recommended_memory_mb": 128, "observed_peak_mb": 74},
            tags={"Service": "Exporter"},
            risk_level=RiskLevel.LOW,
        ),
    ]

    advisor = FinOpsAIAdvisor()
    store = WasteStateStore(local_fallback_path="simulated_findings.json")

    for f in findings:
        f.ai_analysis = advisor.analyze_finding(f)
        store.save_finding(f)

    total_waste = sum(f.monthly_cost_usd for f in findings)
    report = WasteReport(
        scan_id="sim-9921",
        region="us-east-1",
        total_monthly_waste_usd=round(total_waste, 2),
        estimated_annual_savings_usd=round(total_waste * 12.0, 2),
        findings_count=len(findings),
        findings=findings,
    )
    report.ai_summary = advisor.generate_executive_summary(report)

    _display_report(report)


def _display_report(report: WasteReport):
    table = Table(title=f"Cloud Waste Findings ({report.region})", show_lines=True)
    table.add_column("Resource ID", style="bold cyan")
    table.add_column("Resource Type", style="magenta")
    table.add_column("Recommended Action", style="blue")
    table.add_column("Monthly Waste", style="bold red")
    table.add_column("Risk", style="yellow")
    table.add_column("Status", style="green")

    for f in report.findings:
        table.add_row(
            f.resource_id,
            f.resource_type.value,
            f.recommended_action.value,
            f"${f.monthly_cost_usd:.2f}/mo",
            f.risk_level.value,
            f.status.value,
        )

    console.print(table)

    summary_panel = (
        f"[bold]Identified Waste Items:[/] {report.findings_count}\n"
        f"[bold red]Total Monthly Waste:[/] ${report.total_monthly_waste_usd:.2f} / month\n"
        f"[bold green]Recoverable Annual Savings:[/] ${report.estimated_annual_savings_usd:.2f} / year\n\n"
        f"[bold magenta]AI Executive Summary:[/] {report.ai_summary}"
    )
    console.print(Panel(summary_panel, title="💰 FinOps Optimization Summary", border_style="green"))


if __name__ == "__main__":
    cli()
