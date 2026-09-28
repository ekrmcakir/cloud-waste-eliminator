from unittest.mock import MagicMock
from src.models import ActionType, ResourceType, WasteFinding
from src.remediation.executor import RemediationExecutor


def test_dry_run_does_not_mutate():
    mock_ec2 = MagicMock()
    executor = RemediationExecutor(ec2_client=mock_ec2, dry_run=True)

    finding = WasteFinding(
        finding_id="ebs-test",
        resource_id="vol-test1234",
        resource_type=ResourceType.EBS_VOLUME,
        monthly_cost_usd=15.0,
        waste_reason="unattached",
        recommended_action=ActionType.DELETE_EBS_WITH_SNAPSHOT,
        tags={"Env": "test"},
    )

    result = executor.execute(finding)
    assert result["success"] is True
    assert result["dry_run"] is True
    # Ensure neither snapshot nor delete was called
    mock_ec2.create_snapshot.assert_not_called()
    mock_ec2.delete_volume.assert_not_called()


def test_ebs_remediation_snapshots_then_deletes():
    mock_ec2 = MagicMock()
    mock_ec2.create_snapshot.return_value = {"SnapshotId": "snap-998877"}
    executor = RemediationExecutor(ec2_client=mock_ec2, dry_run=False)

    finding = WasteFinding(
        finding_id="ebs-1",
        resource_id="vol-cleanup",
        resource_type=ResourceType.EBS_VOLUME,
        monthly_cost_usd=25.0,
        waste_reason="unattached",
        recommended_action=ActionType.DELETE_EBS_WITH_SNAPSHOT,
        tags={"Env": "qa"},
    )

    result = executor.execute(finding)
    assert result["success"] is True
    assert result["snapshot_id"] == "snap-998877"

    mock_ec2.create_snapshot.assert_called_once()
    mock_ec2.delete_volume.assert_called_once_with(VolumeId="vol-cleanup")


def test_eip_remediation_releases_address():
    mock_ec2 = MagicMock()
    executor = RemediationExecutor(ec2_client=mock_ec2, dry_run=False)

    finding = WasteFinding(
        finding_id="eip-1",
        resource_id="eipalloc-112233",
        resource_type=ResourceType.ELASTIC_IP,
        monthly_cost_usd=3.65,
        waste_reason="unattached",
        recommended_action=ActionType.RELEASE_EIP,
        tags={},
    )

    result = executor.execute(finding)
    assert result["success"] is True
    mock_ec2.release_address.assert_called_once_with(AllocationId="eipalloc-112233")


def test_rds_remediation_stops_instance():
    mock_rds = MagicMock()
    executor = RemediationExecutor(rds_client=mock_rds, dry_run=False)

    finding = WasteFinding(
        finding_id="rds-1",
        resource_id="staging-db",
        resource_type=ResourceType.RDS_INSTANCE,
        monthly_cost_usd=40.0,
        waste_reason="idle",
        recommended_action=ActionType.STOP_RDS_INSTANCE,
        tags={"Env": "dev"},
    )

    result = executor.execute(finding)
    assert result["success"] is True
    mock_rds.stop_db_instance.assert_called_once_with(DBInstanceIdentifier="staging-db")


def test_lambda_remediation_updates_memory():
    mock_lambda = MagicMock()
    executor = RemediationExecutor(lambda_client=mock_lambda, dry_run=False)

    finding = WasteFinding(
        finding_id="lambda-1",
        resource_id="heavy-fn",
        resource_type=ResourceType.LAMBDA_FUNCTION,
        monthly_cost_usd=10.0,
        waste_reason="overprovisioned",
        recommended_action=ActionType.RIGHTSIZE_LAMBDA_MEMORY,
        action_details={"recommended_memory_mb": 256},
        tags={},
    )

    result = executor.execute(finding)
    assert result["success"] is True
    assert result["new_memory_mb"] == 256
    mock_lambda.update_function_configuration.assert_called_once_with(
        FunctionName="heavy-fn",
        MemorySize=256,
    )
