"""Configuration service implementation."""

import os
import yaml
import logging
from pathlib import Path
from typing import Dict, Any, List, Optional
from dataclasses import asdict

from core.interfaces.config_interface import IConfigService
from core.models.config import (
    WorkflowConfig,
    LandingZoneConfig,
    AWSConfig,
    Environment,
    LogLevel,
    WorkflowPhaseConfig,
)


class ConfigService(IConfigService):
    """Implementation of configuration service."""

    def __init__(self, config_file_path: Optional[str] = None):
        self.logger = logging.getLogger(__name__)
        self._config_file_path = config_file_path
        self._workflow_config: Optional[WorkflowConfig] = None
        self._config_cache: Dict[str, Any] = {}
        self._environment_overrides: Dict[str, Any] = {}

        if config_file_path:
            self._load_workflow_config_sync(config_file_path)
    
    async def load_config(self, config_path: Optional[str] = None) -> None:
        """Load configuration from default or specified path.
        
        Args:
            config_path: Optional path to configuration file. Defaults to 'config/default.yml'
        """
        if config_path is None:
            config_path = "config/default.yml"
        
        await self.load_workflow_config(config_path)

    def _handle_error(self, operation: str, error: Exception) -> None:
        """Centralized error handling and logging."""
        self.logger.error(f"Error {operation}: {str(error)}")
        raise error

    def _create_config(
        self, config_class, data: Dict[str, Any], defaults: Dict[str, Any] = None
    ):
        """Helper method to create configuration objects with defaults."""
        if defaults:
            merged_data = {**defaults, **data}
        else:
            merged_data = data
        return config_class(
            **{
                k: merged_data.get(k, v)
                for k, v in config_class.__annotations__.items()
                if k in merged_data or k in (defaults or {})
            }
        )

    async def load_workflow_config(self, config_path: str) -> WorkflowConfig:
        """Load workflow configuration from file.
        
        Args:
            config_path: Path to the configuration file
            
        Returns:
            WorkflowConfig object
            
        Raises:
            ConfigurationError: If config is invalid or not found
        """
        return self._load_workflow_config_sync(config_path)
    
    def _load_workflow_config_sync(self, config_file_path: str) -> WorkflowConfig:
        """Synchronous implementation of workflow config loading."""
        try:
            config_path = Path(config_file_path)

            if not config_path.exists():
                raise FileNotFoundError(
                    f"Configuration file not found: {config_file_path}"
                )

            with open(config_path, "r", encoding="utf-8") as file:
                raw_config = yaml.safe_load(file)

            if not raw_config:
                raise ValueError("Configuration file is empty or invalid")

            self._apply_environment_overrides(raw_config)
            self._workflow_config = self._parse_workflow_config(raw_config)
            self._config_file_path = config_file_path
            self._config_cache["raw"] = raw_config

            return self._workflow_config

        except Exception as e:
            self._handle_error("loading workflow configuration", e)

    def load_landing_zone_config(
        self, landing_zone_file: str
    ) -> List[LandingZoneConfig]:
        """Load landing zone configurations from file."""
        try:
            config_path = Path(landing_zone_file)

            if not config_path.exists():
                raise FileNotFoundError(
                    f"Landing zone configuration file not found: {landing_zone_file}"
                )

            with open(config_path, "r", encoding="utf-8") as file:
                raw_config = yaml.safe_load(file)

            if not raw_config:
                raise ValueError("Landing zone configuration file is empty or invalid")

            landing_zones = []

            if isinstance(raw_config, dict):
                if "landing_zones" in raw_config:
                    for lz_data in raw_config["landing_zones"]:
                        landing_zones.append(self._parse_landing_zone_config(lz_data))
                else:
                    landing_zones.append(self._parse_landing_zone_config(raw_config))
            elif isinstance(raw_config, list):
                for lz_data in raw_config:
                    landing_zones.append(self._parse_landing_zone_config(lz_data))
            else:
                raise ValueError("Invalid landing zone configuration format")

            return landing_zones

        except Exception as e:
            self._handle_error("loading landing zone configuration", e)

    async def load_landing_zones(self, config_path: Optional[str] = None) -> List[LandingZoneConfig]:
        """Load landing zone configurations.
        
        Args:
            config_path: Optional path to landing zones config
            
        Returns:
            List of LandingZoneConfig objects
        """
        if config_path is None:
            # Default to inventory directory
            config_path = "inventory/nonprod_landing_zones.yml"
        
        return self.load_landing_zone_config(config_path)

    async def validate_config(self, config: Dict[str, Any]) -> bool:
        """Validate configuration against schema.
        
        Args:
            config: Configuration dictionary to validate
            
        Returns:
            True if valid, raises exception if invalid
            
        Raises:
            ValidationError: If configuration is invalid
        """
        errors = self._validate_config_sync()
        if errors:
            raise ValueError(f"Configuration validation failed: {'; '.join(errors)}")
        return True
    
    def _validate_config_sync(self) -> List[str]:
        """Synchronous implementation of config validation."""
        errors = []

        if not self._workflow_config:
            errors.append("No workflow configuration loaded")
            return errors

        try:
            workflow_errors = self._workflow_config.validate()
            errors.extend(workflow_errors)

            if self._workflow_config.aws:
                aws_errors = self._validate_aws_config(self._workflow_config.aws)
                errors.extend(aws_errors)

            if self._workflow_config.landing_zones:
                for i, lz in enumerate(self._workflow_config.landing_zones):
                    lz_errors = self._validate_landing_zone_config(
                        lz, f"landing_zone[{i}]"
                    )
                    errors.extend(lz_errors)

            phase_errors = self._validate_phase_configs()
            errors.extend(phase_errors)

        except Exception as e:
            errors.append(f"Configuration validation error: {str(e)}")

        return errors

    def get_setting(self, key: str, default: Any = None) -> Any:
        """Get a configuration setting by key path (e.g., 'aws.region')."""
        if not self._workflow_config:
            return default

        try:
            # Convert workflow config to dict for easy access
            config_dict = asdict(self._workflow_config)

            # Navigate through nested keys
            keys = key.split(".")
            value = config_dict

            for k in keys:
                if isinstance(value, dict) and k in value:
                    value = value[k]
                else:
                    return default

            return value

        except Exception:
            return default

    def get_aws_config(self) -> Optional[AWSConfig]:
        """Get AWS configuration."""
        return self._workflow_config.aws if self._workflow_config else None

    def get_environment_config(self, environment: Environment) -> Dict[str, Any]:
        """Get environment-specific configuration."""
        if not self._workflow_config or not self._workflow_config.environments:
            return {}

        return self._workflow_config.environments.get(environment.value, {})

    def get_phase_config(self, phase_name: str) -> Dict[str, Any]:
        """Get configuration for a specific workflow phase."""
        if not self._workflow_config:
            return {}

        # Map phase names to configuration objects
        phase_configs = {
            "scanner": (
                asdict(self._workflow_config.scanner)
                if self._workflow_config.scanner
                else {}
            ),
            "ami_backup": (
                asdict(self._workflow_config.ami_backup)
                if self._workflow_config.ami_backup
                else {}
            ),
            "server_manager": (
                asdict(self._workflow_config.server_manager)
                if self._workflow_config.server_manager
                else {}
            ),
            # Note: validation, reporting, logging, and safety configs
            # are not part of the current WorkflowConfig model
        }

        return phase_configs.get(phase_name, {})

    def get_landing_zones(self) -> List[str]:
        """Get all landing zone names."""
        return self._workflow_config.landing_zones if self._workflow_config else []

    def get_workflow_config(self) -> Optional[WorkflowConfig]:
        """Get the complete workflow configuration."""
        return self._workflow_config

    def set_environment_override(self, key: str, value: Any) -> None:
        """Set an environment override for configuration."""
        self._environment_overrides[key] = value

    async def reload_config(self) -> None:
        """Reload configuration from source."""
        if not self._config_file_path:
            raise ValueError("No configuration file path available for reload")

        self._config_cache.clear()
        await self.load_workflow_config(self._config_file_path)

    def _parse_workflow_config(self, raw_config: Dict[str, Any]) -> WorkflowConfig:
        """Parse raw configuration into WorkflowConfig object."""
        try:
            workflow_data = raw_config.get("workflow", {})
            aws_data = raw_config.get("aws", {})
            landing_zones_data = raw_config.get("landing_zones", [])
            environments_data = raw_config.get("environments", {})

            aws_config = None
            if aws_data:
                aws_config = AWSConfig(
                    role_name=aws_data.get("role_name", "HIPCMSProvisionSpokeRole"),
                    region=aws_data.get("region", "ap-southeast-2"),
                    timeout=aws_data.get("timeout", 60),
                    max_retries=aws_data.get("max_retries", 3),
                )

            # Handle landing zones as simple list of strings
            landing_zones = landing_zones_data if isinstance(landing_zones_data, list) else []

            return WorkflowConfig(
                name=raw_config.get("name", "Pre-Patch Workflow"),
                landing_zones=landing_zones,
                aws=aws_config or AWSConfig(),
                scanner=self._parse_phase_config(raw_config.get("scanner", {})),
                ami_backup=self._parse_phase_config(raw_config.get("ami_backup", {}), default_timeout=60),
                server_manager=self._parse_phase_config(raw_config.get("server_manager", {}), default_timeout=10),
                output_dir=raw_config.get("output_dir", "reports"),
                log_level=self._parse_log_level(raw_config.get("log_level", "INFO")),
                skip_backup=raw_config.get("skip_backup", False),
                skip_validation=raw_config.get("skip_validation", False),
                continue_on_error=raw_config.get("continue_on_error", True),
            )

        except Exception as e:
            raise ValueError(f"Error parsing workflow configuration: {str(e)}")
    
    def _parse_phase_config(self, phase_data: Dict[str, Any], default_timeout: int = 30) -> WorkflowPhaseConfig:
        """Parse phase configuration into WorkflowPhaseConfig object."""
        return WorkflowPhaseConfig(
            enabled=phase_data.get("enabled", True),
            timeout_minutes=phase_data.get("timeout_minutes", default_timeout),
            max_concurrent=phase_data.get("max_concurrent", 10),
            retry_attempts=phase_data.get("retry_attempts", 2),
        )
    
    def _parse_log_level(self, log_level_str: str) -> LogLevel:
        """Parse log level string into LogLevel enum."""
        try:
            return LogLevel[log_level_str.upper()]
        except (KeyError, AttributeError):
            return LogLevel.INFO

    def _parse_landing_zone_config(self, lz_data: Dict[str, Any]) -> LandingZoneConfig:
        """Parse landing zone configuration."""
        # Convert environment string to Environment enum if needed
        env_str = lz_data.get("environment", "nonprod")
        if isinstance(env_str, str):
            environment = Environment.NONPROD if env_str.lower() in ["nonprod", "non-prod"] else Environment.PROD
        else:
            environment = env_str
            
        return LandingZoneConfig(
            name=lz_data.get("name", ""),
            account_id=lz_data.get("account_id", ""),
            environment=environment,
            enabled=lz_data.get("enabled", True),
        )

    def _parse_scanner_config(self, scanner_data: Dict[str, Any]) -> Dict[str, Any]:
        """Parse scanner configuration."""
        return {
            "enabled": scanner_data.get("enabled", True),
            "platforms": scanner_data.get("platforms", ["linux", "windows"]),
            "include_stopped_instances": scanner_data.get(
                "include_stopped_instances", False
            ),
            "require_ssm_agent": scanner_data.get("require_ssm_agent", True),
            "instance_filters": scanner_data.get("instance_filters", {}),
            "tag_filters": scanner_data.get("tag_filters", {}),
            "exclude_patterns": scanner_data.get("exclude_patterns", []),
            "timeout_seconds": scanner_data.get("timeout_seconds", 300),
            "max_concurrent_scans": scanner_data.get("max_concurrent_scans", 5),
            "retry_attempts": scanner_data.get("retry_attempts", 3),
            "cache_duration_minutes": scanner_data.get("cache_duration_minutes", 15),
        }

    def _parse_ami_backup_config(self, backup_data: Dict[str, Any]) -> Dict[str, Any]:
        """Parse AMI backup configuration."""
        return {
            "enabled": backup_data.get("enabled", True),
            "no_reboot": backup_data.get("no_reboot", True),
            "include_all_volumes": backup_data.get("include_all_volumes", True),
            "copy_tags": backup_data.get("copy_tags", True),
            "description_template": backup_data.get(
                "description_template",
                "Pre-patch backup for {instance_id} - {timestamp}",
            ),
            "retention_days": backup_data.get("retention_days", 30),
            "max_backups_per_instance": backup_data.get("max_backups_per_instance", 5),
            "backup_tags": backup_data.get("backup_tags", {}),
            "timeout_minutes": backup_data.get("timeout_minutes", 60),
            "max_concurrent_backups": backup_data.get("max_concurrent_backups", 10),
            "retry_attempts": backup_data.get("retry_attempts", 2),
            "retry_delay_minutes": backup_data.get("retry_delay_minutes", 5),
            "cleanup_old_backups": backup_data.get("cleanup_old_backups", True),
        }

    def _parse_server_manager_config(
        self, server_data: Dict[str, Any]
    ) -> Dict[str, Any]:
        """Parse server manager configuration."""
        return {
            "enabled": server_data.get("enabled", True),
            "start_timeout_minutes": server_data.get("start_timeout_minutes", 10),
            "stop_timeout_minutes": server_data.get("stop_timeout_minutes", 10),
            "restart_timeout_minutes": server_data.get("restart_timeout_minutes", 15),
            "health_check_timeout_seconds": server_data.get(
                "health_check_timeout_seconds", 300
            ),
            "max_concurrent_operations": server_data.get("max_concurrent_operations", 10),
            "wait_between_operations_seconds": server_data.get(
                "wait_between_operations_seconds", 5
            ),
            "force_stop_after_timeout": server_data.get("force_stop_after_timeout", False),
            "validate_health_after_start": server_data.get(
                "validate_health_after_start", True
            ),
            "retry_failed_operations": server_data.get("retry_failed_operations", True),
            "max_retry_attempts": server_data.get("max_retry_attempts", 3),
        }

    def _parse_validation_config(
        self, validation_data: Dict[str, Any]
    ) -> Dict[str, Any]:
        """Parse validation configuration."""
        return {
            "enabled": validation_data.get("enabled", True),
            "check_instance_status": validation_data.get("check_instance_status", True),
            "check_ssm_connectivity": validation_data.get("check_ssm_connectivity", True),
            "check_system_health": validation_data.get("check_system_health", True),
            "custom_health_checks": validation_data.get("custom_health_checks", []),
            "timeout_seconds": validation_data.get("timeout_seconds", 300),
            "retry_attempts": validation_data.get("retry_attempts", 3),
            "fail_on_validation_error": validation_data.get(
                "fail_on_validation_error", False
            ),
            "health_check_interval_seconds": validation_data.get(
                "health_check_interval_seconds", 30
            ),
        }

    def _parse_reporting_config(
        self, reporting_data: Dict[str, Any]
    ) -> Dict[str, Any]:
        """Parse reporting configuration."""
        return {
            "enabled": reporting_data.get("enabled", True),
            "output_directory": reporting_data.get("output_directory", "./reports"),
            "formats": reporting_data.get("formats", ["json", "csv"]),
            "include_detailed_logs": reporting_data.get("include_detailed_logs", True),
            "include_instance_details": reporting_data.get(
                "include_instance_details", True
            ),
            "include_operation_metrics": reporting_data.get(
                "include_operation_metrics", True
            ),
            "compress_reports": reporting_data.get("compress_reports", False),
            "retention_days": reporting_data.get("retention_days", 90),
            "email_notifications": reporting_data.get("email_notifications", {}),
            "webhook_notifications": reporting_data.get("webhook_notifications", {}),
        }

    def _parse_logging_config(self, logging_data: Dict[str, Any]) -> Dict[str, Any]:
        """Parse logging configuration."""
        return {
            "level": logging_data.get("level", "INFO"),
            "format": logging_data.get(
                "format", "%(asctime)s - %(name)s - %(levelname)s - %(message)s"
            ),
            "file_path": logging_data.get("file_path"),
            "max_file_size_mb": logging_data.get("max_file_size_mb", 100),
            "backup_count": logging_data.get("backup_count", 5),
            "console_output": logging_data.get("console_output", True),
            "structured_logging": logging_data.get("structured_logging", False),
            "log_aws_api_calls": logging_data.get("log_aws_api_calls", False),
            "sensitive_data_masking": logging_data.get("sensitive_data_masking", True),
        }

    def _parse_safety_config(self, safety_data: Dict[str, Any]) -> Dict[str, Any]:
        """Parse safety configuration."""
        return {
            "enabled": safety_data.get("enabled", True),
            "max_instances_per_batch": safety_data.get("max_instances_per_batch", 50),
            "require_confirmation": safety_data.get("require_confirmation", False),
            "dry_run_mode": safety_data.get("dry_run_mode", False),
            "stop_on_first_failure": safety_data.get("stop_on_first_failure", False),
            "max_failure_percentage": safety_data.get("max_failure_percentage", 20),
            "protected_tags": safety_data.get("protected_tags", {}),
            "excluded_instance_ids": safety_data.get("excluded_instance_ids", []),
            "business_hours_only": safety_data.get("business_hours_only", False),
            "maintenance_window": safety_data.get("maintenance_window", {}),
        }

    def _apply_environment_overrides(self, config: Dict[str, Any]) -> None:
        """Apply environment variable overrides to configuration."""
        for key, value in self._environment_overrides.items():
            self._set_nested_value(config, key, value)

        env_mappings = {
            "PATCHING_AWS_REGION": "aws.region",
            "PATCHING_AWS_ROLE": "aws.role_name",
            "PATCHING_LOG_LEVEL": "logging.level",
            "PATCHING_DRY_RUN": "safety.dry_run_mode",
            "PATCHING_MAX_CONCURRENT": "workflow.max_concurrent_instances",
        }

        for env_var, config_key in env_mappings.items():
            env_value = os.getenv(env_var)
            if env_value is not None:
                if env_value.lower() in ["true", "false"]:
                    env_value = env_value.lower() == "true"
                elif env_value.isdigit():
                    env_value = int(env_value)

                self._set_nested_value(config, config_key, env_value)

    def _set_nested_value(
        self, config: Dict[str, Any], key_path: str, value: Any
    ) -> None:
        """Set a nested value in configuration dictionary."""
        keys = key_path.split(".")
        current = config

        for key in keys[:-1]:
            if key not in current:
                current[key] = {}
            current = current[key]

        current[keys[-1]] = value

    def _validate_aws_config(self, aws_config: AWSConfig) -> List[str]:
        """Validate AWS configuration."""
        errors = []

        if not aws_config.region:
            errors.append("AWS region is required")

        if aws_config.session_duration and (
            aws_config.session_duration < 900 or aws_config.session_duration > 43200
        ):
            errors.append("AWS session duration must be between 900 and 43200 seconds")

        return errors

    def _validate_landing_zone_config(
        self, lz_config: LandingZoneConfig, prefix: str
    ) -> List[str]:
        """Validate landing zone configuration."""
        errors = []

        if not lz_config.name:
            errors.append(f"{prefix}: Landing zone name is required")

        if not lz_config.account_id:
            errors.append(f"{prefix}: Account ID is required")

        if not lz_config.regions:
            errors.append(f"{prefix}: At least one region is required")

        if lz_config.priority < 1:
            errors.append(f"{prefix}: Priority must be >= 1")

        return errors

    def _validate_phase_configs(self) -> List[str]:
        """Validate phase configurations."""
        errors = []

        # Validate that required phases are configured
        required_phases = ["scanner", "ami_backup", "server_manager"]

        for phase in required_phases:
            phase_config = getattr(self._workflow_config, phase, None)
            if not phase_config or not phase_config.enabled:
                errors.append(f"Required phase '{phase}' is not enabled")

        return errors
