"""Instance data model."""

from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Optional, Dict, Any, List


class Platform(Enum):
    """Supported instance platforms."""
    WINDOWS = "windows"
    LINUX = "linux"


class InstanceStatus(Enum):
    """Instance status enumeration."""

    RUNNING = "running"
    STOPPED = "stopped"
    STOPPING = "stopping"
    STARTING = "starting"
    PENDING = "pending"
    SHUTTING_DOWN = "shutting-down"
    TERMINATED = "terminated"
    TERMINATING = "terminating"
    UNKNOWN = "unknown"


class SSMStatus(Enum):
    """SSM agent status."""

    ONLINE = "online"
    CONNECTION_LOST = "connection_lost"
    INACTIVE = "inactive"
    NOT_REGISTERED = "not_registered"
    UNKNOWN = "unknown"


@dataclass
class InstanceTags:
    """Instance tags structure."""

    name: Optional[str] = None
    environment: Optional[str] = None
    application: Optional[str] = None
    owner: Optional[str] = None
    cost_center: Optional[str] = None
    backup_required: Optional[bool] = None
    patch_group: Optional[str] = None
    maintenance_window: Optional[str] = None
    additional_tags: Dict[str, str] = field(default_factory=dict)


@dataclass
class InstanceNetworking:
    """Instance networking information."""

    vpc_id: Optional[str] = None
    subnet_id: Optional[str] = None
    private_ip: Optional[str] = None
    public_ip: Optional[str] = None
    security_groups: List[str] = field(default_factory=list)
    availability_zone: Optional[str] = None


@dataclass
class InstanceSpecs:
    """Instance specifications."""

    instance_type: Optional[str] = None
    cpu_cores: Optional[int] = None
    memory_gb: Optional[float] = None
    storage_gb: Optional[int] = None
    architecture: Optional[str] = None  # x86_64, arm64


@dataclass
class SSMInfo:
    """SSM agent information."""

    status: SSMStatus = SSMStatus.UNKNOWN
    agent_version: Optional[str] = None
    last_ping: Optional[datetime] = None
    platform_type: Optional[str] = None
    platform_name: Optional[str] = None
    platform_version: Optional[str] = None
    is_latest_version: Optional[bool] = None
    ping_status: Optional[str] = None


@dataclass
class Instance:
    """Comprehensive instance data model."""

    # Core identification
    instance_id: str
    landing_zone: str
    region: str
    account_id: str

    # Instance state
    status: InstanceStatus = InstanceStatus.UNKNOWN
    platform: Platform = Platform.LINUX

    # Instance details
    tags: InstanceTags = field(default_factory=InstanceTags)
    networking: InstanceNetworking = field(default_factory=InstanceNetworking)
    specs: InstanceSpecs = field(default_factory=InstanceSpecs)
    ssm_info: SSMInfo = field(default_factory=SSMInfo)

    # AMI information
    ami_id: Optional[str] = None
    ami_name: Optional[str] = None
    ami_description: Optional[str] = None

    # Timestamps
    launch_time: Optional[datetime] = None
    last_scan_time: Optional[datetime] = None
    last_backup_time: Optional[datetime] = None

    # Patching information
    patch_baseline: Optional[str] = None
    last_patch_time: Optional[datetime] = None
    pending_reboot: bool = False

    # Validation flags
    is_managed: bool = False
    is_patchable: bool = False
    validation_errors: List[str] = field(default_factory=list)

    # Additional metadata
    metadata: Dict[str, Any] = field(default_factory=dict)

    def __post_init__(self):
        """Post-initialization validation and processing."""
        # Ensure instance_id is not empty
        if not self.instance_id:
            raise ValueError("instance_id cannot be empty")

        # Set default name from tags if available
        if not self.tags.name and "Name" in self.tags.additional_tags:
            self.tags.name = self.tags.additional_tags["Name"]

    @property
    def display_name(self) -> str:
        """Get display name for the instance."""
        return self.tags.name or self.instance_id

    @property
    def is_windows(self) -> bool:
        """Check if instance is Windows-based."""
        return self.platform == Platform.WINDOWS

    @property
    def is_linux(self) -> bool:
        """Check if instance is Linux-based."""
        return self.platform == Platform.LINUX

    @property
    def is_running(self) -> bool:
        """Check if instance is in running state."""
        return self.status == InstanceStatus.RUNNING

    @property
    def is_stopped(self) -> bool:
        """Check if instance is in stopped state."""
        return self.status == InstanceStatus.STOPPED

    @property
    def ssm_online(self) -> bool:
        """Check if SSM agent is online."""
        return self.ssm_info.status == SSMStatus.ONLINE

    @property
    def requires_backup(self) -> bool:
        """Check if instance requires backup before patching."""
        return self.tags.backup_required is True

    def add_validation_error(self, error: str) -> None:
        """Add a validation error."""
        if error not in self.validation_errors:
            self.validation_errors.append(error)

    def clear_validation_errors(self) -> None:
        """Clear all validation errors."""
        self.validation_errors.clear()

    def to_dict(self) -> Dict[str, Any]:
        """Convert instance to dictionary representation."""
        return {
            "instance_id": self.instance_id,
            "landing_zone": self.landing_zone,
            "region": self.region,
            "account_id": self.account_id,
            "status": self.status.value,
            "platform": self.platform.value,
            "display_name": self.display_name,
            "is_managed": self.is_managed,
            "is_patchable": self.is_patchable,
            "ssm_online": self.ssm_online,
            "requires_backup": self.requires_backup,
            "validation_errors": self.validation_errors,
            "last_scan_time": (
                self.last_scan_time.isoformat() if self.last_scan_time else None
            ),
            "metadata": self.metadata,
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "Instance":
        """Create instance from dictionary representation."""
        # Convert enum values
        if "status" in data and isinstance(data["status"], str):
            data["status"] = InstanceStatus(data["status"])
        if "platform" in data and isinstance(data["platform"], str):
            data["platform"] = Platform(data["platform"])

        # Convert datetime strings
        if "last_scan_time" in data and isinstance(data["last_scan_time"], str):
            data["last_scan_time"] = datetime.fromisoformat(data["last_scan_time"])

        return cls(**data)
