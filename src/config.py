import os
from dataclasses import dataclass, field
from typing import Set


@dataclass
class FinOpsConfig:
    aws_region: str = os.getenv("AWS_REGION", "us-east-1")
    dynamodb_table: str = os.getenv("FINOPS_TABLE_NAME", "finops-cloud-waste-findings")
    dry_run: bool = os.getenv("FINOPS_DRY_RUN", "true").lower() in ("true", "1", "yes")

    # Protection & Exclusion
    exclusion_tag_keys: Set[str] = field(default_factory=lambda: {
        "donotdelete", "finopsexclude", "keepalive", "protection"
    })
    protected_environments: Set[str] = field(default_factory=lambda: {
        "prod", "production"
    })

    # Detection Thresholds
    ebs_min_unattached_days: int = int(os.getenv("EBS_MIN_UNATTACHED_DAYS", "1"))
    rds_idle_cpu_threshold: float = float(os.getenv("RDS_IDLE_CPU_THRESHOLD", "2.0"))  # % CPU
    rds_idle_days: int = int(os.getenv("RDS_IDLE_DAYS", "7"))
    lambda_memory_slack_ratio: float = float(os.getenv("LAMBDA_MEMORY_SLACK_RATIO", "0.40"))  # < 40% utilized

    # AI Model
    bedrock_model_id: str = os.getenv(
        "BEDROCK_MODEL_ID", "amazon.nova-lite-v1:0"
    )
    enable_ai_advisor: bool = os.getenv("ENABLE_AI_ADVISOR", "true").lower() in ("true", "1", "yes")


default_config = FinOpsConfig()
