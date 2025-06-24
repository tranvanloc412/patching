"""AWS EC2 client for instance management operations."""

import asyncio
from typing import List, Dict, Any, Optional
from datetime import datetime

from botocore.exceptions import ClientError
from .session_manager import AWSSessionManager
from core.models.instance import InstanceStatus, Platform
from core.utils.logger import get_infrastructure_logger


class EC2Client:
    """AWS EC2 client wrapper for instance operations."""

    def __init__(
        self,
        region: str,
        account_id: Optional[str] = None,
        role_name: Optional[str] = None,
        run_mode: Optional[str] = None,
    ):
        self.region = region
        self.account_id = account_id
        self.role_name = role_name
        self.run_mode = run_mode
        self.logger = get_infrastructure_logger(__name__)
        self._client = None
        self._session_manager = AWSSessionManager(region=region)
    
    def _ensure_client(self) -> None:
        """Ensure the EC2 client is initialized (lazy initialization)."""
        if self._client is None:
            session = self._session_manager.get_session(self.account_id, self.role_name, self.run_mode)
            self._client = session.client("ec2", region_name=self.region)
    
    def configure_for_region(self, region: str) -> None:
        """Configure the client for a different region."""
        self.region = region
        self._session_manager = AWSSessionManager(region=region)
        self._client = None  # Reset client to force re-initialization with new region
    
    def _handle_error(self, operation: str, error: Exception) -> None:
        """Handle AWS client errors with consistent logging."""
        if isinstance(error, ClientError):
            error_code = error.response["Error"]["Code"]
            self.logger.error(f"{operation} failed: {error_code}")
        else:
            self.logger.error(f"{operation} failed: {str(error)}")
        raise

    async def describe_instances(
        self,
        instance_ids: Optional[List[str]] = None,
        filters: Optional[List[Dict[str, Any]]] = None,
        max_results: Optional[int] = None,
    ) -> List[Dict[str, Any]]:
        """Describe EC2 instances with optional filtering."""
        try:
            self._ensure_client()
            params = {}
            if instance_ids:
                params["InstanceIds"] = instance_ids
            if filters:
                params["Filters"] = filters
            if max_results:
                params["MaxResults"] = max_results

            instances = []
            paginator = self._client.get_paginator("describe_instances")
            for page in paginator.paginate(**params):
                for reservation in page["Reservations"]:
                    instances.extend(reservation["Instances"])
            
            return instances
        except Exception as e:
            self._handle_error("Describe instances", e)

    async def describe_instance_status(
        self,
        instance_ids: Optional[List[str]] = None,
        include_all_instances: bool = False,
    ) -> List[Dict[str, Any]]:
        """Get instance status information."""
        try:
            self._ensure_client()
            params = {"IncludeAllInstances": include_all_instances}
            if instance_ids:
                params["InstanceIds"] = instance_ids
            
            response = self._client.describe_instance_status(**params)
            return response["InstanceStatuses"]
        except Exception as e:
            self._handle_error("Describe instance status", e)

    async def start_instances(self, instance_ids: List[str]) -> Dict[str, Any]:
        """Start EC2 instances."""
        try:
            self._ensure_client()
            response = self._client.start_instances(InstanceIds=instance_ids)
            return {
                "starting_instances": response["StartingInstances"],
                "timestamp": datetime.utcnow().isoformat(),
            }
        except Exception as e:
            self._handle_error("Start instances", e)

    async def stop_instances(
        self, instance_ids: List[str], force: bool = False
    ) -> Dict[str, Any]:
        """Stop EC2 instances."""
        try:
            self._ensure_client()
            response = self._client.stop_instances(
                InstanceIds=instance_ids, Force=force
            )
            return {
                "stopping_instances": response["StoppingInstances"],
                "timestamp": datetime.utcnow().isoformat(),
            }
        except Exception as e:
            self._handle_error("Stop instances", e)

    async def reboot_instances(self, instance_ids: List[str]) -> Dict[str, Any]:
        """Reboot EC2 instances."""
        try:
            self._ensure_client()
            self._client.reboot_instances(InstanceIds=instance_ids)
            return {
                "rebooted_instances": instance_ids,
                "timestamp": datetime.utcnow().isoformat(),
            }
        except Exception as e:
            self._handle_error("Reboot instances", e)

    async def create_image(
        self,
        instance_id: str,
        name: str,
        description: Optional[str] = None,
        no_reboot: bool = True,
        block_device_mappings: Optional[List[Dict[str, Any]]] = None,
    ) -> Dict[str, Any]:
        """Create an AMI from an instance."""
        try:
            self._ensure_client()
            params = {"InstanceId": instance_id, "Name": name, "NoReboot": no_reboot}
            if description:
                params["Description"] = description
            if block_device_mappings:
                params["BlockDeviceMappings"] = block_device_mappings

            response = self._client.create_image(**params)
            return {
                "ami_id": response["ImageId"],
                "instance_id": instance_id,
                "name": name,
                "timestamp": datetime.utcnow().isoformat(),
            }
        except Exception as e:
            self._handle_error("Create AMI", e)

    async def describe_images(
        self,
        image_ids: Optional[List[str]] = None,
        owners: Optional[List[str]] = None,
        filters: Optional[List[Dict[str, Any]]] = None,
    ) -> List[Dict[str, Any]]:
        """Describe AMI images."""
        try:
            self._ensure_client()
            params = {}
            if image_ids:
                params["ImageIds"] = image_ids
            if owners:
                params["Owners"] = owners
            if filters:
                params["Filters"] = filters

            response = self._client.describe_images(**params)
            return response["Images"]
        except Exception as e:
            self._handle_error("Describe images", e)

    async def deregister_image(self, image_id: str) -> Dict[str, Any]:
        """Deregister an AMI."""
        try:
            self._ensure_client()
            self._client.deregister_image(ImageId=image_id)
            return {
                "image_id": image_id,
                "deregistered": True,
                "timestamp": datetime.utcnow().isoformat(),
            }
        except Exception as e:
            self._handle_error("Deregister AMI", e)

    async def wait_for_instance_state(
        self, instance_ids: List[str], target_state: str, max_wait_time: int = 600
    ) -> Dict[str, Any]:
        """Wait for instances to reach target state."""
        try:
            self._ensure_client()
            waiter_name = f"instance_{target_state}"
            
            if waiter_name in self._client.waiter_names:
                waiter = self._client.get_waiter(waiter_name)
                waiter.wait(
                    InstanceIds=instance_ids,
                    WaiterConfig={"Delay": 15, "MaxAttempts": max_wait_time // 15},
                )
            else:
                await self._poll_instance_state(instance_ids, target_state, max_wait_time)
            
            return {
                "instance_ids": instance_ids,
                "target_state": target_state,
                "success": True,
                "timestamp": datetime.utcnow().isoformat(),
            }
        except Exception as e:
            self._handle_error("Wait for instance state", e)

    async def _poll_instance_state(
        self, instance_ids: List[str], target_state: str, max_wait_time: int
    ) -> None:
        """Poll instance state manually."""
        start_time = datetime.utcnow()
        poll_interval = 15

        while (datetime.utcnow() - start_time).total_seconds() < max_wait_time:
            try:
                instances = await self.describe_instances(instance_ids=instance_ids)
                if all(instance["State"]["Name"] == target_state for instance in instances):
                    return
                await asyncio.sleep(poll_interval)
            except Exception:
                await asyncio.sleep(poll_interval)

        raise TimeoutError(
            f"Instances did not reach state '{target_state}' within {max_wait_time} seconds"
        )

    async def describe_regions(self) -> List[Dict[str, Any]]:
        """Describe available AWS regions."""
        try:
            self._ensure_client()
            response = self._client.describe_regions()
            return response["Regions"]
        except Exception as e:
            self._handle_error("Describe regions", e)

    async def describe_availability_zones(self) -> List[Dict[str, Any]]:
        """Describe availability zones in current region."""
        try:
            self._ensure_client()
            response = self._client.describe_availability_zones()
            return response["AvailabilityZones"]
        except Exception as e:
            self._handle_error("Describe availability zones", e)

    def _map_instance_state(self, aws_state: str) -> InstanceStatus:
        """Map AWS instance state to our InstanceStatus enum."""
        state_mapping = {
            "pending": InstanceStatus.PENDING,
            "running": InstanceStatus.RUNNING,
            "shutting-down": InstanceStatus.STOPPING,
            "terminated": InstanceStatus.TERMINATED,
            "stopping": InstanceStatus.STOPPING,
            "stopped": InstanceStatus.STOPPED,
        }

        return state_mapping.get(aws_state, InstanceStatus.UNKNOWN)

    def _map_platform(
        self, platform_details: Optional[str], platform: Optional[str]
    ) -> Platform:
        """Map AWS platform information to our Platform enum."""
        if platform_details:
            platform_lower = platform_details.lower()
            if "windows" in platform_lower:
                return Platform.WINDOWS
            else:
                return Platform.LINUX  # All Linux variants treated as LINUX

        if platform and platform.lower() == "windows":
            return Platform.WINDOWS

        return Platform.LINUX  # Default to LINUX
