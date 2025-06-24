"""Scanner service interface for instance discovery."""

from abc import ABC, abstractmethod
from typing import List, Dict, Any, Optional
from core.models.instance import Instance
from core.models.config import LandingZoneConfig


class IScannerService(ABC):
    """Interface for scanning and discovering EC2 instances."""
    
    @abstractmethod
    async def scan_landing_zone(self, landing_zone_config: LandingZoneConfig, 
                               platform_filter: Optional[str] = None) -> List[Instance]:
        """Scan a specific landing zone for instances.
        
        Args:
            landing_zone_config: The landing zone configuration to scan
            platform_filter: Optional platform filter ('windows', 'linux')
            
        Returns:
            List of discovered instances
        """
        pass
    
    @abstractmethod
    async def scan_multiple_landing_zones(self, landing_zone_configs: List[LandingZoneConfig],
                                         platform_filter: Optional[str] = None) -> Dict[str, List[Instance]]:
        """Scan multiple landing zones concurrently.
        
        Args:
            landing_zone_configs: List of landing zone configurations to scan
            platform_filter: Optional platform filter
            
        Returns:
            Dictionary mapping landing zone names to lists of instances
        """
        pass
    
    @abstractmethod
    async def get_instance_details(self, instance_id: str, 
                                  landing_zone_config: LandingZoneConfig) -> Optional[Instance]:
        """Get detailed information for a specific instance.
        
        Args:
            instance_id: The EC2 instance ID
            landing_zone_config: The landing zone configuration containing the instance
            
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