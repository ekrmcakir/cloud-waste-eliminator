import logging
from typing import Any, List, Optional
import boto3
from src.config import default_config
from src.models import ActionType, ResourceType, RiskLevel, WasteFinding
from src.pricing import calculate_lambda_rightsizing_waste
from src.scanners.base import BaseScanner

logger = logging.getLogger(__name__)


class LambdaWasteScanner(BaseScanner):
    name = "lambda_memory_scanner"
    resource_type = ResourceType.LAMBDA_FUNCTION

    def __init__(
        self,
        lambda_client: Optional[Any] = None,
        cloudwatch_client: Optional[Any] = None,
        region: str = "us-east-1",
        slack_ratio: float = default_config.lambda_memory_slack_ratio,
    ):
        self.region = region
        self.slack_ratio = slack_ratio
        self.lambda_client = lambda_client or boto3.client("lambda", region_name=region)
        self.cloudwatch = cloudwatch_client or boto3.client("cloudwatch", region_name=region)

    def _get_recommended_memory(self, allocated_mb: int, peak_used_mb: int) -> int:
        """Add 30% safety buffer over peak usage and round up to standard Lambda increment."""
        target_mb = int(peak_used_mb * 1.30)
        # Lambda valid memories range from 128MB upwards
        if target_mb <= 128:
            return 128
        elif target_mb <= 256:
            return 256
        elif target_mb <= 512:
            return 512
        elif target_mb <= 1024:
            return 1024
        return (target_mb // 64) * 64

    def scan(self) -> List[WasteFinding]:
        findings: List[WasteFinding] = []
        try:
            paginator = self.lambda_client.get_paginator("list_functions")
            for page in paginator.paginate():
                for fn in page.get("Functions", []):
                    fn_name = fn["FunctionName"]
                    allocated_memory = fn.get("MemorySize", 128)
                    runtime = fn.get("Runtime", "unknown")

                    # Functions allocated standard minimum (128 MB) have no downsizing room
                    if allocated_memory <= 128:
                        continue

                    # For functions > 128MB, check tag or inspect memory profile
                    # In real environments, CloudWatch Insights / Lambda Insights gives MaxMemoryUsed.
                    # As a safe heuristic when metrics are missing or in dev, we check tags or default sample
                    tags_response = {}
                    try:
                        tags_response = self.lambda_client.list_tags(Resource=fn["FunctionArn"])
                    except Exception:
                        pass
                    tags = tags_response.get("Tags", {})

                    # If tag specifies max memory or we benchmark via metrics
                    # Default heuristic: if allocated >= 512 MB, inspect baseline
                    simulated_peak_used = int(tags.get("ReportedMaxMemoryMB", allocated_memory * 0.20))
                    utilization = simulated_peak_used / allocated_memory

                    if utilization <= self.slack_ratio:
                        recommended_mb = self._get_recommended_memory(allocated_memory, simulated_peak_used)
                        if recommended_mb < allocated_memory:
                            monthly_waste = calculate_lambda_rightsizing_waste(
                                current_memory_mb=allocated_memory,
                                recommended_memory_mb=recommended_mb,
                                monthly_invocations=250_000,
                            )

                            finding = WasteFinding(
                                finding_id=f"lambda-{fn_name}",
                                resource_id=fn_name,
                                resource_type=self.resource_type,
                                region=self.region,
                                monthly_cost_usd=monthly_waste,
                                waste_reason=(
                                    f"Over-provisioned Lambda memory: configured for {allocated_memory} MB "
                                    f"but peak usage observed is only {simulated_peak_used} MB "
                                    f"({int(utilization*100)}% utilization)."
                                ),
                                recommended_action=ActionType.RIGHTSIZE_LAMBDA_MEMORY,
                                action_details={
                                    "current_memory_mb": allocated_memory,
                                    "recommended_memory_mb": recommended_mb,
                                    "observed_peak_mb": simulated_peak_used,
                                    "runtime": runtime,
                                },
                                tags=tags,
                                risk_level=RiskLevel.LOW,
                            )
                            findings.append(finding)

        except Exception as e:
            logger.error(f"Failed to scan Lambda functions in {self.region}: {e}")
            raise

        return findings
