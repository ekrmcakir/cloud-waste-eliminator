import json
import logging
from typing import Any, Dict, Optional
from src.config import default_config
from src.models import ApprovalStatus
from src.remediation.executor import RemediationExecutor
from src.safety.state_store import WasteStateStore

logger = logging.getLogger(__name__)


class RemediationOrchestrator:
    """Handles approval decisions and executes remediation workflows."""

    def __init__(
        self,
        state_store: Optional[WasteStateStore] = None,
        executor: Optional[RemediationExecutor] = None,
        dry_run: bool = default_config.dry_run,
    ):
        self.state_store = state_store or WasteStateStore()
        self.executor = executor or RemediationExecutor(dry_run=dry_run)

    def process_approval(
        self,
        finding_id: str,
        action: str,  # "APPROVE" or "REJECT"
        user: str = "finops-engineer",
    ) -> Dict[str, Any]:
        finding = self.state_store.get_finding(finding_id)
        if not finding:
            return {"success": False, "error": f"Finding {finding_id} not found"}

        if action.upper() == "REJECT":
            self.state_store.update_status(
                finding_id=finding_id,
                status=ApprovalStatus.REJECTED,
                approved_by=user,
                execution_result="Remediation rejected by reviewer",
            )
            return {"success": True, "status": "REJECTED", "finding_id": finding_id}

        if action.upper() == "APPROVE":
            # Update to approved
            self.state_store.update_status(
                finding_id=finding_id,
                status=ApprovalStatus.APPROVED,
                approved_by=user,
            )

            # Execute remediation
            result = self.executor.execute(finding)

            if result.get("success"):
                new_status = ApprovalStatus.EXECUTED
            else:
                new_status = ApprovalStatus.FAILED

            self.state_store.update_status(
                finding_id=finding_id,
                status=new_status,
                approved_by=user,
                execution_result=json.dumps(result),
            )
            return {
                "success": result.get("success", False),
                "status": new_status.value,
                "finding_id": finding_id,
                "details": result,
            }

        return {"success": False, "error": f"Invalid action: {action}. Expected APPROVE or REJECT."}


def lambda_handler(event: Dict[str, Any], context: Any) -> Dict[str, Any]:
    """
    AWS Lambda entrypoint triggered by API Gateway, Webhook, or admin portal.
    Payload: {"finding_id": "ebs-vol-1234", "action": "APPROVE", "user": "alice@company.com"}
    """
    body = event
    if "body" in event and isinstance(event["body"], str):
        try:
            body = json.loads(event["body"])
        except Exception:
            body = event

    finding_id = body.get("finding_id")
    action = body.get("action", "APPROVE")
    user = body.get("user", "cloud-admin")

    if not finding_id:
        return {
            "statusCode": 400,
            "body": json.dumps({"error": "Missing required field: finding_id"}),
        }

    orchestrator = RemediationOrchestrator()
    result = orchestrator.process_approval(finding_id=finding_id, action=action, user=user)

    status_code = 200 if result.get("success") else 400
    return {
        "statusCode": status_code,
        "body": json.dumps(result),
    }
