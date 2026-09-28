import logging
import uuid
from typing import Any, Dict, List, Optional
from src.advisor.bedrock_advisor import FinOpsAIAdvisor
from src.config import default_config
from src.models import WasteFinding, WasteReport
from src.safety.guardrails import FinOpsGuardrail
from src.safety.state_store import WasteStateStore
from src.scanners.ebs import EBSWasteScanner
from src.scanners.eip import EIPWasteScanner
from src.scanners.lambda_fn import LambdaWasteScanner
from src.scanners.rds import RDSWasteScanner

logger = logging.getLogger(__name__)


class FinOpsScanOrchestrator:
    """Orchestrates multi-service scanning, pricing analysis, AI rightsizing, and persistence."""

    def __init__(
        self,
        region: str = default_config.aws_region,
        state_store: Optional[WasteStateStore] = None,
        ai_advisor: Optional[FinOpsAIAdvisor] = None,
        scanners: Optional[List[Any]] = None,
    ):
        self.region = region
        self.state_store = state_store or WasteStateStore()
        self.ai_advisor = ai_advisor or FinOpsAIAdvisor(region=region)
        self.guardrail = FinOpsGuardrail()

        self.scanners = scanners or [
            EBSWasteScanner(region=region),
            EIPWasteScanner(region=region),
            RDSWasteScanner(region=region),
            LambdaWasteScanner(region=region),
        ]

    def run_scan(self) -> WasteReport:
        all_findings: List[WasteFinding] = []
        for scanner in self.scanners:
            try:
                findings = scanner.scan()
                for f in findings:
                    # Evaluate guardrails
                    is_safe, reason = self.guardrail.evaluate(f)
                    # Run AI analysis
                    f.ai_analysis = self.ai_advisor.analyze_finding(f)
                    # Persist finding
                    self.state_store.save_finding(f)
                    all_findings.append(f)
            except Exception as e:
                logger.error(f"Scanner {getattr(scanner, 'name', 'unknown')} encountered error: {e}")

        total_waste = sum(f.monthly_cost_usd for f in all_findings)
        annual_savings = total_waste * 12.0

        report = WasteReport(
            scan_id=f"scan-{uuid.uuid4().hex[:8]}",
            region=self.region,
            total_monthly_waste_usd=round(total_waste, 2),
            estimated_annual_savings_usd=round(annual_savings, 2),
            findings_count=len(all_findings),
            findings=all_findings,
        )

        report.ai_summary = self.ai_advisor.generate_executive_summary(report)
        return report


def lambda_handler(event: Dict[str, Any], context: Any) -> Dict[str, Any]:
    """AWS Lambda entrypoint triggered by EventBridge Cron or manual invocation."""
    orchestrator = FinOpsScanOrchestrator()
    report = orchestrator.run_scan()
    return {
        "statusCode": 200,
        "body": report.model_dump(),
    }
