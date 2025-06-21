"""Configuration data models."""

from dataclasses import dataclass, field
from typing import Dict, Any, List, Optional
from enum import Enum


class Environment(Enum):
    """Environment types."""
    NONPROD = "nonprod"
    PREPROD = "preprod"
    PROD = "prod"
    DEV = "dev"
    TEST = "test"
    STAGING = "staging"


class LogLevel(Enum):
    """Logging levels."""
    DEBUG = "DEBUG"
    INFO = "INFO"
    WARNING = "WARNING"
    ERROR = "ERROR"
    CRITICAL = "CRITICAL"


@dataclass
class AWSConfig:
    """AWS-specific configuration."""
    region: str = "us-east-1"
    role_name: Optional[str] = None
    profile: Optional[str] = None
    assume_role_arn: Optional[str] = None
    session_duration: int = 3600
    max_retries: int = 3
    timeout: int = 60
    
    # Service-specific settings
    ec2_endpoint: Optional[str] = None
    ssm_endpoint: Optional[str] = None
    sts_endpoint: Optional[str] = None


@dataclass
class ScannerConfig:
    """Scanner phase configuration."""
    enabled: bool = True
    platforms: List[str] = field(default_factory=lambda: ["windows", "linux"])
    include_stopped_instances: bool = True
    ssm_timeout: int = 30
    max_concurrent_scans: int = 50
    retry_attempts: int = 3
    retry_delay: int = 5
    
    # Filtering options
    exclude_terminated: bool = True
    exclude_spot_instances: bool = False
    min_uptime_hours: int = 0
    
    # Output options
    save_to_csv: bool = True
    csv_filename: str = "instance_scan_results.csv"


@dataclass
class AMIBackupConfig:
    """AMI backup phase configuration."""
    enabled: bool = True
    timeout_minutes: int = 60
    max_concurrent_backups: int = 10
    retry_attempts: int = 2
    retry_delay: int = 10
    
    # Backup options
    no_reboot: bool = True
    description_template: str = "Pre-patch backup for {instance_id} - {timestamp}"
    
    # Cleanup options
    cleanup_old_backups: bool = True
    max_backup_age_days: int = 30
    max_backups_per_instance: int = 5
    
    # Tagging
    backup_tags: Dict[str, str] = field(default_factory=lambda: {
        "Purpose": "PrePatchBackup",
        "AutoCleanup": "true"
    })


@dataclass
class ServerManagerConfig:
    """Server management phase configuration."""
    enabled: bool = True
    start_timeout_minutes: int = 10
    stop_timeout_minutes: int = 5
    max_concurrent_operations: int = 20
    retry_attempts: int = 3
    retry_delay: int = 5
    
    # Health check options
    health_check_enabled: bool = True
    health_check_timeout: int = 300
    health_check_interval: int = 30
    
    # Safety options
    require_confirmation: bool = False
    dry_run: bool = False


@dataclass
class ValidationConfig:
    """Validation phase configuration."""
    enabled: bool = True
    timeout_minutes: int = 15
    
    # Validation checks
    check_ssm_connectivity: bool = True
    check_disk_space: bool = True
    check_memory_usage: bool = True
    check_cpu_usage: bool = True
    check_network_connectivity: bool = True
    
    # Thresholds
    min_disk_space_gb: int = 5
    max_memory_usage_percent: int = 90
    max_cpu_usage_percent: int = 80
    
    # Actions on validation failure
    fail_on_validation_error: bool = True
    skip_failed_instances: bool = True


@dataclass
class ReportingConfig:
    """Reporting configuration."""
    enabled: bool = True
    output_directory: str = "reports"
    formats: List[str] = field(default_factory=lambda: ["json", "csv"])
    
    # Report content
    include_summary: bool = True
    include_details: bool = True
    include_errors: bool = True
    include_metrics: bool = True
    
    # File naming
    filename_template: str = "prepatch_report_{timestamp}"
    timestamp_format: str = "%Y%m%d_%H%M%S"


@dataclass
class LoggingConfig:
    """Logging configuration."""
    level: LogLevel = LogLevel.INFO
    format: str = "%(asctime)s - %(name)s - %(levelname)s - %(message)s"
    
    # File logging
    log_to_file: bool = True
    log_file: str = "prepatch_workflow.log"
    max_file_size_mb: int = 100
    backup_count: int = 5
    
    # Console logging
    log_to_console: bool = True
    console_level: LogLevel = LogLevel.INFO
    
    # Structured logging
    structured_logging: bool = False
    log_format: str = "text"  # text, json


