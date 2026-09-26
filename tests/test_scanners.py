from unittest.mock import MagicMock
from src.models import ActionType, ResourceType
from src.scanners.ebs import EBSWasteScanner
from src.scanners.eip import EIPWasteScanner
from src.scanners.lambda_fn import LambdaWasteScanner
from src.scanners.rds import RDSWasteScanner


def test_ebs_scanner_detects_unattached_volume():
    mock_ec2 = MagicMock()
    mock_paginator = MagicMock()
    mock_paginator.paginate.return_value = [
        {
            "Volumes": [
                {
                    "VolumeId": "vol-0abc123",
                    "Size": 100,
                    "VolumeType": "gp3",
                    "State": "available",
                    "Tags": [{"Key": "Environment", "Value": "staging"}],
                }
            ]
        }
    ]
    mock_ec2.get_paginator.return_value = mock_paginator

    scanner = EBSWasteScanner(ec2_client=mock_ec2)
    findings = scanner.scan()

    assert len(findings) == 1
    f = findings[0]
    assert f.resource_id == "vol-0abc123"
    assert f.resource_type == ResourceType.EBS_VOLUME
    assert f.monthly_cost_usd == 8.00  # 100GB * 0.08
    assert f.recommended_action == ActionType.DELETE_EBS_WITH_SNAPSHOT
    assert f.tags == {"Environment": "staging"}


def test_eip_scanner_detects_unattached_address():
    mock_ec2 = MagicMock()
    mock_ec2.describe_addresses.return_value = {
        "Addresses": [
            {
                "AllocationId": "eipalloc-998877",
                "PublicIp": "52.1.2.3",
                # No InstanceId or NetworkInterfaceId -> idle
                "Tags": [{"Key": "Project", "Value": "Demo"}],
            },
            {
                "AllocationId": "eipalloc-attached",
                "PublicIp": "52.4.5.6",
                "InstanceId": "i-12345678",  # In use -> not waste
            },
        ]
    }

    scanner = EIPWasteScanner(ec2_client=mock_ec2)
    findings = scanner.scan()

    assert len(findings) == 1
    assert findings[0].resource_id == "eipalloc-998877"
    assert findings[0].monthly_cost_usd == 3.65
    assert findings[0].recommended_action == ActionType.RELEASE_EIP


def test_rds_scanner_detects_idle_database():
    mock_rds = MagicMock()
    mock_cw = MagicMock()

    mock_paginator = MagicMock()
    mock_paginator.paginate.return_value = [
        {
            "DBInstances": [
                {
                    "DBInstanceIdentifier": "dev-reporting-db",
                    "DBInstanceClass": "db.t3.micro",
                    "DBInstanceStatus": "available",
                    "Engine": "postgres",
                    "TagList": [{"Key": "Env", "Value": "dev"}],
                }
            ]
        }
    ]
    mock_rds.get_paginator.return_value = mock_paginator

    # Mock CloudWatch returning low CPU (0.5% average)
    mock_cw.get_metric_statistics.return_value = {
        "Datapoints": [{"Average": 0.5}]
    }

    scanner = RDSWasteScanner(rds_client=mock_rds, cloudwatch_client=mock_cw)
    findings = scanner.scan()

    assert len(findings) == 1
    f = findings[0]
    assert f.resource_id == "dev-reporting-db"
    assert f.monthly_cost_usd == 12.41
    assert f.recommended_action == ActionType.STOP_RDS_INSTANCE


def test_lambda_scanner_detects_overprovisioned_memory():
    mock_lambda = MagicMock()
    mock_paginator = MagicMock()
    mock_paginator.paginate.return_value = [
        {
            "Functions": [
                {
                    "FunctionName": "image-resizer",
                    "MemorySize": 1024,
                    "Runtime": "python3.12",
                    "FunctionArn": "arn:aws:lambda:us-east-1:123456:function:image-resizer",
                }
            ]
        }
    ]
    mock_lambda.get_paginator.return_value = mock_paginator
    mock_lambda.list_tags.return_value = {
        "Tags": {"ReportedMaxMemoryMB": "80"}
    }

    scanner = LambdaWasteScanner(lambda_client=mock_lambda)
    findings = scanner.scan()

    assert len(findings) == 1
    f = findings[0]
    assert f.resource_id == "image-resizer"
    assert f.recommended_action == ActionType.RIGHTSIZE_LAMBDA_MEMORY
    assert f.action_details["recommended_memory_mb"] == 128
