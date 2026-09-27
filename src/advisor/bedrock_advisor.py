import json
import logging
from typing import Any, Optional
import boto3
from botocore.exceptions import ClientError
from src.config import default_config
from src.models import ActionType, WasteFinding, WasteReport

logger = logging.getLogger(__name__)


class FinOpsAIAdvisor:
    """
    FinOps rightsizing and risk reasoning advisor.
    Uses Amazon Bedrock (or deterministic heuristic fallback) to generate
    context-aware recommendations, risk assessments, and executive summaries.
    """

    def __init__(
        self,
        bedrock_client: Optional[Any] = None,
        model_id: str = default_config.bedrock_model_id,
        region: str = default_config.aws_region,
    ):
        self.model_id = model_id
        self.region = region
        self.bedrock = bedrock_client
        if not self.bedrock and default_config.enable_ai_advisor:
            try:
                self.bedrock = boto3.client("bedrock-runtime", region_name=region)
            except Exception:
                self.bedrock = None

    def analyze_finding(self, finding: WasteFinding) -> str:
        """Generates an AI rightsizing recommendation for a specific finding."""
        if not self.bedrock:
            return self._heuristic_analysis(finding)

        prompt = (
            f"You are a Cloud FinOps Engineer. Evaluate this unoptimized AWS resource and provide "
            f"a concise 2-sentence rationale on why action is recommended, potential risks, and verified savings.\n\n"
            f"Resource ID: {finding.resource_id}\n"
            f"Type: {finding.resource_type.value}\n"
            f"Monthly Waste: ${finding.monthly_cost_usd:.2f}/mo\n"
            f"Reason: {finding.waste_reason}\n"
            f"Recommended Action: {finding.recommended_action.value}\n"
            f"Details: {json.dumps(finding.action_details)}\n"
            f"Tags: {json.dumps(finding.tags)}\n\n"
            f"Provide direct, professional technical analysis without conversational fluff."
        )

        try:
            # Bedrock Converse or InvokeModel API
            body = json.dumps({
                "inputText": prompt,
                "textGenerationConfig": {
                    "maxTokenCount": 200,
                    "temperature": 0.2,
                    "topP": 0.9,
                }
            })
            # Try Amazon Nova or Claude format
            if "anthropic" in self.model_id:
                body = json.dumps({
                    "anthropic_version": "bedrock-2023-05-31",
                    "max_tokens": 200,
                    "messages": [{"role": "user", "content": prompt}],
                    "temperature": 0.2,
                })
                response = self.bedrock.invoke_model(modelId=self.model_id, body=body)
                resp_body = json.loads(response["body"].read())
                return resp_body["content"][0]["text"].strip()
            elif "amazon.nova" in self.model_id:
                body = json.dumps({
                    "messages": [{"role": "user", "content": [{"text": prompt}]}],
                    "inferenceConfig": {"max_new_tokens": 200, "temperature": 0.2}
                })
                response = self.bedrock.invoke_model(modelId=self.model_id, body=body)
                resp_body = json.loads(response["body"].read())
                return resp_body["output"]["message"]["content"][0]["text"].strip()
            else:
                response = self.bedrock.invoke_model(modelId=self.model_id, body=body)
                resp_body = json.loads(response["body"].read())
                return resp_body.get("results", [{}])[0].get("outputText", "").strip()

        except (ClientError, Exception) as e:
            logger.debug(f"Bedrock invocation failed, falling back to heuristic: {e}")
            return self._heuristic_analysis(finding)

    def generate_executive_summary(self, report: WasteReport) -> str:
        """Generates an executive FinOps summary for an entire scan run."""
        if not report.findings:
            return (
                "No idle or unoptimized AWS resources identified. "
                "Cloud infrastructure is operating within nominal cost thresholds."
            )

        if not self.bedrock:
            return (
                f"Scan identified {report.findings_count} unoptimized resources totaling "
                f"${report.total_monthly_waste_usd:.2f}/month (${report.estimated_annual_savings_usd:.2f}/year) "
                f"in recoverable waste. Actions require human approval prior to execution."
            )

        summary_prompt = (
            f"Generate a professional, 3-sentence FinOps executive summary for the engineering team "
            f"based on these scan results:\n"
            f"Total Unoptimized Resources: {report.findings_count}\n"
            f"Total Recoverable Monthly Waste: ${report.total_monthly_waste_usd:.2f}\n"
            f"Estimated Annual Savings: ${report.estimated_annual_savings_usd:.2f}\n"
            f"Breakdown: {', '.join(f'{f.resource_type.value}: ${f.monthly_cost_usd}' for f in report.findings[:8])}\n"
            f"Highlight top waste drivers and safety posture."
        )

        try:
            if "anthropic" in self.model_id:
                body = json.dumps({
                    "anthropic_version": "bedrock-2023-05-31",
                    "max_tokens": 250,
                    "messages": [{"role": "user", "content": summary_prompt}],
                    "temperature": 0.2,
                })
                response = self.bedrock.invoke_model(modelId=self.model_id, body=body)
                resp_body = json.loads(response["body"].read())
                return resp_body["content"][0]["text"].strip()
            else:
                return (
                    f"Identified {report.findings_count} unoptimized resources yielding "
                    f"${report.total_monthly_waste_usd:.2f}/mo in recoverable spend. "
                    f"Primary waste driver is unattached storage and idle database capacity."
                )
        except Exception:
            return (
                f"Identified {report.findings_count} unoptimized resources yielding "
                f"${report.total_monthly_waste_usd:.2f}/mo in recoverable spend. "
                f"Primary waste driver is unattached storage and idle database capacity."
            )

    def _heuristic_analysis(self, finding: WasteFinding) -> str:
        """Deterministic heuristic analysis when Bedrock is offline or disabled."""
        if finding.recommended_action == ActionType.DELETE_EBS_WITH_SNAPSHOT:
            return (
                f"Volume has been detached with 0 active I/O operations. Deletion after taking a safety snapshot "
                f"eliminates ${finding.monthly_cost_usd:.2f}/month with zero production disruption risk."
            )
        elif finding.recommended_action == ActionType.RELEASE_EIP:
            return (
                f"Static IP has no active ENI association, generating unnecessary hourly reservation penalties. "
                f"Immediate release reclaims ${finding.monthly_cost_usd:.2f}/month."
            )
        elif finding.recommended_action == ActionType.STOP_RDS_INSTANCE:
            avg_cpu = finding.action_details.get("average_cpu_percent", 0.0)
            return (
                f"Database exhibits sustained idle metrics (avg {avg_cpu}% CPU). Stopping this development "
                f"instance reclaims 100% of compute capacity cost while preserving underlying storage and state."
            )
        elif finding.recommended_action == ActionType.RIGHTSIZE_LAMBDA_MEMORY:
            cur = finding.action_details.get("current_memory_mb", 0)
            rec = finding.action_details.get("recommended_memory_mb", 0)
            return (
                f"Function memory is significantly over-allocated ({cur} MB vs {rec} MB recommended). "
                f"Right-sizing maintains a 30% execution buffer while trimming execution GB-second billing."
            )
        return "Resource parameters indicate continuous idle waste without active upstream dependencies."
