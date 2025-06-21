"""AWS EC2 client for instance management operations."""

import logging
import asyncio
from typing import List, Dict, Any, Optional, Tuple
from datetime import datetime

from botocore.exceptions import ClientError
from .session_manager import AWSSessionManager
from core.models.instance import Instance, InstanceStatus, Platform


class EC2Client:
    """AWS EC2 client wrapper for instance operations."""
    
    def __init__(
        self,
        region: str,
        account_id: Optional[str] = None,
        role_name: Optional[str] = None,
        external_id: Optional[str] = None
    ):
        self.region = region
        self.account_id = account_id
        self.role_name = role_name
        self.external_id = external_id
        self.logger = logging.getLogger(__name__)
        
        # Initialize session manager
        self.session_manager = AWSSessionManager(region=region)
        
        # Get EC2 client
        self._client = self.session_manager.get_client(
            'ec2',
            account_id=account_id,
            role_name=role_name,
            external_id=external_id,
            region=region
        )
    
    async def describe_instances(
        self,
        instance_ids: Optional[List[str]] = None,
        filters: Optional[List[Dict[str, Any]]] = None,
        max_results: Optional[int] = None
    ) -> List[Dict[str, Any]]:
        """Describe EC2 instances with optional filtering."""
        try:
            self.logger.debug(f"Describing instances in region {self.region}")
            
            # Prepare parameters
            params = {}
            
            if instance_ids:
                params['InstanceIds'] = instance_ids
            
            if filters:
                params['Filters'] = filters
            
            if max_results:
                params['MaxResults'] = max_results
            
            # Get instances
            instances = []
            paginator = self._client.get_paginator('describe_instances')
            
            for page in paginator.paginate(**params):
                for reservation in page['Reservations']:
                    instances.extend(reservation['Instances'])
            
            self.logger.info(f"Found {len(instances)} instances in region {self.region}")
            return instances
            
        except ClientError as e:
            self.logger.error(f"Failed to describe instances: {str(e)}")
            raise
        except Exception as e:
            self.logger.error(f"Unexpected error describing instances: {str(e)}")
            raise
    
    async def describe_instance_status(
        self,
        instance_ids: Optional[List[str]] = None,
        include_all_instances: bool = False
    ) -> List[Dict[str, Any]]:
        """Get instance status information."""
        try:
            self.logger.debug(f"Getting instance status for {len(instance_ids) if instance_ids else 'all'} instances")
            
            params = {
                'IncludeAllInstances': include_all_instances
            }
            
            if instance_ids:
                params['InstanceIds'] = instance_ids
            
            response = self._client.describe_instance_status(**params)
            status_list = response['InstanceStatuses']
            
            self.logger.debug(f"Retrieved status for {len(status_list)} instances")
            return status_list
            
        except ClientError as e:
            self.logger.error(f"Failed to get instance status: {str(e)}")
            raise
        except Exception as e:
            self.logger.error(f"Unexpected error getting instance status: {str(e)}")
            raise
    
    async def start_instances(self, instance_ids: List[str]) -> Dict[str, Any]:
        """Start EC2 instances."""
        try:
            self.logger.info(f"Starting {len(instance_ids)} instances: {instance_ids}")
            
            response = self._client.start_instances(InstanceIds=instance_ids)
            
            starting_instances = response['StartingInstances']
            
            result = {
                'starting_instances': starting_instances,
                'timestamp': datetime.utcnow().isoformat()
            }
            
            self.logger.info(f"Start command sent for {len(starting_instances)} instances")
            return result
            
        except ClientError as e:
            error_code = e.response['Error']['Code']
            
            if error_code == 'InvalidInstanceID.NotFound':
                self.logger.error(f"One or more instance IDs not found: {instance_ids}")
            elif error_code == 'IncorrectInstanceState':
                self.logger.error(f"One or more instances are in incorrect state for starting")
            else:
                self.logger.error(f"Error starting instances: {error_code}")
            
            raise
        except Exception as e:
            self.logger.error(f"Unexpected error starting instances: {str(e)}")
            raise
    
    async def stop_instances(
        self,
        instance_ids: List[str],
        force: bool = False
    ) -> Dict[str, Any]:
        """Stop EC2 instances."""
        try:
            self.logger.info(f"Stopping {len(instance_ids)} instances: {instance_ids}")
            
            params = {
                'InstanceIds': instance_ids,
                'Force': force
            }
            
            response = self._client.stop_instances(**params)
            
            stopping_instances = response['StoppingInstances']
            
            result = {
                'stopping_instances': stopping_instances,
                'timestamp': datetime.utcnow().isoformat()
            }
            
            self.logger.info(f"Stop command sent for {len(stopping_instances)} instances")
            return result
            
        except ClientError as e:
            error_code = e.response['Error']['Code']
            
            if error_code == 'InvalidInstanceID.NotFound':
                self.logger.error(f"One or more instance IDs not found: {instance_ids}")
            elif error_code == 'IncorrectInstanceState':
                self.logger.error(f"One or more instances are in incorrect state for stopping")
            else:
                self.logger.error(f"Error stopping instances: {error_code}")
            
            raise
        except Exception as e:
            self.logger.error(f"Unexpected error stopping instances: {str(e)}")
            raise
    
    async def reboot_instances(self, instance_ids: List[str]) -> Dict[str, Any]:
        """Reboot EC2 instances."""
        try:
            self.logger.info(f"Rebooting {len(instance_ids)} instances: {instance_ids}")
            
            response = self._client.reboot_instances(InstanceIds=instance_ids)
            
            result = {
                'rebooted_instances': instance_ids,
                'timestamp': datetime.utcnow().isoformat()
            }
            
            self.logger.info(f"Reboot command sent for {len(instance_ids)} instances")
            return result
            
        except ClientError as e:
            error_code = e.response['Error']['Code']
            
            if error_code == 'InvalidInstanceID.NotFound':
                self.logger.error(f"One or more instance IDs not found: {instance_ids}")
            elif error_code == 'IncorrectInstanceState':
                self.logger.error(f"One or more instances are in incorrect state for rebooting")
            else:
                self.logger.error(f"Error rebooting instances: {error_code}")
            
            raise
        except Exception as e:
            self.logger.error(f"Unexpected error rebooting instances: {str(e)}")
            raise
    
    async def create_image(
        self,
        instance_id: str,
        name: str,
        description: Optional[str] = None,
        no_reboot: bool = True,
        block_device_mappings: Optional[List[Dict[str, Any]]] = None
    ) -> Dict[str, Any]:
        """Create an AMI from an instance."""
        try:
            self.logger.info(f"Creating AMI for instance {instance_id}: {name}")
            
            params = {
                'InstanceId': instance_id,
                'Name': name,
                'NoReboot': no_reboot
            }
            
            if description:
                params['Description'] = description
            
            if block_device_mappings:
                params['BlockDeviceMappings'] = block_device_mappings
            
            response = self._client.create_image(**params)
            
            ami_id = response['ImageId']
            
            result = {
                'ami_id': ami_id,
                'instance_id': instance_id,
                'name': name,
                'timestamp': datetime.utcnow().isoformat()
            }
            
            self.logger.info(f"AMI creation initiated: {ami_id}")
            return result
            
        except ClientError as e:
            error_code = e.response['Error']['Code']
            
            if error_code == 'InvalidInstanceID.NotFound':
                self.logger.error(f"Instance not found: {instance_id}")
            elif error_code == 'IncorrectInstanceState':
                self.logger.error(f"Instance {instance_id} is in incorrect state for AMI creation")
            else:
                self.logger.error(f"Error creating AMI: {error_code}")
            
            raise
        except Exception as e:
            self.logger.error(f"Unexpected error creating AMI: {str(e)}")
            raise
    
    async def describe_images(
        self,
        image_ids: Optional[List[str]] = None,
        owners: Optional[List[str]] = None,
        filters: Optional[List[Dict[str, Any]]] = None
    ) -> List[Dict[str, Any]]:
        """Describe AMI images."""
        try:
            self.logger.debug("Describing AMI images")
            
            params = {}
            
            if image_ids:
                params['ImageIds'] = image_ids
            
            if owners:
                params['Owners'] = owners
            
            if filters:
                params['Filters'] = filters
            
            response = self._client.describe_images(**params)
            images = response['Images']
            
            self.logger.debug(f"Found {len(images)} AMI images")
            return images
            
        except ClientError as e:
            self.logger.error(f"Failed to describe images: {str(e)}")
            raise
        except Exception as e:
            self.logger.error(f"Unexpected error describing images: {str(e)}")
            raise
    
    async def deregister_image(self, image_id: str) -> Dict[str, Any]:
        """Deregister an AMI."""
        try:
            self.logger.info(f"Deregistering AMI: {image_id}")
            
            response = self._client.deregister_image(ImageId=image_id)
            
            result = {
                'image_id': image_id,
                'deregistered': True,
                'timestamp': datetime.utcnow().isoformat()
            }
            
            self.logger.info(f"AMI deregistered: {image_id}")
            return result
            
        except ClientError as e:
            error_code = e.response['Error']['Code']
            
            if error_code == 'InvalidAMIID.NotFound':
                self.logger.error(f"AMI not found: {image_id}")
            else:
                self.logger.error(f"Error deregistering AMI: {error_code}")
            
            raise
        except Exception as e:
            self.logger.error(f"Unexpected error deregistering AMI: {str(e)}")
            raise
    
    async def wait_for_instance_state(
        self,
        instance_ids: List[str],
        target_state: str,
        max_wait_time: int = 600
    ) -> Dict[str, Any]:
        """Wait for instances to reach target state."""
        try:
            self.logger.info(f"Waiting for instances to reach state '{target_state}': {instance_ids}")
            
            waiter_name = f"instance_{target_state}"
            
            if waiter_name in self._client.waiter_names:
                waiter = self._client.get_waiter(waiter_name)
                
                waiter.wait(
                    InstanceIds=instance_ids,
                    WaiterConfig={
                        'Delay': 15,
                        'MaxAttempts': max_wait_time // 15
                    }
                )
                
                result = {
                    'instance_ids': instance_ids,
                    'target_state': target_state,
                    'success': True,
                    'timestamp': datetime.utcnow().isoformat()
                }
                
                self.logger.info(f"Instances reached target state '{target_state}'")
                return result
            else:
                # Manual polling if waiter not available
                return await self._poll_instance_state(instance_ids, target_state, max_wait_time)
                
        except Exception as e:
            self.logger.error(f"Error waiting for instance state: {str(e)}")
            raise
    
    async def _poll_instance_state(
        self,
        instance_ids: List[str],
        target_state: str,
        max_wait_time: int
    ) -> Dict[str, Any]:
        """Poll instance state manually."""
        start_time = datetime.utcnow()
        poll_interval = 15
        
        while (datetime.utcnow() - start_time).total_seconds() < max_wait_time:
            try:
                instances = await self.describe_instances(instance_ids=instance_ids)
                
                all_ready = True
                for instance in instances:
                    current_state = instance['State']['Name']
                    if current_state != target_state:
                        all_ready = False
                        break
                
                if all_ready:
                    return {
                        'instance_ids': instance_ids,
                        'target_state': target_state,
                        'success': True,
                        'timestamp': datetime.utcnow().isoformat()
                    }
                
                # Wait before next poll
                await asyncio.sleep(poll_interval)
                
            except Exception as e:
                self.logger.warning(f"Error during state polling: {str(e)}")
                await asyncio.sleep(poll_interval)
        
        # Timeout reached
        raise TimeoutError(f"Instances did not reach state '{target_state}' within {max_wait_time} seconds")
    
    async def describe_regions(self) -> List[Dict[str, Any]]:
        """Describe available AWS regions."""
        try:
            self.logger.debug("Describing AWS regions")
            
            response = self._client.describe_regions()
            regions = response['Regions']
            
            self.logger.debug(f"Found {len(regions)} regions")
            return regions
            
        except ClientError as e:
            self.logger.error(f"Failed to describe regions: {str(e)}")
            raise
        except Exception as e:
            self.logger.error(f"Unexpected error describing regions: {str(e)}")
            raise
    
    async def describe_availability_zones(self) -> List[Dict[str, Any]]:
        """Describe availability zones in current region."""
        try:
            self.logger.debug(f"Describing availability zones in {self.region}")
            
            response = self._client.describe_availability_zones()
            zones = response['AvailabilityZones']
            
            self.logger.debug(f"Found {len(zones)} availability zones")
            return zones
            
        except ClientError as e:
            self.logger.error(f"Failed to describe availability zones: {str(e)}")
            raise
        except Exception as e:
            self.logger.error(f"Unexpected error describing availability zones: {str(e)}")
            raise
    
    def _map_instance_state(self, aws_state: str) -> InstanceStatus:
        """Map AWS instance state to our InstanceStatus enum."""
        state_mapping = {
            'pending': InstanceStatus.PENDING,
            'running': InstanceStatus.RUNNING,
            'shutting-down': InstanceStatus.STOPPING,
            'terminated': InstanceStatus.TERMINATED,
            'stopping': InstanceStatus.STOPPING,
            'stopped': InstanceStatus.STOPPED
        }
        
        return state_mapping.get(aws_state, InstanceStatus.UNKNOWN)
    
    def _map_platform(self, platform_details: Optional[str], platform: Optional[str]) -> Platform:
        """Map AWS platform information to our Platform enum."""
        if platform_details:
            platform_lower = platform_details.lower()
            if 'windows' in platform_lower:
                return Platform.WINDOWS
            elif 'linux' in platform_lower:
                if 'amazon' in platform_lower:
                    return Platform.AMAZON_LINUX
                elif 'ubuntu' in platform_lower:
                    return Platform.UBUNTU
                elif 'red hat' in platform_lower or 'rhel' in platform_lower:
                    return Platform.RHEL
                elif 'centos' in platform_lower:
                    return Platform.CENTOS
                else:
                    return Platform.LINUX
        
        if platform and platform.lower() == 'windows':
            return Platform.WINDOWS
        
        return Platform.LINUX  # Default to Linux