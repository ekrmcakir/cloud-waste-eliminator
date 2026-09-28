import logging
from typing import Any, Dict, Optional
import boto3
from botocore.exceptions import ClientError
from src.config import default_config
from src.models import ActionType, ApprovalStatus, WasteFinding
from src.safety.guardrails import FinOpsGuardrail

logger = logging.getLogger(__name__)


class RemediationExecutor:
    """Executes safe, approved remediation operations across AWS services."""

    def __init__(
        self,
        ec2_client: Optional[Any] = None,
        rds_client: Optional[Any] = None,
        lambda_client: Optional[Any] = None,
        dry_run: bool = default_config.dry_run,
        region: str = default_config.aws_region,
    ):
        self.dry_run = dry_run
        self.region = region
        self.ec2 = ec2_client or boto3.client("ec2", region_name=region)
        self.rds = rds_client or boto3.client("rds", region_name=region)
        self.lambda_client = lambda_client or boto3.client("lambda", region_name=region)
        self.guardrail = FinOpsGuardrail()

    def execute(self, finding: WasteFinding) -> Dict[str, Any]:
        """
        Executes remediation for an approved finding.
        Returns execution result dictionary.
        """
        # 1. Enforce safety guardrails
        is_safe, reason = self.guardrail.evaluate(finding)
        if not is_safe:
            logger.warning(f"Remediation blocked by guardrail for {finding.resource_id}: {reason}")
            return {"success": False, "reason": reason, "status": ApprovalStatus.EXCLUDED.value}

        if self.dry_run:
            logger.info(f"[DRY-RUN] Would execute {finding.recommended_action.value} on {finding.resource_id}")
            return {
                "success": True,
                "dry_run": True,
                "action": finding.recommended_action.value,
                "resource_id": finding.resource_id,
                "message": f"[DRY-RUN] Simulated execution for {finding.resource_id}",
            }

        try:
            if finding.recommended_action == ActionType.DELETE_EBS_WITH_SNAPSHOT:
                return self._remediate_ebs(finding)
            elif finding.recommended_action == ActionType.RELEASE_EIP:
                return self._remediate_eip(finding)
            elif finding.recommended_action == ActionType.STOP_RDS_INSTANCE:
                return self._remediate_rds(finding)
            elif finding.recommended_action == ActionType.RIGHTSIZE_LAMBDA_MEMORY:
                return self._remediate_lambda(finding)
            else:
                return {"success": False, "reason": f"Unknown action: {finding.recommended_action}"}

        except ClientError as e:
            err_msg = e.response.get("Error", {}).get("Message", str(e))
            logger.error(f"Remediation execution failed for {finding.resource_id}: {err_msg}")
            return {"success": False, "error": err_msg}

    def _remediate_ebs(self, finding: WasteFinding) -> Dict[str, Any]:
        vol_id = finding.resource_id
        # Step 1: Create backup snapshot
        snapshot_resp = self.ec2.create_snapshot(
            VolumeId=vol_id,
            Description=f"Pre-deletion safety snapshot created by Cloud Waste Eliminator for {vol_id}",
            TagSpecifications=[
                {
                    "ResourceType": "snapshot",
                    "Tags": [
                        {"Key": "CreatedBy", "Value": "CloudWasteEliminator"},
                        {"Key": "OriginalVolumeId", "Value": vol_id},
                    ],
                }
            ],
        )
        snap_id = snapshot_resp.get("SnapshotId")
        logger.info(f"Created safety snapshot {snap_id} for volume {vol_id}")

        # Step 2: Delete volume
        self.ec2.delete_volume(VolumeId=vol_id)
        logger.info(f"Deleted unattached volume {vol_id}")

        return {
            "success": True,
            "action": finding.recommended_action.value,
            "volume_id": vol_id,
            "snapshot_id": snap_id,
            "monthly_savings_usd": finding.monthly_cost_usd,
        }

    def _remediate_eip(self, finding: WasteFinding) -> Dict[str, Any]:
        alloc_id = finding.action_details.get("allocation_id", finding.resource_id)
        self.ec2.release_address(AllocationId=alloc_id)
        logger.info(f"Released unattached Elastic IP allocation: {alloc_id}")

        return {
            "success": True,
            "action": finding.recommended_action.value,
            "allocation_id": alloc_id,
            "monthly_savings_usd": finding.monthly_cost_usd,
        }

    def _remediate_rds(self, finding: WasteFinding) -> Dict[str, Any]:
        db_id = finding.resource_id
        self.rds.stop_db_instance(DBInstanceIdentifier=db_id)
        logger.info(f"Stopped idle RDS instance: {db_id}")

        return {
            "success": True,
            "action": finding.recommended_action.value,
            "db_instance_id": db_id,
            "monthly_savings_usd": finding.monthly_cost_usd,
        }

    def _remediate_lambda(self, finding: WasteFinding) -> Dict[str, Any]:
        fn_name = finding.resource_id
        target_memory = finding.action_details.get("recommended_memory_mb", 128)
        self.lambda_client.update_function_configuration(
            FunctionName=fn_name,
            MemorySize=target_memory,
        )
        logger.info(f"Right-sized Lambda {fn_name} to {target_memory} MB")

        return {
            "success": True,
            "action": finding.recommended_action.value,
            "function_name": fn_name,
            "new_memory_mb": target_memory,
            "monthly_savings_usd": finding.monthly_cost_usd,
        }
