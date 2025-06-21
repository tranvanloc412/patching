"""Server manager service interface."""

from abc import ABC, abstractmethod
from typing import List, Dict, Any, Optional
from core.models.instance import Instance
from core.models.server_operation import ServerOperation, OperationResult


class IServerManagerService(ABC):
    """Interface for server state management operations."""
    
    @abstractmethod
    async def start_instance(self, instance: Instance) -> OperationResult:
        """Start a stopped EC2 instance.
        
        Args:
            instance: The instance to start
            
        Returns:
            OperationResult with success status and details
        """
        pass
    
    @abstractmethod
    async def stop_instance(self, instance: Instance) -> OperationResult:
        """Stop a running EC2 instance.
        
        Args:
            instance: The instance to stop
            
        Returns:
            OperationResult with success status and details
        """
        pass
    
    @abstractmethod
    async def restart_instance(self, instance: Instance) -> OperationResult:
        """Restart an EC2 instance.
        
        Args:
            instance: The instance to restart
            
        Returns:
            OperationResult with success status and details
        """
        pass
    
    @abstractmethod
    async def start_multiple_instances(self, instances: List[Instance],
                                      max_concurrent: int = 10) -> List[OperationResult]:
        """Start multiple instances concurrently.
        
        Args:
            instances: List of instances to start
            max_concurrent: Maximum concurrent operations
            
        Returns:
            List of OperationResult objects
        """
        pass
    
    @abstractmethod
    async def wait_for_instance_state(self, instance: Instance, 
                                     target_state: str,
                                     timeout_seconds: int = 300) -> bool:
        """Wait for an instance to reach a specific state.
        
        Args:
            instance: The instance to monitor
            target_state: Target state ('running', 'stopped', etc.)
            timeout_seconds: Maximum time to wait
            
        Returns:
            True if target state reached, False if timeout
        """
        pass
    
    @abstractmethod
    async def get_instance_state(self, instance: Instance) -> str:
        """Get the current state of an instance.
        
        Args:
            instance: The instance to check
            
        Returns:
            Current state string
        """
        pass
    
    @abstractmethod
    async def validate_instance_readiness(self, instance: Instance) -> Dict[str, Any]:
        """Validate if an instance is ready for patching.
        
        Args:
            instance: The instance to validate
            
        Returns:
            Dictionary with validation results
        """
        pass
    
    @abstractmethod
    async def get_instance_health_status(self, instances: List[Instance]) -> Dict[str, Dict[str, Any]]:
        """Get health status for multiple instances.
        
        Args:
            instances: List of instances to check
            
        Returns:
            Dictionary mapping instance IDs to health status
        """
        pass