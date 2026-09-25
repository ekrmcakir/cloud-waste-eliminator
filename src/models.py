from datetime import datetime, timezone
from enum import Enum
from typing import Any, Dict, List, Optional
from pydantic import BaseModel, Field


class ResourceType(str, Enum):
    EBS_VOLUME = "ebs_volume"
    ELASTIC_IP = "elastic_ip"
    RDS_INSTANCE = "rds_instance"
    LAMBDA_FUNCTION = "lambda_function"


class ActionType(str, Enum):
    DELETE_EBS_WITH_SNAPSHOT = "delete_ebs_with_snapshot"
    RELEASE_EIP = "release_eip"
    STOP_RDS_INSTANCE = "stop_rds_instance"
    RIGHTSIZE_LAMBDA_MEMORY = "rightsize_lambda_memory"


class ApprovalStatus(str, Enum):
    PENDING_APPROVAL = "PENDING_APPROVAL"
    APPROVED = "APPROVED"
    REJECTED = "REJECTED"
    EXECUTED = "EXECUTED"
    FAILED = "FAILED"
    EXCLUDED = "EXCLUDED"


class RiskLevel(str, Enum):
    LOW = "LOW"
    MEDIUM = "MEDIUM"
    HIGH = "HIGH"


class WasteFinding(BaseModel):
    finding_id: str
    resource_id: str
    resource_type: ResourceType
    region: str = "us-east-1"
    monthly_cost_usd: float = 0.0
    waste_reason: str
    recommended_action: ActionType
    action_details: Dict[str, Any] = Field(default_factory=dict)
    tags: Dict[str, str] = Field(default_factory=dict)
    status: ApprovalStatus = ApprovalStatus.PENDING_APPROVAL
    ai_analysis: Optional[str] = None
    risk_level: RiskLevel = RiskLevel.LOW
    created_at: str = Field(default_factory=lambda: datetime.now(timezone.utc).isoformat())
    approved_by: Optional[str] = None
    executed_at: Optional[str] = None
    execution_result: Optional[str] = None


class WasteReport(BaseModel):
    scan_id: str
    timestamp: str = Field(default_factory=lambda: datetime.now(timezone.utc).isoformat())
    region: str = "us-east-1"
    total_monthly_waste_usd: float = 0.0
    estimated_annual_savings_usd: float = 0.0
    findings_count: int = 0
    findings: List[WasteFinding] = Field(default_factory=list)
    ai_summary: Optional[str] = None
