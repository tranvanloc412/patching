"""Scanner service implementation."""

import asyncio
import logging
from datetime import datetime
from typing import List, Dict, Any, Optional, Set

from core.interfaces.scanner_interface import IScannerService
from core.interfaces.config_interface import IConfigService
from core.models.instance import Instance, InstanceStatus, Platform, SSMStatus, InstanceTags, InstanceNetworking, InstanceSpecs, SSMInfo
from core.models.config import LandingZoneConfig, ScannerConfig
from infrastructure.aws.ec2_client import EC2Client
from infrastructure.aws.ssm_client import SSMClient


class ScannerService(IScannerService):
    """Implementation of scanner service for instance discovery."""
    
    def __init__(self, config_service: IConfigService,
                 ec2_client: EC2Client,
                 ssm_client: SSMClient):
        self.config_service = config_service
        self.ec2_client = ec2_client
        self.ssm_client = ssm_client
        self.logger = logging.getLogger(__name__)
    
    async def scan_landing_zone(self, landing_zone_config: LandingZoneConfig) -> List[Instance]:
        """Scan a single landing zone for instances."""
        self.logger.info(f"Starting scan of landing zone: {landing_zone_config.name}")
        
        try:
            # Configure AWS clients for this landing zone
            await self._configure_clients_for_landing_zone(landing_zone_config)
            
            # Get scanner configuration
            scanner_config = self.config_service.get_phase_config("scanner")
            
            # Discover EC2 instances
            instances = await self._discover_ec2_instances(landing_zone_config, scanner_config)
            
            # Enrich with SSM information
            instances = await self._enrich_with_ssm_info(instances, scanner_config)
            
            # Apply filters
            instances = await self._apply_filters(instances, landing_zone_config, scanner_config)
            
            # Validate instances
            instances = await self._validate_instances(instances, scanner_config)
            
            self.logger.info(f"Completed scan of landing zone {landing_zone_config.name}: "
                           f"found {len(instances)} instances")
            
            return instances
            
        except Exception as e:
            self.logger.error(f"Error scanning landing zone {landing_zone_config.name}: {str(e)}")
            raise
    
    async def scan_multiple_landing_zones(self, landing_zone_configs: List[LandingZoneConfig]) -> Dict[str, List[Instance]]:
        """Scan multiple landing zones concurrently."""
        self.logger.info(f"Starting scan of {len(landing_zone_configs)} landing zones")
        
        # Get scanner configuration
        scanner_config = self.config_service.get_phase_config("scanner")
        max_concurrent = scanner_config.get("max_concurrent_scans", 5)
        
        # Create semaphore to limit concurrent scans
        semaphore = asyncio.Semaphore(max_concurrent)
        
        async def scan_with_semaphore(lz_config: LandingZoneConfig) -> tuple[str, List[Instance]]:
            async with semaphore:
                instances = await self.scan_landing_zone(lz_config)
                return lz_config.name, instances
        
        # Execute scans concurrently
        tasks = [scan_with_semaphore(lz_config) for lz_config in landing_zone_configs]
        results = await asyncio.gather(*tasks, return_exceptions=True)
        
        # Process results
        landing_zone_results = {}
        for result in results:
            if isinstance(result, Exception):
                self.logger.error(f"Landing zone scan failed: {str(result)}")
                continue
            
            lz_name, instances = result
            landing_zone_results[lz_name] = instances
        
        total_instances = sum(len(instances) for instances in landing_zone_results.values())
        self.logger.info(f"Completed scan of all landing zones: found {total_instances} total instances")
        
        return landing_zone_results
    
    async def get_instance_details(self, instance_id: str, region: str) -> Optional[Instance]:
        """Get detailed information for a specific instance."""
        try:
            # Configure client for the region
            await self.ec2_client.configure_for_region(region)
            
            # Get instance details from EC2
            ec2_instance = await self.ec2_client.describe_instance(instance_id)
            if not ec2_instance:
                return None
            
            # Convert to our Instance model
            instance = await self._convert_ec2_instance_to_model(ec2_instance, "unknown", region)
            
            # Enrich with SSM information
            await self._enrich_instance_with_ssm(instance)
            
            return instance
            
        except Exception as e:
            self.logger.error(f"Error getting instance details for {instance_id}: {str(e)}")
            return None
    
    async def validate_ssm_connectivity(self, instances: List[Instance]) -> Dict[str, bool]:
        """Validate SSM connectivity for multiple instances."""
        self.logger.info(f"Validating SSM connectivity for {len(instances)} instances")
        
        # Group instances by region for efficient batch processing
        instances_by_region = {}
        for instance in instances:
            region = instance.region
            if region not in instances_by_region:
                instances_by_region[region] = []
            instances_by_region[region].append(instance)
        
        connectivity_results = {}
        
        # Process each region
        for region, region_instances in instances_by_region.items():
            try:
                await self.ssm_client.configure_for_region(region)
                
                # Get SSM managed instances for this region
                managed_instances = await self.ssm_client.get_managed_instances()
                managed_instance_ids = {inst['InstanceId'] for inst in managed_instances}
                
                # Check connectivity for each instance
                for instance in region_instances:
                    is_connected = instance.instance_id in managed_instance_ids
                    connectivity_results[instance.instance_id] = is_connected
                    
                    # Update instance SSM status
                    if is_connected:
                        instance.ssm_info.status = SSMStatus.ONLINE
                    else:
                        instance.ssm_info.status = SSMStatus.NOT_REGISTERED
                        
            except Exception as e:
                self.logger.error(f"Error validating SSM connectivity in region {region}: {str(e)}")
                # Mark all instances in this region as unknown
                for instance in region_instances:
                    connectivity_results[instance.instance_id] = False
                    instance.ssm_info.status = SSMStatus.UNKNOWN
        
        connected_count = sum(1 for connected in connectivity_results.values() if connected)
        self.logger.info(f"SSM connectivity validation complete: {connected_count}/{len(instances)} connected")
        
        return connectivity_results
    
    async def _configure_clients_for_landing_zone(self, landing_zone_config: LandingZoneConfig) -> None:
        """Configure AWS clients for a specific landing zone."""
        aws_config = landing_zone_config.aws_config
        
        # Configure EC2 client
        await self.ec2_client.configure(
            region=aws_config.region,
            role_arn=aws_config.assume_role_arn,
            profile=aws_config.profile
        )
        
        # Configure SSM client
        await self.ssm_client.configure(
            region=aws_config.region,
            role_arn=aws_config.assume_role_arn,
            profile=aws_config.profile
        )
    
    async def _discover_ec2_instances(self, landing_zone_config: LandingZoneConfig,
                                     scanner_config: Dict[str, Any]) -> List[Instance]:
        """Discover EC2 instances in a landing zone."""
        self.logger.debug(f"Discovering EC2 instances in {landing_zone_config.name}")
        
        # Build filters for EC2 describe_instances call
        filters = []
        
        # Filter by state if configured
        if not scanner_config.get("include_stopped_instances", True):
            filters.append({
                'Name': 'instance-state-name',
                'Values': ['running', 'pending']
            })
        
        # Exclude terminated instances
        if scanner_config.get("exclude_terminated", True):
            filters.append({
                'Name': 'instance-state-name',
                'Values': ['running', 'pending', 'stopping', 'stopped']
            })
        
        # Apply tag filters from landing zone config
        for tag_key, tag_value in landing_zone_config.tag_filters.items():
            filters.append({
                'Name': f'tag:{tag_key}',
                'Values': [tag_value]
            })
        
        # Get instances from EC2
        ec2_instances = await self.ec2_client.describe_instances(filters=filters)
        
        # Convert to our Instance model
        instances = []
        for ec2_instance in ec2_instances:
            try:
                instance = await self._convert_ec2_instance_to_model(
                    ec2_instance, landing_zone_config.name, landing_zone_config.region
                )
                instances.append(instance)
            except Exception as e:
                self.logger.warning(f"Error converting instance {ec2_instance.get('InstanceId', 'unknown')}: {str(e)}")
                continue
        
        self.logger.debug(f"Discovered {len(instances)} instances in {landing_zone_config.name}")
        return instances
    
    async def _convert_ec2_instance_to_model(self, ec2_instance: Dict[str, Any],
                                           landing_zone: str, region: str) -> Instance:
        """Convert EC2 instance data to our Instance model."""
        instance_id = ec2_instance['InstanceId']
        
        # Parse instance state
        state_name = ec2_instance['State']['Name']
        try:
            status = InstanceStatus(state_name.replace('-', '_'))
        except ValueError:
            status = InstanceStatus.UNKNOWN
        
        # Parse platform
        platform_value = ec2_instance.get('Platform', 'linux').lower()
        if platform_value == 'windows':
            platform = Platform.WINDOWS
        else:
            # Try to determine Linux distribution from image description
            image_description = ec2_instance.get('ImageDescription', '').lower()
            if 'amazon' in image_description:
                platform = Platform.AMAZON_LINUX
            elif 'ubuntu' in image_description:
                platform = Platform.UBUNTU
            elif 'rhel' in image_description or 'red hat' in image_description:
                platform = Platform.RHEL
            elif 'centos' in image_description:
                platform = Platform.CENTOS
            elif 'suse' in image_description:
                platform = Platform.SUSE
            else:
                platform = Platform.LINUX
        
        # Parse tags
        tags_dict = {tag['Key']: tag['Value'] for tag in ec2_instance.get('Tags', [])}
        tags = InstanceTags(
            name=tags_dict.get('Name'),
            environment=tags_dict.get('Environment'),
            application=tags_dict.get('Application'),
            owner=tags_dict.get('Owner'),
            cost_center=tags_dict.get('CostCenter'),
            backup_required=tags_dict.get('BackupRequired', '').lower() == 'true',
            patch_group=tags_dict.get('PatchGroup'),
            maintenance_window=tags_dict.get('MaintenanceWindow'),
            additional_tags=tags_dict
        )
        
        # Parse networking
        networking = InstanceNetworking(
            vpc_id=ec2_instance.get('VpcId'),
            subnet_id=ec2_instance.get('SubnetId'),
            private_ip=ec2_instance.get('PrivateIpAddress'),
            public_ip=ec2_instance.get('PublicIpAddress'),
            security_groups=[sg['GroupId'] for sg in ec2_instance.get('SecurityGroups', [])],
            availability_zone=ec2_instance.get('Placement', {}).get('AvailabilityZone')
        )
        
        # Parse instance specifications
        specs = InstanceSpecs(
            instance_type=ec2_instance.get('InstanceType'),
            architecture=ec2_instance.get('Architecture'),
            cpu_cores=ec2_instance.get('CpuOptions', {}).get('CoreCount'),
            # Memory and storage would need additional API calls
        )
        
        # Parse launch time
        launch_time = None
        if 'LaunchTime' in ec2_instance:
            launch_time = ec2_instance['LaunchTime']
            if isinstance(launch_time, str):
                launch_time = datetime.fromisoformat(launch_time.replace('Z', '+00:00'))
        
        # Create instance
        instance = Instance(
            instance_id=instance_id,
            landing_zone=landing_zone,
            region=region,
            account_id=ec2_instance.get('OwnerId', ''),
            status=status,
            platform=platform,
            tags=tags,
            networking=networking,
            specs=specs,
            ami_id=ec2_instance.get('ImageId'),
            launch_time=launch_time,
            last_scan_time=datetime.utcnow()
        )
        
        return instance
    
    async def _enrich_with_ssm_info(self, instances: List[Instance],
                                   scanner_config: Dict[str, Any]) -> List[Instance]:
        """Enrich instances with SSM information."""
        if not instances:
            return instances
        
        self.logger.debug(f"Enriching {len(instances)} instances with SSM information")
        
        try:
            # Get SSM managed instances
            managed_instances = await self.ssm_client.get_managed_instances()
            managed_instances_dict = {inst['InstanceId']: inst for inst in managed_instances}
            
            # Enrich each instance
            for instance in instances:
                await self._enrich_instance_with_ssm(instance, managed_instances_dict)
                
        except Exception as e:
            self.logger.warning(f"Error enriching instances with SSM info: {str(e)}")
            # Set all instances to unknown SSM status
            for instance in instances:
                instance.ssm_info.status = SSMStatus.UNKNOWN
        
        return instances
    
    async def _enrich_instance_with_ssm(self, instance: Instance,
                                       managed_instances_dict: Optional[Dict[str, Any]] = None) -> None:
        """Enrich a single instance with SSM information."""
        if managed_instances_dict is None:
            try:
                managed_instances = await self.ssm_client.get_managed_instances()
                managed_instances_dict = {inst['InstanceId']: inst for inst in managed_instances}
            except Exception as e:
                self.logger.warning(f"Error getting SSM managed instances: {str(e)}")
                instance.ssm_info.status = SSMStatus.UNKNOWN
                return
        
        ssm_instance = managed_instances_dict.get(instance.instance_id)
        
        if ssm_instance:
            # Parse SSM status
            ping_status = ssm_instance.get('PingStatus', 'Unknown')
            if ping_status == 'Online':
                ssm_status = SSMStatus.ONLINE
            elif ping_status == 'ConnectionLost':
                ssm_status = SSMStatus.CONNECTION_LOST
            elif ping_status == 'Inactive':
                ssm_status = SSMStatus.INACTIVE
            else:
                ssm_status = SSMStatus.UNKNOWN
            
            # Parse last ping time
            last_ping = ssm_instance.get('LastPingDateTime')
            if isinstance(last_ping, str):
                last_ping = datetime.fromisoformat(last_ping.replace('Z', '+00:00'))
            
            # Update SSM info
            instance.ssm_info = SSMInfo(
                status=ssm_status,
                agent_version=ssm_instance.get('AgentVersion'),
                last_ping=last_ping,
                platform_type=ssm_instance.get('PlatformType'),
                platform_name=ssm_instance.get('PlatformName'),
                platform_version=ssm_instance.get('PlatformVersion'),
                is_latest_version=ssm_instance.get('IsLatestVersion'),
                ping_status=ping_status
            )
            
            instance.is_managed = True
        else:
            instance.ssm_info.status = SSMStatus.NOT_REGISTERED
            instance.is_managed = False
    
    async def _apply_filters(self, instances: List[Instance],
                           landing_zone_config: LandingZoneConfig,
                           scanner_config: Dict[str, Any]) -> List[Instance]:
        """Apply filtering rules to instances."""
        filtered_instances = []
        
        for instance in instances:
            # Apply platform filters
            platforms = scanner_config.get("platforms", ["windows", "linux"])
            if instance.platform.value not in platforms:
                continue
            
            # Apply include/exclude patterns
            if not self._matches_patterns(instance, landing_zone_config.include_patterns,
                                         landing_zone_config.exclude_patterns):
                continue
            
            # Apply minimum uptime filter
            min_uptime_hours = scanner_config.get("min_uptime_hours", 0)
            if min_uptime_hours > 0 and instance.launch_time:
                uptime = datetime.utcnow() - instance.launch_time
                if uptime.total_seconds() < min_uptime_hours * 3600:
                    continue
            
            # Apply spot instance filter
            if scanner_config.get("exclude_spot_instances", False):
                # This would require additional EC2 API call to check spot instance status
                pass
            
            filtered_instances.append(instance)
        
        self.logger.debug(f"Applied filters: {len(instances)} -> {len(filtered_instances)} instances")
        return filtered_instances
    
    def _matches_patterns(self, instance: Instance, include_patterns: List[str],
                         exclude_patterns: List[str]) -> bool:
        """Check if instance matches include/exclude patterns."""
        import re
        
        # Check exclude patterns first
        for pattern in exclude_patterns:
            if re.search(pattern, instance.display_name, re.IGNORECASE):
                return False
            if re.search(pattern, instance.instance_id, re.IGNORECASE):
                return False
        
        # If no include patterns, include by default
        if not include_patterns:
            return True
        
        # Check include patterns
        for pattern in include_patterns:
            if re.search(pattern, instance.display_name, re.IGNORECASE):
                return True
            if re.search(pattern, instance.instance_id, re.IGNORECASE):
                return True
        
        return False
    
    async def _validate_instances(self, instances: List[Instance],
                                scanner_config: Dict[str, Any]) -> List[Instance]:
        """Validate instances for patching readiness."""
        for instance in instances:
            instance.clear_validation_errors()
            
            # Check if instance is running
            if not instance.is_running:
                instance.add_validation_error("Instance is not in running state")
            
            # Check SSM connectivity
            if not instance.ssm_online:
                instance.add_validation_error("SSM agent is not online")
            
            # Check platform support
            if instance.platform == Platform.WINDOWS:
                # Windows-specific validations
                pass
            else:
                # Linux-specific validations
                pass
            
            # Set patchable flag
            instance.is_patchable = (
                instance.is_running and
                instance.ssm_online and
                len(instance.validation_errors) == 0
            )
        
        patchable_count = sum(1 for instance in instances if instance.is_patchable)
        self.logger.info(f"Instance validation complete: {patchable_count}/{len(instances)} patchable")
        
        return instances