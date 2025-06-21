"""Configuration service interface."""

from abc import ABC, abstractmethod
from typing import Any, Dict, List, Optional, Union
from core.models.config import WorkflowConfig, LandingZoneConfig


class IConfigService(ABC):
    """Interface for configuration management."""
    
    @abstractmethod
    async def load_workflow_config(self, config_path: str) -> WorkflowConfig:
        """Load workflow configuration from file.
        
        Args:
            config_path: Path to the configuration file
            
        Returns:
            WorkflowConfig object
            
        Raises:
            ConfigurationError: If config is invalid or not found
        """
        pass
    
    @abstractmethod
    async def load_landing_zones(self, config_path: Optional[str] = None) -> List[LandingZoneConfig]:
        """Load landing zone configurations.
        
        Args:
            config_path: Optional path to landing zones config
            
        Returns:
            List of LandingZoneConfig objects
        """
        pass
    
    @abstractmethod
    async def validate_config(self, config: Dict[str, Any]) -> bool:
        """Validate configuration against schema.
        
        Args:
            config: Configuration dictionary to validate
            
        Returns:
            True if valid, raises exception if invalid
            
        Raises:
            ValidationError: If configuration is invalid
        """
        pass
    
    @abstractmethod
    def get_setting(self, key: str, default: Any = None) -> Any:
        """Get a configuration setting by key.
        
        Args:
            key: Setting key (supports dot notation)
            default: Default value if key not found
            
        Returns:
            Configuration value or default
        """
        pass
    
    @abstractmethod
    def get_aws_config(self) -> Dict[str, Any]:
        """Get AWS-specific configuration.
        
        Returns:
            Dictionary with AWS configuration
        """
        pass
    
    @abstractmethod
    def get_environment_config(self, environment: str) -> Dict[str, Any]:
        """Get environment-specific configuration.
        
        Args:
            environment: Environment name ('nonprod', 'preprod', 'prod')
            
        Returns:
            Environment-specific configuration
        """
        pass
    
    @abstractmethod
    def get_phase_config(self, phase_name: str) -> Dict[str, Any]:
        """Get configuration for a specific workflow phase.
        
        Args:
            phase_name: Name of the workflow phase
            
        Returns:
            Phase-specific configuration
        """
        pass
    
    @abstractmethod
    async def reload_config(self) -> None:
        """Reload configuration from source."""
        pass