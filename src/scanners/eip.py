import logging
from typing import Any, List, Optional
import boto3
from src.models import ActionType, ResourceType, RiskLevel, WasteFinding
from src.pricing import calculate_eip_monthly_waste
from src.scanners.base import BaseScanner

logger = logging.getLogger(__name__)


class EIPWasteScanner(BaseScanner):
    name = "elastic_ip_scanner"
    resource_type = ResourceType.ELASTIC_IP

    def __init__(self, ec2_client: Optional[Any] = None, region: str = "us-east-1"):
        self.region = region
        self.ec2 = ec2_client or boto3.client("ec2", region_name=region)

    def scan(self) -> List[WasteFinding]:
        findings: List[WasteFinding] = []
        try:
            response = self.ec2.describe_addresses()
            addresses = response.get("Addresses", [])

            for addr in addresses:
                # An EIP is unattached/idle if it has no InstanceId and no NetworkInterfaceId
                instance_id = addr.get("InstanceId")
                interface_id = addr.get("NetworkInterfaceId")

                if not instance_id and not interface_id:
                    allocation_id = addr.get("AllocationId", addr.get("PublicIp"))
                    public_ip = addr.get("PublicIp", "")
                    tags = self.parse_aws_tags(addr.get("Tags", []))

                    monthly_cost = calculate_eip_monthly_waste()

                    finding = WasteFinding(
                        finding_id=f"eip-{allocation_id}",
                        resource_id=allocation_id,
                        resource_type=self.resource_type,
                        region=self.region,
                        monthly_cost_usd=monthly_cost,
                        waste_reason=f"Unattached Elastic IP ({public_ip}) incurring idle hourly reservation fee.",
                        recommended_action=ActionType.RELEASE_EIP,
                        action_details={
                            "allocation_id": allocation_id,
                            "public_ip": public_ip,
                        },
                        tags=tags,
                        risk_level=RiskLevel.LOW,
                    )
                    findings.append(finding)

        except Exception as e:
            logger.error(f"Failed to scan unattached Elastic IPs in {self.region}: {e}")
            raise

        return findings
