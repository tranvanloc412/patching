"""Scanner service interface for instance discovery."""

from abc import ABC, abstractmethod
from typing import List, Dict, Any, Optional
from core.models.instance import Instance
from core.models.landing_zone import LandingZone
from core.models.scan_result import ScanResult


class IScannerService(ABC):
    """Interface for scanning and discovering EC2 instances."""
    
    @abstractmethod
    async def scan_landing_zone(self, landing_zone: LandingZone, 
                               platform_filter: Optional[str] = None) -> ScanResult:
        """Scan a specific landing zone for instances.
        
        Args:
            landing_zone: The landing zone to scan
            platform_filter: Optional platform filter ('windows', 'linux')
            
        Returns:
            ScanResult containing discovered instances and metadata
        """
        pass
    
    @abstractmethod
    async def scan_multiple_landing_zones(self, landing_zones: List[LandingZone],
                                         platform_filter: Optional[str] = None) -> List[ScanResult]:
        """Scan multiple landing zones concurrently.
        
        Args:
            landing_zones: List of landing zones to scan
            platform_filter: Optional platform filter
            
        Returns:
            List of ScanResult objects
        """
        pass
    
    @abstractmethod
    async def get_instance_details(self, instance_id: str, 
                                  landing_zone: LandingZone) -> Optional[Instance]:
        """Get detailed information for a specific instance.
        
        Args:
            instance_id: The EC2 instance ID
            landing_zone: The landing zone containing the instance
            
        Returns:
            Instance object with detailed information or None if not found
        """
        pass
    
    @abstractmethod
    async def validate_ssm_connectivity(self, instances: List[Instance]) -> Dict[str, bool]:
        """Validate SSM connectivity for instances.
        
        Args:
            instances: List of instances to validate
            
        Returns:
            Dictionary mapping instance IDs to connectivity status
        """
        pass