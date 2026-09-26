import logging
from typing import Any, List, Optional
import boto3
from src.models import ActionType, ResourceType, RiskLevel, WasteFinding
from src.pricing import calculate_ebs_monthly_waste
from src.scanners.base import BaseScanner

logger = logging.getLogger(__name__)


class EBSWasteScanner(BaseScanner):
    name = "ebs_volume_scanner"
    resource_type = ResourceType.EBS_VOLUME

    def __init__(self, ec2_client: Optional[Any] = None, region: str = "us-east-1"):
        self.region = region
        self.ec2 = ec2_client or boto3.client("ec2", region_name=region)

    def scan(self) -> List[WasteFinding]:
        findings: List[WasteFinding] = []
        try:
            # An 'available' volume is detached from all EC2 instances
            paginator = self.ec2.get_paginator("describe_volumes")
            page_iterator = paginator.paginate(
                Filters=[{"Name": "status", "Values": ["available"]}]
            )

            for page in page_iterator:
                for vol in page.get("Volumes", []):
                    vol_id = vol["VolumeId"]
                    size_gb = vol.get("Size", 0)
                    vol_type = vol.get("VolumeType", "gp3")
                    tags = self.parse_aws_tags(vol.get("Tags", []))
                    create_time = vol.get("CreateTime")
                    create_time_str = create_time.isoformat() if create_time else ""

                    monthly_cost = calculate_ebs_monthly_waste(size_gb, vol_type)
                    risk = RiskLevel.MEDIUM if size_gb >= 200 else RiskLevel.LOW

                    finding = WasteFinding(
                        finding_id=f"ebs-{vol_id}",
                        resource_id=vol_id,
                        resource_type=self.resource_type,
                        region=self.region,
                        monthly_cost_usd=monthly_cost,
                        waste_reason=(
                            f"Unattached EBS volume ({size_gb} GB {vol_type}) sitting idle in 'available' state."
                        ),
                        recommended_action=ActionType.DELETE_EBS_WITH_SNAPSHOT,
                        action_details={
                            "size_gb": size_gb,
                            "volume_type": vol_type,
                            "create_time": create_time_str,
                            "require_snapshot": True,
                        },
                        tags=tags,
                        risk_level=risk,
                    )
                    findings.append(finding)

        except Exception as e:
            logger.error(f"Failed to scan unattached EBS volumes in {self.region}: {e}")
            raise

        return findings
