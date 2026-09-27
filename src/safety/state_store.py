from datetime import datetime, timezone
import json
import logging
import os
from typing import Any, Dict, List, Optional
import boto3
from botocore.exceptions import ClientError
from src.config import default_config
from src.models import ApprovalStatus, WasteFinding

logger = logging.getLogger(__name__)


class WasteStateStore:
    """Manages finding state, approvals, and audit trail in DynamoDB with local fallback."""

    def __init__(
        self,
        table_name: str = default_config.dynamodb_table,
        dynamodb_resource: Optional[Any] = None,
        local_fallback_path: str = "findings_state.json",
    ):
        self.table_name = table_name
        self.local_fallback_path = local_fallback_path
        self._local_cache: Dict[str, Dict[str, Any]] = {}
        self.dynamodb = dynamodb_resource
        self.table = None
        self.is_dynamo_available = False

        if not self.dynamodb:
            try:
                self.dynamodb = boto3.resource("dynamodb", region_name=default_config.aws_region)
                self.table = self.dynamodb.Table(self.table_name)
                # Quick ping to see if table exists
                self.table.load()
                self.is_dynamo_available = True
            except Exception:
                logger.info(f"DynamoDB table '{self.table_name}' unavailable. Using local state store.")
                self.is_dynamo_available = False
                self._load_local_cache()

    def _load_local_cache(self):
        if os.path.exists(self.local_fallback_path):
            try:
                with open(self.local_fallback_path, "r") as f:
                    self._local_cache = json.load(f)
            except Exception:
                self._local_cache = {}

    def _save_local_cache(self):
        try:
            with open(self.local_fallback_path, "w") as f:
                json.dump(self._local_cache, f, indent=2)
        except Exception as e:
            logger.error(f"Error persisting local state: {e}")

    def save_finding(self, finding: WasteFinding) -> bool:
        item = finding.model_dump()
        # Convert float to string or Decimal if in DynamoDB
        if self.is_dynamo_available and self.table:
            try:
                # DynamoDB does not support native float, convert to Decimal string
                from decimal import Decimal
                dynamo_item = json.loads(json.dumps(item), parse_float=Decimal)
                self.table.put_item(Item=dynamo_item)
                return True
            except ClientError as e:
                logger.error(f"DynamoDB put_item failed: {e}")

        # Local storage fallback
        self._local_cache[finding.finding_id] = item
        self._save_local_cache()
        return True

    def get_finding(self, finding_id: str) -> Optional[WasteFinding]:
        if self.is_dynamo_available and self.table:
            try:
                response = self.table.get_item(Key={"finding_id": finding_id})
                item = response.get("Item")
                if item:
                    # Convert Decimals back
                    clean_item = json.loads(json.dumps(item, default=str))
                    clean_item["monthly_cost_usd"] = float(clean_item["monthly_cost_usd"])
                    return WasteFinding(**clean_item)
            except ClientError as e:
                logger.error(f"DynamoDB get_item failed: {e}")

        if finding_id in self._local_cache:
            return WasteFinding(**self._local_cache[finding_id])
        return None

    def update_status(
        self,
        finding_id: str,
        status: ApprovalStatus,
        approved_by: Optional[str] = None,
        execution_result: Optional[str] = None,
    ) -> bool:
        now_str = datetime.now(timezone.utc).isoformat()
        if self.is_dynamo_available and self.table:
            try:
                update_expr = "SET #s = :status, updated_at = :now"
                expr_names = {"#s": "status"}
                expr_values = {":status": status.value, ":now": now_str}

                if approved_by:
                    update_expr += ", approved_by = :approver"
                    expr_values[":approver"] = approved_by
                if execution_result:
                    update_expr += ", execution_result = :res, executed_at = :exec_at"
                    expr_values[":res"] = execution_result
                    expr_values[":exec_at"] = now_str

                self.table.update_item(
                    Key={"finding_id": finding_id},
                    UpdateExpression=update_expr,
                    ExpressionAttributeNames=expr_names,
                    ExpressionAttributeValues=expr_values,
                )
                return True
            except ClientError as e:
                logger.error(f"DynamoDB update_item failed: {e}")

        if finding_id in self._local_cache:
            item = self._local_cache[finding_id]
            item["status"] = status.value
            if approved_by:
                item["approved_by"] = approved_by
            if execution_result:
                item["execution_result"] = execution_result
                item["executed_at"] = now_str
            self._save_local_cache()
            return True
        return False

    def list_findings(self, status: Optional[ApprovalStatus] = None) -> List[WasteFinding]:
        results: List[WasteFinding] = []
        if self.is_dynamo_available and self.table:
            try:
                response = self.table.scan()
                for item in response.get("Items", []):
                    clean_item = json.loads(json.dumps(item, default=str))
                    clean_item["monthly_cost_usd"] = float(clean_item["monthly_cost_usd"])
                    f = WasteFinding(**clean_item)
                    if not status or f.status == status:
                        results.append(f)
                return results
            except ClientError as e:
                logger.error(f"DynamoDB scan failed: {e}")

        for item in self._local_cache.values():
            f = WasteFinding(**item)
            if not status or f.status == status:
                results.append(f)
        return results
