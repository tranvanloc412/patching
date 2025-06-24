from dataclasses import dataclass, field
from typing import Dict, Any, List, Optional
from enum import Enum
from dataclasses import dataclass, field


class Environment(Enum):
    """Environment types."""
    NONPROD = "nonprod"
    PROD = "prod"


class LogLevel(Enum):
    """Logging levels."""
    DEBUG = "DEBUG"
    INFO = "INFO"
    WARNING = "WARNING"
    ERROR = "ERROR"


@dataclass
class AWSConfig:
    """AWS configuration."""
    region: str = "ap-southeast-2"
    role_name: str = "HIPCMSProvisionSpokeRole"
    timeout: int = 60
    max_retries: int = 3


@dataclass
class WorkflowPhaseConfig:
    """Simplified phase configuration."""
    enabled: bool = True
    timeout_minutes: int = 30
    max_concurrent: int = 10
    retry_attempts: int = 2


@dataclass
class LandingZoneConfig:
    """Landing zone configuration."""
    name: str
    account_id: str
    environment: Environment
    enabled: bool = True
    tag_filters: Dict[str, str] = field(default_factory=dict)
    region: str = "ap-southeast-2"  # Default region
    include_patterns: List[str] = field(default_factory=list)
    exclude_patterns: List[str] = field(default_factory=list)


@dataclass
class WorkflowConfig:
    """Simplified workflow configuration."""
    
    # Basic settings
    name: str = "Pre-Patch Workflow"
    
    # Landing zones
    landing_zones: List[str] = field(default_factory=list)
    
    # AWS settings
    aws: AWSConfig = field(default_factory=AWSConfig)
    
    # Phase settings
    scanner: WorkflowPhaseConfig = field(default_factory=WorkflowPhaseConfig)
    ami_backup: WorkflowPhaseConfig = field(default_factory=lambda: WorkflowPhaseConfig(timeout_minutes=60))
    server_manager: WorkflowPhaseConfig = field(default_factory=lambda: WorkflowPhaseConfig(timeout_minutes=10))
    
    # Output settings
    output_dir: str = "reports"
    log_level: LogLevel = LogLevel.INFO
    
    # Execution options
    skip_backup: bool = False
    skip_validation: bool = False
    continue_on_error: bool = True
    
    def validate(self) -> List[str]:
        """Validate configuration and return list of errors."""
        errors = []
        
        if not self.landing_zones:
            errors.append("At least one landing zone must be configured")
        
        if self.ami_backup.timeout_minutes <= 0:
            errors.append("AMI backup timeout must be positive")
        
        return errors