"""AMI backup data models."""

from dataclasses import dataclass, field
from datetime import datetime, timedelta
from enum import Enum
from typing import Dict, Any, Optional, List
from uuid import uuid4


class BackupStatus(Enum):
    """AMI backup status."""
    PENDING = "pending"
    CREATING = "creating"
    AVAILABLE = "available"
    FAILED = "failed"
    CANCELLED = "cancelled"
    DEREGISTERED = "deregistered"
    ERROR = "error"


class BackupType(Enum):
    """Type of backup operation."""
    MANUAL = "manual"
    SCHEDULED = "scheduled"
    PRE_PATCH = "pre_patch"
    POST_PATCH = "post_patch"
    EMERGENCY = "emergency"


@dataclass
class BackupConfiguration:
    """Configuration for AMI backup operations."""
    
    # Backup behavior
    no_reboot: bool = True
    include_all_volumes: bool = True
    copy_tags: bool = True
    
    # Description template
    description_template: str = "Pre-patch backup for {instance_id} - {timestamp}"
    
    # Retention settings
    retention_days: int = 30
    max_backups_per_instance: int = 5
    
    # Tagging
    additional_tags: Dict[str, str] = field(default_factory=dict)
    
    # Timeout and retry
    timeout_minutes: int = 60
    retry_attempts: int = 2
    retry_delay_minutes: int = 5
    
    # Notification settings
    notify_on_completion: bool = False
    notify_on_failure: bool = True
    notification_targets: List[str] = field(default_factory=list)


