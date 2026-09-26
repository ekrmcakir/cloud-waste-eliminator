from abc import ABC, abstractmethod
from typing import Dict, List
from src.models import ResourceType, WasteFinding


class BaseScanner(ABC):
    name: str = "base_scanner"
    resource_type: ResourceType

    @abstractmethod
    def scan(self) -> List[WasteFinding]:
        """Scan AWS account for wasted or unoptimized resources."""
        raise NotImplementedError

    @staticmethod
    def parse_aws_tags(tag_list: List[Dict[str, str]]) -> Dict[str, str]:
        """Convert AWS [{'Key': 'k', 'Value': 'v'}] list to a standard dictionary."""
        if not tag_list:
            return {}
        return {t.get("Key", ""): t.get("Value", "") for t in tag_list if "Key" in t}