@dataclass
class SafetyConfig:
    """Safety and circuit breaker configuration."""
    max_failure_rate: float = 0.2  # 20% failure rate threshold
    max_concurrent_failures: int = 5
    circuit_breaker_timeout: int = 300  # 5 minutes
    
    # Emergency stops
    enable_emergency_stop: bool = True
    max_total_failures: int = 50
    
    # Confirmation requirements
    require_confirmation_for_prod: bool = True
    require_confirmation_threshold: int = 100  # instances


@dataclass
class LandingZoneConfig:
    """Landing zone configuration."""
    name: str
    account_id: str
    region: str
    environment: Environment
    
    # AWS configuration
    aws_config: AWSConfig = field(default_factory=AWSConfig)
    
    # Instance filtering
    include_patterns: List[str] = field(default_factory=list)
    exclude_patterns: List[str] = field(default_factory=list)
    tag_filters: Dict[str, str] = field(default_factory=dict)
    
    # Landing zone specific settings
    max_instances: Optional[int] = None
    priority: int = 1  # 1 = highest priority
    enabled: bool = True
    
    # Override configurations
    scanner_config_override: Optional[Dict[str, Any]] = None
    ami_backup_config_override: Optional[Dict[str, Any]] = None
    server_manager_config_override: Optional[Dict[str, Any]] = None


@dataclass
class WorkflowConfig:
    """Complete workflow configuration."""
    
    # Workflow metadata
    name: str = "Pre-Patch Workflow"
    version: str = "1.0.0"
    description: str = "Automated pre-patch workflow for EC2 instances"
    
    # Landing zones
    landing_zones: List[LandingZoneConfig] = field(default_factory=list)
    
    # Phase configurations
    scanner: ScannerConfig = field(default_factory=ScannerConfig)
    ami_backup: AMIBackupConfig = field(default_factory=AMIBackupConfig)
    server_manager: ServerManagerConfig = field(default_factory=ServerManagerConfig)
    validation: ValidationConfig = field(default_factory=ValidationConfig)
    
    # Global configurations
    aws: AWSConfig = field(default_factory=AWSConfig)
    reporting: ReportingConfig = field(default_factory=ReportingConfig)
    logging: LoggingConfig = field(default_factory=LoggingConfig)
    safety: SafetyConfig = field(default_factory=SafetyConfig)
    
    # Workflow execution options
    parallel_execution: bool = True
    max_parallel_landing_zones: int = 5
    continue_on_error: bool = True
    
    # Environment-specific overrides
    environment_overrides: Dict[str, Dict[str, Any]] = field(default_factory=dict)
    
    def get_landing_zone_config(self, name: str) -> Optional[LandingZoneConfig]:
        """Get landing zone configuration by name."""
        for lz in self.landing_zones:
            if lz.name == name:
                return lz
        return None
    
    def add_landing_zone(self, config: LandingZoneConfig) -> None:
        """Add a landing zone configuration."""
        # Remove existing config with same name
        self.landing_zones = [lz for lz in self.landing_zones if lz.name != config.name]
        self.landing_zones.append(config)
    
    def get_environment_override(self, environment: str, key: str) -> Any:
        """Get environment-specific override value."""
        if environment in self.environment_overrides:
            return self.environment_overrides[environment].get(key)
        return None
    
    def validate(self) -> List[str]:
        """Validate configuration and return list of errors."""
        errors = []
        
        if not self.landing_zones:
            errors.append("At least one landing zone must be configured")
        
        for lz in self.landing_zones:
            if not lz.name:
                errors.append("Landing zone name cannot be empty")
            if not lz.account_id:
                errors.append(f"Account ID required for landing zone {lz.name}")
            if not lz.region:
                errors.append(f"Region required for landing zone {lz.name}")
        
        # Validate phase configurations
        if self.ami_backup.timeout_minutes <= 0:
            errors.append("AMI backup timeout must be positive")
        
        if self.scanner.max_concurrent_scans <= 0:
            errors.append("Scanner max concurrent scans must be positive")
        
        return errors