"""Storage service interface."""

from abc import ABC, abstractmethod
from typing import List, Dict, Any, Optional, Union
from pathlib import Path
from core.models.instance import Instance
from core.models.report import Report


class IStorageService(ABC):
    """Interface for data storage and retrieval operations."""
    
    @abstractmethod
    async def save_instances_to_csv(self, instances: List[Instance], 
                                   file_path: Union[str, Path]) -> bool:
        """Save instances data to CSV file.
        
        Args:
            instances: List of instances to save
            file_path: Path where to save the CSV file
            
        Returns:
            True if successful, False otherwise
        """
        pass
    
    @abstractmethod
    async def load_instances_from_csv(self, file_path: Union[str, Path]) -> List[Instance]:
        """Load instances data from CSV file.
        
        Args:
            file_path: Path to the CSV file
            
        Returns:
            List of Instance objects
            
        Raises:
            FileNotFoundError: If file doesn't exist
            ValidationError: If CSV format is invalid
        """
        pass
    
    @abstractmethod
    async def save_report(self, report: Report, 
                         file_path: Union[str, Path],
                         format_type: str = 'json') -> bool:
        """Save report to file.
        
        Args:
            report: Report object to save
            file_path: Path where to save the report
            format_type: Format type ('json', 'yaml', 'csv')
            
        Returns:
            True if successful, False otherwise
        """
        pass
    
    @abstractmethod
    async def load_report(self, file_path: Union[str, Path],
                         format_type: str = 'json') -> Report:
        """Load report from file.
        
        Args:
            file_path: Path to the report file
            format_type: Format type ('json', 'yaml', 'csv')
            
        Returns:
            Report object
        """
        pass
    
    @abstractmethod
    async def create_backup(self, file_path: Union[str, Path]) -> str:
        """Create a backup of a file.
        
        Args:
            file_path: Path to the file to backup
            
        Returns:
            Path to the backup file
        """
        pass
    
    @abstractmethod
    async def list_files(self, directory: Union[str, Path], 
                        pattern: Optional[str] = None) -> List[Path]:
        """List files in a directory.
        
        Args:
            directory: Directory to list
            pattern: Optional file pattern to match
            
        Returns:
            List of file paths
        """
        pass
    
    @abstractmethod
    async def ensure_directory(self, directory: Union[str, Path]) -> bool:
        """Ensure directory exists, create if necessary.
        
        Args:
            directory: Directory path
            
        Returns:
            True if directory exists or was created
        """
        pass
    
    @abstractmethod
    async def cleanup_old_files(self, directory: Union[str, Path],
                               max_age_days: int = 30,
                               pattern: Optional[str] = None) -> List[Path]:
        """Clean up old files in a directory.
        
        Args:
            directory: Directory to clean
            max_age_days: Maximum age in days
            pattern: Optional file pattern to match
            
        Returns:
            List of deleted file paths
        """
        pass