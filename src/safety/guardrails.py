from typing import Tuple
from src.config import default_config
from src.models import ActionType, ApprovalStatus, RiskLevel, WasteFinding


class FinOpsGuardrail:
    """Safety guardrail preventing accidental termination or disruptive remediation."""

    def __init__(self, config=default_config):
        self.config = config

    def evaluate(self, finding: WasteFinding) -> Tuple[bool, str]:
        """
        Evaluates whether a finding is eligible for remediation.
        Returns: (is_eligible: bool, reason: str)
        """
        tags_lower = {k.lower(): str(v).lower() for k, v in finding.tags.items()}

        # 1. Check explicit exclusion tags
        for key in self.config.exclusion_tag_keys:
            if key in tags_lower:
                val = tags_lower[key]
                if val in ("true", "1", "yes", "enabled"):
                    finding.status = ApprovalStatus.EXCLUDED
                    return False, f"Protected by tag: {key}={val}"

        # 2. Production environment safeguard
        for env_key in ("env", "environment", "stage"):
            if env_key in tags_lower:
                env_val = tags_lower[env_key]
                if env_val in self.config.protected_environments:
                    # Production resources are never automated; require high-risk strict manual review
                    finding.risk_level = RiskLevel.HIGH
                    return (
                        False,
                        f"Production environment tag detected ({env_key}={env_val}). Automated execution blocked.",
                    )

        # 3. Guard against deleting critical EBS volumes without snapshot
        if finding.recommended_action == ActionType.DELETE_EBS_WITH_SNAPSHOT:
            if not finding.action_details.get("require_snapshot", True):
                return False, "EBS deletion requires snapshot flag to be enabled."

        # 4. Check if cost is negative or invalid
        if finding.monthly_cost_usd < 0:
            return False, "Invalid negative cost calculation."

        return True, "Passed safety guardrails"
