from datetime import datetime, timedelta, timezone
import logging
from typing import Any, List, Optional
import boto3
from src.config import default_config
from src.models import ActionType, ResourceType, RiskLevel, WasteFinding
from src.pricing import calculate_rds_idle_monthly_waste
from src.scanners.base import BaseScanner

logger = logging.getLogger(__name__)


class RDSWasteScanner(BaseScanner):
    name = "rds_instance_scanner"
    resource_type = ResourceType.RDS_INSTANCE

    def __init__(
        self,
        rds_client: Optional[Any] = None,
        cloudwatch_client: Optional[Any] = None,
        region: str = "us-east-1",
        cpu_threshold: float = default_config.rds_idle_cpu_threshold,
        days_window: int = default_config.rds_idle_days,
    ):
        self.region = region
        self.cpu_threshold = cpu_threshold
        self.days_window = days_window
        self.rds = rds_client or boto3.client("rds", region_name=region)
        self.cloudwatch = cloudwatch_client or boto3.client("cloudwatch", region_name=region)

    def _get_average_cpu(self, db_identifier: str) -> Optional[float]:
        try:
            end_time = datetime.now(timezone.utc)
            start_time = end_time - timedelta(days=self.days_window)

            response = self.cloudwatch.get_metric_statistics(
                Namespace="AWS/RDS",
                MetricName="CPUUtilization",
                Dimensions=[{"Name": "DBInstanceIdentifier", "Value": db_identifier}],
                StartTime=start_time,
                EndTime=end_time,
                Period=86400,  # 1-day aggregates
                Statistics=["Average"],
            )
            datapoints = response.get("Datapoints", [])
            if not datapoints:
                return None

            avg_cpu = sum(dp["Average"] for dp in datapoints) / len(datapoints)
            return round(avg_cpu, 2)
        except Exception as e:
            logger.warning(f"Could not retrieve CloudWatch CPU for RDS {db_identifier}: {e}")
            return None

    def scan(self) -> List[WasteFinding]:
        findings: List[WasteFinding] = []
        try:
            paginator = self.rds.get_paginator("describe_db_instances")
            for page in paginator.paginate():
                for instance in page.get("DBInstances", []):
                    # Multi-AZ or Aurora clusters might have different lifecycle
                    status = instance.get("DBInstanceStatus")
                    if status != "available":
                        continue

                    db_id = instance["DBInstanceIdentifier"]
                    instance_class = instance.get("DBInstanceClass", "db.t3.micro")
                    engine = instance.get("Engine", "mysql")
                    tags = self.parse_aws_tags(instance.get("TagList", []))

                    avg_cpu = self._get_average_cpu(db_id)

                    # If metrics exist and average CPU is under threshold (e.g. < 2.0%)
                    if avg_cpu is not None and avg_cpu <= self.cpu_threshold:
                        monthly_cost = calculate_rds_idle_monthly_waste(instance_class)

                        is_prod = any(
                            k.lower() in ("env", "environment") and v.lower() in ("prod", "production")
                            for k, v in tags.items()
                        )
                        risk = RiskLevel.HIGH if is_prod else RiskLevel.MEDIUM

                        finding = WasteFinding(
                            finding_id=f"rds-{db_id}",
                            resource_id=db_id,
                            resource_type=self.resource_type,
                            region=self.region,
                            monthly_cost_usd=monthly_cost,
                            waste_reason=(
                                f"Idle RDS instance ({instance_class}, {engine}) averaging "
                                f"{avg_cpu}% CPU over {self.days_window} days."
                            ),
                            recommended_action=ActionType.STOP_RDS_INSTANCE,
                            action_details={
                                "instance_class": instance_class,
                                "engine": engine,
                                "average_cpu_percent": avg_cpu,
                                "days_evaluated": self.days_window,
                            },
                            tags=tags,
                            risk_level=risk,
                        )
                        findings.append(finding)

        except Exception as e:
            logger.error(f"Failed to scan RDS instances in {self.region}: {e}")
            raise

        return findings
