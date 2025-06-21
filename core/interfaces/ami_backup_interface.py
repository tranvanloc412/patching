"""AMI backup service interface."""

from abc import ABC, abstractmethod
from typing import List, Dict, Any, Optional
from datetime import datetime
from core.models.instance import Instance
from core.models.ami_backup import AMIBackup, BackupResult


class IAMIBackupService(ABC):
    """Interface for AMI backup operations."""
    
    @abstractmethod
    async def create_backup(self, instance: Instance, 
                           description: Optional[str] = None,
                           tags: Optional[Dict[str, str]] = None) -> AMIBackup:
        """Create an AMI backup for a single instance.
        
        Args:
            instance: The instance to backup
            description: Optional backup description
            tags: Optional tags to apply to the AMI
            
        Returns:
            AMIBackup object with backup details
        """
        pass
    
    @abstractmethod
    async def create_multiple_backups(self, instances: List[Instance],
                                     description_template: Optional[str] = None,
                                     tags: Optional[Dict[str, str]] = None,
                                     max_concurrent: int = 5) -> List[BackupResult]:
        """Create AMI backups for multiple instances concurrently.
        
        Args:
            instances: List of instances to backup
            description_template: Template for backup descriptions
            tags: Tags to apply to all AMIs
            max_concurrent: Maximum concurrent backup operations
            
        Returns:
            List of BackupResult objects
        """
        pass
    
    @abstractmethod
    async def wait_for_backup_completion(self, ami_id: str, 
                                        timeout_seconds: int = 1800) -> bool:
        """Wait for an AMI backup to complete.
        
        Args:
            ami_id: The AMI ID to monitor
            timeout_seconds: Maximum time to wait
            
        Returns:
            True if backup completed successfully, False if timeout or failed
        """
        pass
    
    @abstractmethod
    async def get_backup_status(self, ami_id: str) -> str:
        """Get the current status of an AMI backup.
        
        Args:
            ami_id: The AMI ID to check
            
        Returns:
            Status string ('pending', 'available', 'failed', etc.)
        """
        pass
    
    @abstractmethod
    async def cleanup_old_backups(self, instance_id: str, 
                                 retention_days: int = 7) -> List[str]:
        """Clean up old AMI backups for an instance.
        
        Args:
            instance_id: The instance ID
            retention_days: Number of days to retain backups
            
        Returns:
            List of deleted AMI IDs
        """
        pass
    
    @abstractmethod
    async def list_backups_for_instance(self, instance_id: str) -> List[AMIBackup]:
        """List all AMI backups for a specific instance.
        
        Args:
            instance_id: The instance ID
            
        Returns:
            List of AMIBackup objects
        """
        pass