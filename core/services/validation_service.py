"""Validation service for comprehensive system and configuration validation."""

import logging
import asyncio
from datetime import datetime
from typing import List, Dict, Any, Optional, Tuple
from pathlib import Path

from core.models.instance import Instance, InstanceStatus, SSMStatus
from core.models.config import WorkflowConfig, LandingZoneConfig
from core.interfaces.config_interface import IConfigService
from core.interfaces.server_manager_interface import IServerManagerService
from infrastructure.aws.ec2_client import EC2Client
from infrastructure.aws.ssm_client import SSMClient


class ValidationService:
    """Service for validating configurations, instances, and system health."""
    
    def __init__(
        self,
        config_service: IConfigService,
        server_manager_service: IServerManagerService
    ):
        self.config_service = config_service
        self.server_manager_service = server_manager_service
        self.logger = logging.getLogger(__name__)
    
    async def validate_workflow_config(self, config_file: str) -> Dict[str, Any]:
        """Validate workflow configuration file."""
        self.logger.info(f"Validating workflow configuration: {config_file}")
        
        validation_result = {
            'valid': True,
            'errors': [],
            'warnings': [],
            'config_file': config_file,
            'validation_time': datetime.utcnow().isoformat()
        }
        
        try:
            # Check if config file exists
            if not Path(config_file).exists():
                validation_result['valid'] = False
                validation_result['errors'].append(f"Configuration file not found: {config_file}")
                return validation_result
            
            # Load configuration
            try:
                workflow_config = self.config_service.load_workflow_config(config_file)
            except Exception as e:
                validation_result['valid'] = False
                validation_result['errors'].append(f"Failed to load configuration: {str(e)}")
                return validation_result
            
            # Validate configuration structure
            config_errors = self.config_service.validate_config()
            if config_errors:
                validation_result['valid'] = False
                validation_result['errors'].extend(config_errors)
            
            # Validate landing zones
            lz_validation = await self._validate_landing_zones(workflow_config.landing_zones)
            if not lz_validation['valid']:
                validation_result['valid'] = False
                validation_result['errors'].extend(lz_validation['errors'])
            validation_result['warnings'].extend(lz_validation['warnings'])
            
            # Validate workflow phases
            phase_validation = self._validate_workflow_phases(workflow_config.phases)
            if not phase_validation['valid']:
                validation_result['valid'] = False
                validation_result['errors'].extend(phase_validation['errors'])
            validation_result['warnings'].extend(phase_validation['warnings'])
            
            # Validate AWS configuration
            aws_validation = await self._validate_aws_config(workflow_config)
            if not aws_validation['valid']:
                validation_result['valid'] = False
                validation_result['errors'].extend(aws_validation['errors'])
            validation_result['warnings'].extend(aws_validation['warnings'])
            
            # Validate timeout and safety settings
            safety_validation = self._validate_safety_settings(workflow_config)
            if not safety_validation['valid']:
                validation_result['valid'] = False
                validation_result['errors'].extend(safety_validation['errors'])
            validation_result['warnings'].extend(safety_validation['warnings'])
            
            self.logger.info(f"Configuration validation completed: {'PASSED' if validation_result['valid'] else 'FAILED'}")
            
        except Exception as e:
            validation_result['valid'] = False
            validation_result['errors'].append(f"Unexpected validation error: {str(e)}")
            self.logger.error(f"Configuration validation failed: {str(e)}")
        
        return validation_result
    
    async def validate_instance_health(self, instance: Instance) -> Dict[str, Any]:
        """Validate the health of a specific instance."""
        self.logger.info(f"Validating health for instance: {instance.instance_id}")
        
        health_result = {
            'instance_id': instance.instance_id,
            'overall_healthy': True,
            'checks': {},
            'validation_time': datetime.utcnow().isoformat()
        }
        
        try:
            # EC2 instance status check
            ec2_health = await self._validate_ec2_health(instance)
            health_result['checks']['ec2_status'] = ec2_health
            if not ec2_health['healthy']:
                health_result['overall_healthy'] = False
            
            # SSM connectivity check
            ssm_health = await self._validate_ssm_connectivity(instance)
            health_result['checks']['ssm_connectivity'] = ssm_health
            if not ssm_health['healthy']:
                health_result['overall_healthy'] = False
            
            # System resource check (if SSM is available)
            if ssm_health['healthy']:
                resource_health = await self._validate_system_resources(instance)
                health_result['checks']['system_resources'] = resource_health
                if not resource_health['healthy']:
                    health_result['overall_healthy'] = False
            
            # Network connectivity check
            network_health = await self._validate_network_connectivity(instance)
            health_result['checks']['network_connectivity'] = network_health
            if not network_health['healthy']:
                health_result['overall_healthy'] = False
            
            # Patch readiness check
            patch_readiness = await self._validate_patch_readiness(instance)
            health_result['checks']['patch_readiness'] = patch_readiness
            if not patch_readiness['healthy']:
                health_result['overall_healthy'] = False
            
            self.logger.info(f"Instance health validation completed: {'HEALTHY' if health_result['overall_healthy'] else 'UNHEALTHY'}")
            
        except Exception as e:
            health_result['overall_healthy'] = False
            health_result['error'] = str(e)
            self.logger.error(f"Instance health validation failed: {str(e)}")
        
        return health_result
    
    async def validate_multiple_instances(
        self,
        instances: List[Instance],
        max_concurrent: int = 10
    ) -> Dict[str, Any]:
        """Validate health for multiple instances concurrently."""
        self.logger.info(f"Validating health for {len(instances)} instances")
        
        validation_result = {
            'total_instances': len(instances),
            'healthy_instances': 0,
            'unhealthy_instances': 0,
            'instance_results': {},
            'validation_time': datetime.utcnow().isoformat()
        }
        
        try:
            # Create semaphore for concurrent validation
            semaphore = asyncio.Semaphore(max_concurrent)
            
            async def validate_single_instance(instance: Instance) -> Tuple[str, Dict[str, Any]]:
                async with semaphore:
                    result = await self.validate_instance_health(instance)
                    return instance.instance_id, result
            
            # Run validations concurrently
            tasks = [validate_single_instance(instance) for instance in instances]
            results = await asyncio.gather(*tasks, return_exceptions=True)
            
            # Process results
            for result in results:
                if isinstance(result, Exception):
                    self.logger.error(f"Instance validation error: {str(result)}")
                    continue
                
                instance_id, health_result = result
                validation_result['instance_results'][instance_id] = health_result
                
                if health_result['overall_healthy']:
                    validation_result['healthy_instances'] += 1
                else:
                    validation_result['unhealthy_instances'] += 1
            
            self.logger.info(
                f"Multiple instance validation completed: "
                f"{validation_result['healthy_instances']} healthy, "
                f"{validation_result['unhealthy_instances']} unhealthy"
            )
            
        except Exception as e:
            self.logger.error(f"Multiple instance validation failed: {str(e)}")
            validation_result['error'] = str(e)
        
        return validation_result
    
    async def validate_pre_patch_readiness(
        self,
        instances: List[Instance],
        workflow_config: WorkflowConfig
    ) -> Dict[str, Any]:
        """Validate that instances are ready for pre-patch workflow."""
        self.logger.info(f"Validating pre-patch readiness for {len(instances)} instances")
        
        readiness_result = {
            'ready_for_patching': True,
            'total_instances': len(instances),
            'ready_instances': 0,
            'not_ready_instances': 0,
            'instance_readiness': {},
            'blocking_issues': [],
            'warnings': [],
            'validation_time': datetime.utcnow().isoformat()
        }
        
        try:
            for instance in instances:
                instance_readiness = await self._validate_instance_patch_readiness(instance, workflow_config)
                readiness_result['instance_readiness'][instance.instance_id] = instance_readiness
                
                if instance_readiness['ready']:
                    readiness_result['ready_instances'] += 1
                else:
                    readiness_result['not_ready_instances'] += 1
                    readiness_result['ready_for_patching'] = False
                    
                    # Collect blocking issues
                    for issue in instance_readiness.get('blocking_issues', []):
                        if issue not in readiness_result['blocking_issues']:
                            readiness_result['blocking_issues'].append(issue)
                
                # Collect warnings
                for warning in instance_readiness.get('warnings', []):
                    if warning not in readiness_result['warnings']:
                        readiness_result['warnings'].append(warning)
            
            self.logger.info(
                f"Pre-patch readiness validation completed: "
                f"{'READY' if readiness_result['ready_for_patching'] else 'NOT READY'}"
            )
            
        except Exception as e:
            readiness_result['ready_for_patching'] = False
            readiness_result['error'] = str(e)
            self.logger.error(f"Pre-patch readiness validation failed: {str(e)}")
        
        return readiness_result
    
    async def _validate_landing_zones(self, landing_zones: List[LandingZoneConfig]) -> Dict[str, Any]:
        """Validate landing zone configurations."""
        validation_result = {'valid': True, 'errors': [], 'warnings': []}
        
        if not landing_zones:
            validation_result['valid'] = False
            validation_result['errors'].append("No landing zones configured")
            return validation_result
        
        enabled_zones = [lz for lz in landing_zones if lz.enabled]
        if not enabled_zones:
            validation_result['valid'] = False
            validation_result['errors'].append("No enabled landing zones found")
            return validation_result
        
        for lz in landing_zones:
            # Validate account ID format
            if not lz.account_id or len(lz.account_id) != 12 or not lz.account_id.isdigit():
                validation_result['valid'] = False
                validation_result['errors'].append(f"Invalid account ID for landing zone {lz.name}: {lz.account_id}")
            
            # Validate regions
            if not lz.regions:
                validation_result['warnings'].append(f"No regions specified for landing zone {lz.name}")
            
            # Validate role name
            if not lz.role_name:
                validation_result['valid'] = False
                validation_result['errors'].append(f"No role name specified for landing zone {lz.name}")
        
        return validation_result
    
    def _validate_workflow_phases(self, phases: List[str]) -> Dict[str, Any]:
        """Validate workflow phase configuration."""
        validation_result = {'valid': True, 'errors': [], 'warnings': []}
        
        if not phases:
            validation_result['valid'] = False
            validation_result['errors'].append("No workflow phases configured")
            return validation_result
        
        valid_phases = ['scanner', 'ami_backup', 'start_servers', 'validation']
        
        for phase in phases:
            if phase not in valid_phases:
                validation_result['valid'] = False
                validation_result['errors'].append(f"Invalid workflow phase: {phase}")
        
        # Check for recommended phase order
        if 'scanner' in phases and phases[0] != 'scanner':
            validation_result['warnings'].append("Scanner phase should typically be first")
        
        if 'validation' in phases and phases[-1] != 'validation':
            validation_result['warnings'].append("Validation phase should typically be last")
        
        return validation_result
    
    async def _validate_aws_config(self, workflow_config: WorkflowConfig) -> Dict[str, Any]:
        """Validate AWS configuration and connectivity."""
        validation_result = {'valid': True, 'errors': [], 'warnings': []}
        
        try:
            # Validate AWS configuration exists
            aws_config = workflow_config.aws
            if not aws_config:
                validation_result['valid'] = False
                validation_result['errors'].append("AWS configuration not found")
                return validation_result
            
            # Validate region
            if not aws_config.region:
                validation_result['valid'] = False
                validation_result['errors'].append("AWS region not specified")
            
            # Test AWS connectivity (basic)
            try:
                ec2_client = EC2Client(aws_config.region)
                # Simple connectivity test
                await ec2_client.describe_regions()
                self.logger.info("AWS connectivity test passed")
            except Exception as e:
                validation_result['warnings'].append(f"AWS connectivity test failed: {str(e)}")
            
        except Exception as e:
            validation_result['valid'] = False
            validation_result['errors'].append(f"AWS configuration validation error: {str(e)}")
        
        return validation_result
    
    def _validate_safety_settings(self, workflow_config: WorkflowConfig) -> Dict[str, Any]:
        """Validate safety and timeout settings."""
        validation_result = {'valid': True, 'errors': [], 'warnings': []}
        
        # Validate AMI backup settings
        if workflow_config.ami_backup and workflow_config.ami_backup.enabled:
            if workflow_config.ami_backup.timeout_minutes < 10:
                validation_result['warnings'].append("AMI backup timeout is very short (< 10 minutes)")
            elif workflow_config.ami_backup.timeout_minutes > 120:
                validation_result['warnings'].append("AMI backup timeout is very long (> 2 hours)")
        
        # Validate server manager settings
        if workflow_config.server_manager:
            if workflow_config.server_manager.max_concurrent_operations > 50:
                validation_result['warnings'].append("High concurrent operations limit may cause throttling")
            
            if workflow_config.server_manager.operation_timeout_minutes < 5:
                validation_result['warnings'].append("Server operation timeout is very short (< 5 minutes)")
        
        # Validate safety settings
        if workflow_config.safety:
            if not workflow_config.safety.require_confirmation:
                validation_result['warnings'].append("Confirmation requirement is disabled - operations will run automatically")
            
            if workflow_config.safety.max_instances_per_batch > 100:
                validation_result['warnings'].append("Large batch size may impact system performance")
        
        return validation_result
    
    async def _validate_ec2_health(self, instance: Instance) -> Dict[str, Any]:
        """Validate EC2 instance health."""
        health_result = {'healthy': True, 'checks': {}, 'issues': []}
        
        try:
            # Use server manager service for health validation
            ec2_health = await self.server_manager_service.validate_instance_health(instance)
            
            # Extract EC2-specific health information
            health_result['checks']['instance_state'] = ec2_health.get('instance_state', 'unknown')
            health_result['checks']['system_status'] = ec2_health.get('system_status', 'unknown')
            health_result['checks']['instance_status'] = ec2_health.get('instance_status', 'unknown')
            
            # Check if instance is in a healthy state
            if instance.status not in [InstanceStatus.RUNNING, InstanceStatus.STOPPED]:
                health_result['healthy'] = False
                health_result['issues'].append(f"Instance is in {instance.status.value} state")
            
        except Exception as e:
            health_result['healthy'] = False
            health_result['issues'].append(f"EC2 health check failed: {str(e)}")
        
        return health_result
    
    async def _validate_ssm_connectivity(self, instance: Instance) -> Dict[str, Any]:
        """Validate SSM connectivity for instance."""
        health_result = {'healthy': True, 'checks': {}, 'issues': []}
        
        try:
            # Check SSM status from instance data
            if hasattr(instance, 'ssm_info') and instance.ssm_info:
                ssm_status = instance.ssm_info.status
                health_result['checks']['ssm_status'] = ssm_status.value
                
                if ssm_status != SSMStatus.ONLINE:
                    health_result['healthy'] = False
                    health_result['issues'].append(f"SSM agent is {ssm_status.value}")
                
                # Check last ping time
                if instance.ssm_info.last_ping_time:
                    time_since_ping = (datetime.utcnow() - instance.ssm_info.last_ping_time).total_seconds()
                    if time_since_ping > 3600:  # 1 hour
                        health_result['healthy'] = False
                        health_result['issues'].append(f"SSM last ping was {time_since_ping/3600:.1f} hours ago")
            else:
                health_result['healthy'] = False
                health_result['issues'].append("No SSM information available")
            
        except Exception as e:
            health_result['healthy'] = False
            health_result['issues'].append(f"SSM connectivity check failed: {str(e)}")
        
        return health_result
    
    async def _validate_system_resources(self, instance: Instance) -> Dict[str, Any]:
        """Validate system resources via SSM."""
        health_result = {'healthy': True, 'checks': {}, 'issues': []}
        
        try:
            # This would typically use SSM to run commands and check resources
            # For now, we'll do basic checks based on instance specifications
            
            # Check if instance has sufficient resources for patching
            if hasattr(instance, 'specs') and instance.specs:
                # Check memory (should have at least 1GB free for patching)
                if instance.specs.memory_gb and instance.specs.memory_gb < 2:
                    health_result['issues'].append("Low memory may impact patching performance")
                
                # Check disk space (basic check)
                if instance.specs.storage_gb and instance.specs.storage_gb < 10:
                    health_result['issues'].append("Low disk space may impact patching")
            
            # For now, mark as healthy unless critical issues found
            health_result['checks']['resource_check'] = 'basic_validation_passed'
            
        except Exception as e:
            health_result['healthy'] = False
            health_result['issues'].append(f"System resource check failed: {str(e)}")
        
        return health_result
    
    async def _validate_network_connectivity(self, instance: Instance) -> Dict[str, Any]:
        """Validate network connectivity for instance."""
        health_result = {'healthy': True, 'checks': {}, 'issues': []}
        
        try:
            # Check if instance has network configuration
            if not instance.private_ip_address:
                health_result['healthy'] = False
                health_result['issues'].append("No private IP address assigned")
            
            # Check if instance is in a VPC
            if not instance.vpc_id:
                health_result['issues'].append("Instance is not in a VPC")
            
            # Check subnet configuration
            if not instance.subnet_id:
                health_result['issues'].append("No subnet assigned")
            
            health_result['checks']['network_config'] = 'basic_validation_passed'
            
        except Exception as e:
            health_result['healthy'] = False
            health_result['issues'].append(f"Network connectivity check failed: {str(e)}")
        
        return health_result
    
    async def _validate_patch_readiness(self, instance: Instance) -> Dict[str, Any]:
        """Validate if instance is ready for patching."""
        health_result = {'healthy': True, 'checks': {}, 'issues': []}
        
        try:
            # Check if instance is in a patchable state
            if instance.status == InstanceStatus.RUNNING:
                health_result['checks']['instance_state'] = 'running_ready_for_patching'
            elif instance.status == InstanceStatus.STOPPED:
                health_result['checks']['instance_state'] = 'stopped_needs_start_before_patching'
            else:
                health_result['healthy'] = False
                health_result['issues'].append(f"Instance state {instance.status.value} not suitable for patching")
            
            # Check if instance has required tags for patching
            if hasattr(instance, 'tags') and instance.tags:
                # Look for patching-related tags
                patch_group = instance.tags.get_tag('Patch Group')
                if not patch_group:
                    health_result['issues'].append("No Patch Group tag found")
            
            # Check platform support
            supported_platforms = ['windows', 'amazon_linux', 'ubuntu', 'rhel', 'centos']
            if instance.platform.value not in supported_platforms:
                health_result['healthy'] = False
                health_result['issues'].append(f"Platform {instance.platform.value} not supported for patching")
            
            health_result['checks']['patch_readiness'] = 'validation_completed'
            
        except Exception as e:
            health_result['healthy'] = False
            health_result['issues'].append(f"Patch readiness check failed: {str(e)}")
        
        return health_result
    
    async def _validate_instance_patch_readiness(
        self,
        instance: Instance,
        workflow_config: WorkflowConfig
    ) -> Dict[str, Any]:
        """Validate if a specific instance is ready for the pre-patch workflow."""
        readiness_result = {
            'ready': True,
            'blocking_issues': [],
            'warnings': [],
            'checks': {}
        }
        
        try:
            # Run comprehensive health validation
            health_result = await self.validate_instance_health(instance)
            readiness_result['checks']['health_validation'] = health_result
            
            if not health_result['overall_healthy']:
                readiness_result['ready'] = False
                readiness_result['blocking_issues'].append(f"Instance {instance.instance_id} failed health checks")
            
            # Check workflow-specific requirements
            if 'ami_backup' in workflow_config.phases:
                if not instance.requires_backup:
                    readiness_result['warnings'].append(f"Instance {instance.instance_id} marked as not requiring backup")
            
            # Check if instance meets minimum requirements
            if hasattr(instance, 'specs') and instance.specs:
                if instance.specs.memory_gb and instance.specs.memory_gb < 1:
                    readiness_result['blocking_issues'].append(f"Instance {instance.instance_id} has insufficient memory")
                    readiness_result['ready'] = False
            
        except Exception as e:
            readiness_result['ready'] = False
            readiness_result['blocking_issues'].append(f"Readiness validation failed for {instance.instance_id}: {str(e)}")
        
        return readiness_result