@dataclass
class BlockDeviceMapping:
    """Block device mapping for AMI."""
    device_name: str
    volume_id: Optional[str] = None
    volume_size: Optional[int] = None
    volume_type: Optional[str] = None
    encrypted: Optional[bool] = None
    snapshot_id: Optional[str] = None
    delete_on_termination: bool = True
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary representation."""
        return {
            'device_name': self.device_name,
            'volume_id': self.volume_id,
            'volume_size': self.volume_size,
            'volume_type': self.volume_type,
            'encrypted': self.encrypted,
            'snapshot_id': self.snapshot_id,
            'delete_on_termination': self.delete_on_termination
        }


@dataclass
class AMIBackup:
    """AMI backup data model."""
    
    # Backup identification
    backup_id: str = field(default_factory=lambda: str(uuid4()))
    ami_id: Optional[str] = None
    ami_name: Optional[str] = None
    
    # Source instance information
    instance_id: str = ""
    source_ami_id: Optional[str] = None
    
    # Backup metadata
    backup_type: BackupType = BackupType.PRE_PATCH
    description: str = ""
    
    # Status and timing
    status: BackupStatus = BackupStatus.PENDING
    created_time: datetime = field(default_factory=datetime.utcnow)
    start_time: Optional[datetime] = None
    completion_time: Optional[datetime] = None
    
    # Configuration
    configuration: BackupConfiguration = field(default_factory=BackupConfiguration)
    
    # AWS details
    region: str = ""
    account_id: str = ""
    landing_zone: str = ""
    
    # Image details
    architecture: Optional[str] = None
    platform: Optional[str] = None
    virtualization_type: Optional[str] = None
    root_device_type: Optional[str] = None
    
    # Block device mappings
    block_device_mappings: List[BlockDeviceMapping] = field(default_factory=list)
    
    # Tags
    tags: Dict[str, str] = field(default_factory=dict)
    
    # Error information
    error_message: Optional[str] = None
    error_code: Optional[str] = None
    
    # Progress tracking
    progress_percentage: float = 0.0
    current_step: str = "pending"
    
    # Snapshots created
    snapshot_ids: List[str] = field(default_factory=list)
    
    # Workflow context
    workflow_id: Optional[str] = None
    phase: Optional[str] = None
    
    # Metadata
    metadata: Dict[str, Any] = field(default_factory=dict)
    
    def __post_init__(self):
        """Post-initialization validation."""
        if not self.instance_id:
            raise ValueError("instance_id is required")
        
        # Generate AMI name if not provided
        if not self.ami_name:
            timestamp = self.created_time.strftime("%Y%m%d-%H%M%S")
            self.ami_name = f"prepatch-backup-{self.instance_id}-{timestamp}"
        
        # Generate description if not provided
        if not self.description:
            timestamp = self.created_time.strftime("%Y-%m-%d %H:%M:%S")
            self.description = self.configuration.description_template.format(
                instance_id=self.instance_id,
                timestamp=timestamp
            )
        
        # Set default tags
        default_tags = {
            "Name": self.ami_name,
            "SourceInstanceId": self.instance_id,
            "BackupType": self.backup_type.value,
            "CreatedBy": "PrePatchWorkflow",
            "CreatedDate": self.created_time.strftime("%Y-%m-%d"),
            "Purpose": "PrePatchBackup"
        }
        
        # Merge with existing tags
        for key, value in default_tags.items():
            if key not in self.tags:
                self.tags[key] = value
        
        # Add configuration tags
        self.tags.update(self.configuration.additional_tags)
    
    @property
    def duration(self) -> Optional[timedelta]:
        """Calculate backup duration."""
        if self.start_time and self.completion_time:
            return self.completion_time - self.start_time
        return None
    
    @property
    def is_completed(self) -> bool:
        """Check if backup is completed successfully."""
        return self.status == BackupStatus.AVAILABLE
    
    @property
    def is_failed(self) -> bool:
        """Check if backup failed."""
        return self.status in [BackupStatus.FAILED, BackupStatus.ERROR, BackupStatus.CANCELLED]
    
    @property
    def is_in_progress(self) -> bool:
        """Check if backup is currently in progress."""
        return self.status == BackupStatus.CREATING
    
    @property
    def is_expired(self) -> bool:
        """Check if backup has expired based on retention policy."""
        if self.completion_time:
            expiry_date = self.completion_time + timedelta(days=self.configuration.retention_days)
            return datetime.utcnow() > expiry_date
        return False
    
    @property
    def age_days(self) -> int:
        """Get backup age in days."""
        if self.completion_time:
            return (datetime.utcnow() - self.completion_time).days
        return (datetime.utcnow() - self.created_time).days
    
    def mark_started(self) -> None:
        """Mark backup as started."""
        self.status = BackupStatus.CREATING
        self.start_time = datetime.utcnow()
        self.current_step = "creating_ami"
        self.progress_percentage = 10.0
    
    def mark_completed(self, ami_id: str, snapshot_ids: Optional[List[str]] = None) -> None:
        """Mark backup as completed successfully."""
        self.status = BackupStatus.AVAILABLE
        self.ami_id = ami_id
        self.completion_time = datetime.utcnow()
        self.current_step = "completed"
        self.progress_percentage = 100.0
        
        if snapshot_ids:
            self.snapshot_ids = snapshot_ids
    
    def mark_failed(self, error_message: str, error_code: Optional[str] = None) -> None:
        """Mark backup as failed."""
        self.status = BackupStatus.FAILED
        self.completion_time = datetime.utcnow()
        self.error_message = error_message
        self.error_code = error_code
        self.current_step = "failed"
    
    def update_progress(self, percentage: float, step: str) -> None:
        """Update backup progress."""
        self.progress_percentage = min(100.0, max(0.0, percentage))
        self.current_step = step
    
    def add_block_device_mapping(self, mapping: BlockDeviceMapping) -> None:
        """Add a block device mapping."""
        self.block_device_mappings.append(mapping)
    
    def get_cleanup_date(self) -> datetime:
        """Get the date when this backup should be cleaned up."""
        base_date = self.completion_time or self.created_time
        return base_date + timedelta(days=self.configuration.retention_days)
    
    def should_be_cleaned_up(self) -> bool:
        """Check if backup should be cleaned up based on retention policy."""
        return datetime.utcnow() > self.get_cleanup_date()
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert backup to dictionary representation."""
        return {
            'backup_id': self.backup_id,
            'ami_id': self.ami_id,
            'ami_name': self.ami_name,
            'instance_id': self.instance_id,
            'source_ami_id': self.source_ami_id,
            'backup_type': self.backup_type.value,
            'description': self.description,
            'status': self.status.value,
            'created_time': self.created_time.isoformat(),
            'start_time': self.start_time.isoformat() if self.start_time else None,
            'completion_time': self.completion_time.isoformat() if self.completion_time else None,
            'duration_seconds': self.duration.total_seconds() if self.duration else None,
            'region': self.region,
            'account_id': self.account_id,
            'landing_zone': self.landing_zone,
            'architecture': self.architecture,
            'platform': self.platform,
            'virtualization_type': self.virtualization_type,
            'root_device_type': self.root_device_type,
            'block_device_mappings': [bdm.to_dict() for bdm in self.block_device_mappings],
            'tags': self.tags,
            'error_message': self.error_message,
            'error_code': self.error_code,
            'progress_percentage': self.progress_percentage,
            'current_step': self.current_step,
            'snapshot_ids': self.snapshot_ids,
            'workflow_id': self.workflow_id,
            'phase': self.phase,
            'age_days': self.age_days,
            'is_expired': self.is_expired,
            'cleanup_date': self.get_cleanup_date().isoformat(),
            'metadata': self.metadata
        }
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'AMIBackup':
        """Create AMI backup from dictionary representation."""
        # Convert enum values
        if 'backup_type' in data:
            data['backup_type'] = BackupType(data['backup_type'])
        if 'status' in data:
            data['status'] = BackupStatus(data['status'])
        
        # Convert datetime strings
        datetime_fields = ['created_time', 'start_time', 'completion_time']
        for field in datetime_fields:
            if field in data and isinstance(data[field], str):
                data[field] = datetime.fromisoformat(data[field])
        
        # Convert block device mappings
        if 'block_device_mappings' in data:
            mappings = []
            for bdm_data in data['block_device_mappings']:
                mapping = BlockDeviceMapping(**bdm_data)
                mappings.append(mapping)
            data['block_device_mappings'] = mappings
        
        # Remove computed fields
        computed_fields = ['duration_seconds', 'age_days', 'is_expired', 'cleanup_date']
        for field in computed_fields:
            data.pop(field, None)
        
        return cls(**data)