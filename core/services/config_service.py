"""Configuration service implementation."""

import os
import yaml
import logging
from pathlib import Path
from typing import Dict, Any, List, Optional, Union
from dataclasses import asdict

from core.interfaces.config_interface import IConfigService
from core.models.config import (
    WorkflowConfig, LandingZoneConfig, AWSConfig, Environment,
    ScannerConfig, AMIBackupConfig, ServerManagerConfig,
    ValidationConfig, ReportingConfig, LoggingConfig, SafetyConfig
)


class ConfigService(IConfigService):
    """Implementation of configuration service."""
    
    def __init__(self, config_file_path: Optional[str] = None):
        self.logger = logging.getLogger(__name__)
        self._config_file_path = config_file_path
        self._workflow_config: Optional[WorkflowConfig] = None
        self._config_cache: Dict[str, Any] = {}
        self._environment_overrides: Dict[str, Any] = {}
        
        # Load configuration if path provided
        if config_file_path:
            self.load_workflow_config(config_file_path)
    
    def load_workflow_config(self, config_file_path: str) -> WorkflowConfig:
        """Load workflow configuration from file."""
        self.logger.info(f"Loading workflow configuration from {config_file_path}")
        
        try:
            config_path = Path(config_file_path)
            
            if not config_path.exists():
                raise FileNotFoundError(f"Configuration file not found: {config_file_path}")
            
            # Load YAML configuration
            with open(config_path, 'r', encoding='utf-8') as file:
                raw_config = yaml.safe_load(file)
            
            if not raw_config:
                raise ValueError("Configuration file is empty or invalid")
            
            # Apply environment overrides
            self._apply_environment_overrides(raw_config)
            
            # Parse and validate configuration
            self._workflow_config = self._parse_workflow_config(raw_config)
            self._config_file_path = config_file_path
            
            # Cache the raw config
            self._config_cache['raw'] = raw_config
            
            self.logger.info("Workflow configuration loaded successfully")
            return self._workflow_config
            
        except Exception as e:
            self.logger.error(f"Error loading workflow configuration: {str(e)}")
            raise
    
    def load_landing_zone_config(self, landing_zone_file: str) -> List[LandingZoneConfig]:
        """Load landing zone configurations from file."""
        self.logger.info(f"Loading landing zone configuration from {landing_zone_file}")
        
        try:
            config_path = Path(landing_zone_file)
            
            if not config_path.exists():
                raise FileNotFoundError(f"Landing zone configuration file not found: {landing_zone_file}")
            
            # Load YAML configuration
            with open(config_path, 'r', encoding='utf-8') as file:
                raw_config = yaml.safe_load(file)
            
            if not raw_config:
                raise ValueError("Landing zone configuration file is empty or invalid")
            
            # Parse landing zones
            landing_zones = []
            
            if isinstance(raw_config, dict):
                # Single landing zone or structured format
                if 'landing_zones' in raw_config:
                    # Structured format with landing_zones key
                    for lz_data in raw_config['landing_zones']:
                        landing_zones.append(self._parse_landing_zone_config(lz_data))
                else:
                    # Single landing zone format
                    landing_zones.append(self._parse_landing_zone_config(raw_config))
            elif isinstance(raw_config, list):
                # List of landing zones
                for lz_data in raw_config:
                    landing_zones.append(self._parse_landing_zone_config(lz_data))
            else:
                raise ValueError("Invalid landing zone configuration format")
            
            self.logger.info(f"Loaded {len(landing_zones)} landing zone configurations")
            return landing_zones
            
        except Exception as e:
            self.logger.error(f"Error loading landing zone configuration: {str(e)}")
            raise
    
    def validate_config(self) -> List[str]:
        """Validate the current configuration and return any errors."""
        errors = []
        
        if not self._workflow_config:
            errors.append("No workflow configuration loaded")
            return errors
        
        try:
            # Validate workflow configuration
            workflow_errors = self._workflow_config.validate()
            errors.extend(workflow_errors)
            
            # Validate AWS configuration
            if self._workflow_config.aws:
                aws_errors = self._validate_aws_config(self._workflow_config.aws)
                errors.extend(aws_errors)
            
            # Validate landing zones
            if self._workflow_config.landing_zones:
                for i, lz in enumerate(self._workflow_config.landing_zones):
                    lz_errors = self._validate_landing_zone_config(lz, f"landing_zone[{i}]")
                    errors.extend(lz_errors)
            
            # Validate phase configurations
            phase_errors = self._validate_phase_configs()
            errors.extend(phase_errors)
            
        except Exception as e:
            errors.append(f"Configuration validation error: {str(e)}")
        
        if errors:
            self.logger.warning(f"Configuration validation found {len(errors)} errors")
            for error in errors:
                self.logger.warning(f"  - {error}")
        else:
            self.logger.info("Configuration validation passed")
        
        return errors
    
    def get_setting(self, key: str, default: Any = None) -> Any:
        """Get a configuration setting by key path (e.g., 'aws.region')."""
        if not self._workflow_config:
            return default
        
        try:
            # Convert workflow config to dict for easy access
            config_dict = asdict(self._workflow_config)
            
            # Navigate through nested keys
            keys = key.split('.')
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
            'scanner': asdict(self._workflow_config.scanner) if self._workflow_config.scanner else {},
            'ami_backup': asdict(self._workflow_config.ami_backup) if self._workflow_config.ami_backup else {},
            'server_manager': asdict(self._workflow_config.server_manager) if self._workflow_config.server_manager else {},
            'validation': asdict(self._workflow_config.validation) if self._workflow_config.validation else {},
            'reporting': asdict(self._workflow_config.reporting) if self._workflow_config.reporting else {},
            'logging': asdict(self._workflow_config.logging) if self._workflow_config.logging else {},
            'safety': asdict(self._workflow_config.safety) if self._workflow_config.safety else {}
        }
        
        return phase_configs.get(phase_name, {})
    
    def get_landing_zones(self) -> List[LandingZoneConfig]:
        """Get all landing zone configurations."""
        return self._workflow_config.landing_zones if self._workflow_config else []
    
    def get_workflow_config(self) -> Optional[WorkflowConfig]:
        """Get the complete workflow configuration."""
        return self._workflow_config
    
    def set_environment_override(self, key: str, value: Any) -> None:
        """Set an environment override for configuration."""
        self._environment_overrides[key] = value
        self.logger.debug(f"Set environment override: {key} = {value}")
    
    def reload_config(self) -> WorkflowConfig:
        """Reload configuration from the original file."""
        if not self._config_file_path:
            raise ValueError("No configuration file path available for reload")
        
        self.logger.info("Reloading configuration")
        self._config_cache.clear()
        return self.load_workflow_config(self._config_file_path)
    
    def _parse_workflow_config(self, raw_config: Dict[str, Any]) -> WorkflowConfig:
        """Parse raw configuration into WorkflowConfig object."""
        try:
            # Extract main sections
            workflow_data = raw_config.get('workflow', {})
            aws_data = raw_config.get('aws', {})
            landing_zones_data = raw_config.get('landing_zones', [])
            environments_data = raw_config.get('environments', {})
            
            # Parse AWS configuration
            aws_config = None
            if aws_data:
                aws_config = AWSConfig(
                    role_name=aws_data.get('role_name'),
                    region=aws_data.get('region', 'us-east-1'),
                    profile=aws_data.get('profile'),
                    session_duration=aws_data.get('session_duration', 3600),
                    retry_config=aws_data.get('retry_config', {})
                )
            
            # Parse landing zones
            landing_zones = []
            for lz_data in landing_zones_data:
                landing_zones.append(self._parse_landing_zone_config(lz_data))
            
            # Parse phase configurations
            scanner_config = self._parse_scanner_config(raw_config.get('scanner', {}))
            ami_backup_config = self._parse_ami_backup_config(raw_config.get('ami_backup', {}))
            server_manager_config = self._parse_server_manager_config(raw_config.get('server_manager', {}))
            validation_config = self._parse_validation_config(raw_config.get('validation', {}))
            reporting_config = self._parse_reporting_config(raw_config.get('reporting', {}))
            logging_config = self._parse_logging_config(raw_config.get('logging', {}))
            safety_config = self._parse_safety_config(raw_config.get('safety', {}))
            
            # Create workflow configuration
            workflow_config = WorkflowConfig(
                name=workflow_data.get('name', 'Pre-Patch Workflow'),
                description=workflow_data.get('description', ''),
                version=workflow_data.get('version', '1.0.0'),
                platforms=workflow_data.get('platforms', ['linux', 'windows']),
                phases=workflow_data.get('phases', ['scanner', 'ami_backup', 'start_servers', 'validation']),
                parallel_execution=workflow_data.get('parallel_execution', True),
                max_concurrent_instances=workflow_data.get('max_concurrent_instances', 10),
                timeout_minutes=workflow_data.get('timeout_minutes', 120),
                aws=aws_config,
                landing_zones=landing_zones,
                scanner=scanner_config,
                ami_backup=ami_backup_config,
                server_manager=server_manager_config,
                validation=validation_config,
                reporting=reporting_config,
                logging=logging_config,
                safety=safety_config,
                environments=environments_data
            )
            
            return workflow_config
            
        except Exception as e:
            raise ValueError(f"Error parsing workflow configuration: {str(e)}")
    
    def _parse_landing_zone_config(self, lz_data: Dict[str, Any]) -> LandingZoneConfig:
        """Parse landing zone configuration."""
        return LandingZoneConfig(
            name=lz_data.get('name', ''),
            account_id=lz_data.get('account_id', ''),
            regions=lz_data.get('regions', []),
            role_name=lz_data.get('role_name'),
            filters=lz_data.get('filters', {}),
            tags=lz_data.get('tags', {}),
            enabled=lz_data.get('enabled', True),
            priority=lz_data.get('priority', 1),
            timeout_minutes=lz_data.get('timeout_minutes', 60),
            retry_attempts=lz_data.get('retry_attempts', 3)
        )
    
    def _parse_scanner_config(self, scanner_data: Dict[str, Any]) -> ScannerConfig:
        """Parse scanner configuration."""
        return ScannerConfig(
            enabled=scanner_data.get('enabled', True),
            platforms=scanner_data.get('platforms', ['linux', 'windows']),
            include_stopped_instances=scanner_data.get('include_stopped_instances', False),
            require_ssm_agent=scanner_data.get('require_ssm_agent', True),
            instance_filters=scanner_data.get('instance_filters', {}),
            tag_filters=scanner_data.get('tag_filters', {}),
            exclude_patterns=scanner_data.get('exclude_patterns', []),
            timeout_seconds=scanner_data.get('timeout_seconds', 300),
            max_concurrent_scans=scanner_data.get('max_concurrent_scans', 5),
            retry_attempts=scanner_data.get('retry_attempts', 3),
            cache_duration_minutes=scanner_data.get('cache_duration_minutes', 15)
        )
    
    def _parse_ami_backup_config(self, backup_data: Dict[str, Any]) -> AMIBackupConfig:
        """Parse AMI backup configuration."""
        return AMIBackupConfig(
            enabled=backup_data.get('enabled', True),
            no_reboot=backup_data.get('no_reboot', True),
            include_all_volumes=backup_data.get('include_all_volumes', True),
            copy_tags=backup_data.get('copy_tags', True),
            description_template=backup_data.get('description_template', 
                                               'Pre-patch backup for {instance_id} - {timestamp}'),
            retention_days=backup_data.get('retention_days', 30),
            max_backups_per_instance=backup_data.get('max_backups_per_instance', 5),
            backup_tags=backup_data.get('backup_tags', {}),
            timeout_minutes=backup_data.get('timeout_minutes', 60),
            max_concurrent_backups=backup_data.get('max_concurrent_backups', 10),
            retry_attempts=backup_data.get('retry_attempts', 2),
            retry_delay_minutes=backup_data.get('retry_delay_minutes', 5),
            cleanup_old_backups=backup_data.get('cleanup_old_backups', True)
        )
    
    def _parse_server_manager_config(self, server_data: Dict[str, Any]) -> ServerManagerConfig:
        """Parse server manager configuration."""
        return ServerManagerConfig(
            enabled=server_data.get('enabled', True),
            start_timeout_minutes=server_data.get('start_timeout_minutes', 10),
            stop_timeout_minutes=server_data.get('stop_timeout_minutes', 10),
            restart_timeout_minutes=server_data.get('restart_timeout_minutes', 15),
            health_check_timeout_seconds=server_data.get('health_check_timeout_seconds', 300),
            max_concurrent_operations=server_data.get('max_concurrent_operations', 10),
            wait_between_operations_seconds=server_data.get('wait_between_operations_seconds', 5),
            force_stop_after_timeout=server_data.get('force_stop_after_timeout', False),
            validate_health_after_start=server_data.get('validate_health_after_start', True),
            retry_failed_operations=server_data.get('retry_failed_operations', True),
            max_retry_attempts=server_data.get('max_retry_attempts', 3)
        )
    
    def _parse_validation_config(self, validation_data: Dict[str, Any]) -> ValidationConfig:
        """Parse validation configuration."""
        return ValidationConfig(
            enabled=validation_data.get('enabled', True),
            check_instance_status=validation_data.get('check_instance_status', True),
            check_ssm_connectivity=validation_data.get('check_ssm_connectivity', True),
            check_system_health=validation_data.get('check_system_health', True),
            custom_health_checks=validation_data.get('custom_health_checks', []),
            timeout_seconds=validation_data.get('timeout_seconds', 300),
            retry_attempts=validation_data.get('retry_attempts', 3),
            fail_on_validation_error=validation_data.get('fail_on_validation_error', False),
            health_check_interval_seconds=validation_data.get('health_check_interval_seconds', 30)
        )
    
    def _parse_reporting_config(self, reporting_data: Dict[str, Any]) -> ReportingConfig:
        """Parse reporting configuration."""
        return ReportingConfig(
            enabled=reporting_data.get('enabled', True),
            output_directory=reporting_data.get('output_directory', './reports'),
            formats=reporting_data.get('formats', ['json', 'csv']),
            include_detailed_logs=reporting_data.get('include_detailed_logs', True),
            include_instance_details=reporting_data.get('include_instance_details', True),
            include_operation_metrics=reporting_data.get('include_operation_metrics', True),
            compress_reports=reporting_data.get('compress_reports', False),
            retention_days=reporting_data.get('retention_days', 90),
            email_notifications=reporting_data.get('email_notifications', {}),
            webhook_notifications=reporting_data.get('webhook_notifications', {})
        )
    
    def _parse_logging_config(self, logging_data: Dict[str, Any]) -> LoggingConfig:
        """Parse logging configuration."""
        return LoggingConfig(
            level=logging_data.get('level', 'INFO'),
            format=logging_data.get('format', '%(asctime)s - %(name)s - %(levelname)s - %(message)s'),
            file_path=logging_data.get('file_path'),
            max_file_size_mb=logging_data.get('max_file_size_mb', 100),
            backup_count=logging_data.get('backup_count', 5),
            console_output=logging_data.get('console_output', True),
            structured_logging=logging_data.get('structured_logging', False),
            log_aws_api_calls=logging_data.get('log_aws_api_calls', False),
            sensitive_data_masking=logging_data.get('sensitive_data_masking', True)
        )
    
    def _parse_safety_config(self, safety_data: Dict[str, Any]) -> SafetyConfig:
        """Parse safety configuration."""
        return SafetyConfig(
            enabled=safety_data.get('enabled', True),
            max_instances_per_batch=safety_data.get('max_instances_per_batch', 50),
            require_confirmation=safety_data.get('require_confirmation', False),
            dry_run_mode=safety_data.get('dry_run_mode', False),
            stop_on_first_failure=safety_data.get('stop_on_first_failure', False),
            max_failure_percentage=safety_data.get('max_failure_percentage', 20),
            protected_tags=safety_data.get('protected_tags', {}),
            excluded_instance_ids=safety_data.get('excluded_instance_ids', []),
            business_hours_only=safety_data.get('business_hours_only', False),
            maintenance_window=safety_data.get('maintenance_window', {})
        )
    
    def _apply_environment_overrides(self, config: Dict[str, Any]) -> None:
        """Apply environment variable overrides to configuration."""
        # Apply any environment overrides
        for key, value in self._environment_overrides.items():
            self._set_nested_value(config, key, value)
        
        # Apply environment variables
        env_mappings = {
            'PATCHING_AWS_REGION': 'aws.region',
            'PATCHING_AWS_ROLE': 'aws.role_name',
            'PATCHING_LOG_LEVEL': 'logging.level',
            'PATCHING_DRY_RUN': 'safety.dry_run_mode',
            'PATCHING_MAX_CONCURRENT': 'workflow.max_concurrent_instances'
        }
        
        for env_var, config_key in env_mappings.items():
            env_value = os.getenv(env_var)
            if env_value is not None:
                # Convert string values to appropriate types
                if env_value.lower() in ['true', 'false']:
                    env_value = env_value.lower() == 'true'
                elif env_value.isdigit():
                    env_value = int(env_value)
                
                self._set_nested_value(config, config_key, env_value)
                self.logger.debug(f"Applied environment override: {config_key} = {env_value}")
    
    def _set_nested_value(self, config: Dict[str, Any], key_path: str, value: Any) -> None:
        """Set a nested value in configuration dictionary."""
        keys = key_path.split('.')
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
        
        if aws_config.session_duration and (aws_config.session_duration < 900 or aws_config.session_duration > 43200):
            errors.append("AWS session duration must be between 900 and 43200 seconds")
        
        return errors
    
    def _validate_landing_zone_config(self, lz_config: LandingZoneConfig, prefix: str) -> List[str]:
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
        required_phases = ['scanner', 'ami_backup', 'server_manager']
        
        for phase in required_phases:
            phase_config = getattr(self._workflow_config, phase, None)
            if not phase_config or not phase_config.enabled:
                errors.append(f"Required phase '{phase}' is not enabled")
        
        return errors