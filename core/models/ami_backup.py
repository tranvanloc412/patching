"""AMI backup data models."""

from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Dict, Any, Optional, List
from uuid import uuid4


class BackupStatus(Enum):
    """AMI backup status."""
    PENDING = "pending"
    CREATING = "creating"
    AVAILABLE = "available"
    FAILED = "failed"


class BackupType(Enum):
    """Type of backup operation."""
    PRE_PATCH = "pre_patch"
    POST_PATCH = "post_patch"
    MANUAL = "manual"


@dataclass
class AMIBackup:
    """Simplified AMI backup data model."""
    
    # Required fields
    instance_id: str
    
    # Auto-generated fields
    backup_id: str = field(default_factory=lambda: str(uuid4()))
    created_time: datetime = field(default_factory=datetime.utcnow)
    
    # Basic backup info
    ami_id: Optional[str] = None
    ami_name: Optional[str] = None
    description: Optional[str] = None
    backup_type: BackupType = BackupType.PRE_PATCH
    status: BackupStatus = BackupStatus.PENDING
    
    # Timing
    start_time: Optional[datetime] = None
    completion_time: Optional[datetime] = None
    
    # AWS context
    region: str = ""
    account_id: str = ""
    
    # Error handling
    error_message: Optional[str] = None
    
    # Tags and metadata
    tags: Dict[str, str] = field(default_factory=dict)
    configuration: Dict[str, Any] = field(default_factory=dict)
    
    # Retention (simplified)
    retention_days: int = 30

    def __post_init__(self):
        """Initialize backup with defaults."""
        # Generate AMI name if not provided
        if not self.ami_name:
            timestamp = self.created_time.strftime("%Y%m%d-%H%M%S")
            self.ami_name = f"backup-{self.instance_id}-{timestamp}"
        
        # Set basic tags
        if not self.tags:
            self.tags = {
                "Name": self.ami_name,
                "SourceInstanceId": self.instance_id,
                "BackupType": self.backup_type.value,
                "CreatedBy": "PatchingWorkflow",
                "CreatedDate": self.created_time.strftime("%Y-%m-%d")
            }

    @property
    def is_completed(self) -> bool:
        """Check if backup completed successfully."""
        return self.status == BackupStatus.AVAILABLE
    
    @property
    def is_failed(self) -> bool:
        """Check if backup failed."""
        return self.status == BackupStatus.FAILED
    
    @property
    def is_in_progress(self) -> bool:
        """Check if backup is in progress."""
        return self.status == BackupStatus.CREATING

    def start(self) -> None:
        """Mark backup as started."""
        self.status = BackupStatus.CREATING
        self.start_time = datetime.utcnow()
    
    def mark_started(self) -> None:
        """Mark backup as started (alias for start method)."""
        self.start()
    
    def complete(self, ami_id: str) -> None:
        """Mark backup as completed."""
        self.status = BackupStatus.AVAILABLE
        self.ami_id = ami_id
        self.completion_time = datetime.utcnow()
    
    def fail(self, error_message: str) -> None:
        """Mark backup as failed."""
        self.status = BackupStatus.FAILED
        self.error_message = error_message
        self.completion_time = datetime.utcnow()
    
    def mark_failed(self, error_message: str) -> None:
        """Mark backup as failed (alias for fail method)."""
        self.fail(error_message)
    
    def mark_completed(self, ami_id: str) -> None:
        """Mark backup as completed (alias for complete method)."""
        self.complete(ami_id)
    
    def update_progress(self, progress: float, status: str) -> None:
        """Update backup progress."""
        # For now, just update the status if it's a valid BackupStatus
        if status == "ami_created":
            self.status = BackupStatus.CREATING

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary."""
        return {
            "backup_id": self.backup_id,
            "instance_id": self.instance_id,
            "ami_id": self.ami_id,
            "ami_name": self.ami_name,
            "backup_type": self.backup_type.value,
            "status": self.status.value,
            "created_time": self.created_time.isoformat(),
            "start_time": self.start_time.isoformat() if self.start_time else None,
            "completion_time": self.completion_time.isoformat() if self.completion_time else None,
            "region": self.region,
            "account_id": self.account_id,
            "error_message": self.error_message,
            "tags": self.tags,
            "retention_days": self.retention_days
        }
