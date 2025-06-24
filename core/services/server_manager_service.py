import asyncio
import logging
from datetime import datetime, timedelta
from typing import List, Dict, Any, Optional

from core.interfaces.server_manager_interface import IServerManagerService
from core.interfaces.config_interface import IConfigService
from core.models.instance import Instance, InstanceStatus
from infrastructure.aws.ec2_client import EC2Client
from infrastructure.aws.ssm_client import SSMClient


class ServerManagerService(IServerManagerService):
    """Simplified server manager service for basic instance operations."""

    def __init__(
        self,
        config_service: IConfigService,
        ec2_client: EC2Client,
        ssm_client: SSMClient,
    ):
        self.config_service = config_service
        self.ec2_client = ec2_client
        self.ssm_client = ssm_client
        self.logger = logging.getLogger(__name__)

    def _handle_error(self, message: str, error: Exception) -> None:
        """Centralized error handling and logging."""
        error_msg = f"{message}: {str(error)}"
        self.logger.error(error_msg)

    def _create_operation_result(
        self, instance_id: str, operation: str
    ) -> Dict[str, Any]:
        """Create a standardized operation result dictionary."""
        return {
            "instance_id": instance_id,
            "operation": operation,
            "success": False,
            "start_time": datetime.utcnow(),
            "end_time": None,
            "error_message": None,
        }

    async def _wait_for_state(
        self,
        instance_id: str,
        region: str,
        target_states: List[InstanceStatus],
        timeout_minutes: int,
        invalid_states: List[InstanceStatus] = None,
    ) -> tuple[bool, InstanceStatus, str]:
        """Wait for instance to reach target state with timeout."""
        timeout_time = datetime.utcnow() + timedelta(minutes=timeout_minutes)
        invalid_states = invalid_states or []

        while datetime.utcnow() < timeout_time:
            current_state = await self.get_instance_state(instance_id, region)

            if current_state in target_states:
                return True, current_state, None

            if current_state in invalid_states:
                return (
                    False,
                    current_state,
                    f"Instance entered {current_state.value} state",
                )

            await asyncio.sleep(10)

        return (
            False,
            await self.get_instance_state(instance_id, region),
            "Timeout waiting for state change",
        )

    async def start_instance(
        self,
        instance_id: str,
        account_id: str,
        region: str,
        role_name: str,
        timeout_minutes: int = 10,
    ) -> Dict[str, Any]:
        """Start a single EC2 instance."""
        result = self._create_operation_result(instance_id, "start")

        try:
            current_state = await self.get_instance_state(instance_id, region)

            if current_state == InstanceStatus.RUNNING:
                result["success"] = True
                result["end_time"] = datetime.utcnow()
                return result

            if current_state not in [InstanceStatus.STOPPED, InstanceStatus.STOPPING]:
                result["error_message"] = (
                    f"Instance is in {current_state.value} state, cannot start"
                )
                result["end_time"] = datetime.utcnow()
                return result

            await self.ec2_client.start_instance(instance_id)

            success, final_state, error_msg = await self._wait_for_state(
                instance_id,
                region,
                [InstanceStatus.RUNNING],
                timeout_minutes,
                [InstanceStatus.TERMINATED, InstanceStatus.TERMINATING],
            )

            result["success"] = success
            result["end_time"] = datetime.utcnow()
            if not success:
                result["error_message"] = error_msg

        except Exception as e:
            self._handle_error(f"Failed to start instance {instance_id}", e)
            result["error_message"] = str(e)
            result["end_time"] = datetime.utcnow()

        return result

    async def stop_instance(
        self,
        instance_id: str,
        account_id: str,
        region: str,
        role_name: str,
        timeout_minutes: int = 10,
        force: bool = False,
    ) -> Dict[str, Any]:
        """Stop a single EC2 instance."""
        result = self._create_operation_result(instance_id, "stop")

        try:
            current_state = await self.get_instance_state(instance_id, region)

            if current_state in [InstanceStatus.STOPPED, InstanceStatus.STOPPING]:
                result["success"] = True
                result["end_time"] = datetime.utcnow()
                return result

            if current_state not in [InstanceStatus.RUNNING, InstanceStatus.PENDING]:
                result["error_message"] = (
                    f"Instance is in {current_state.value} state, cannot stop"
                )
                result["end_time"] = datetime.utcnow()
                return result

            if force:
                await self.ec2_client.terminate_instance(instance_id)
            else:
                await self.ec2_client.stop_instance(instance_id)

            target_state = (
                InstanceStatus.TERMINATED if force else InstanceStatus.STOPPED
            )
            success, final_state, error_msg = await self._wait_for_state(
                instance_id, region, [target_state], timeout_minutes
            )

            result["success"] = success
            result["end_time"] = datetime.utcnow()
            if not success:
                result["error_message"] = error_msg

        except Exception as e:
            self._handle_error(f"Failed to stop instance {instance_id}", e)
            result["error_message"] = str(e)
            result["end_time"] = datetime.utcnow()

        return result

    async def get_instance_state(self, instance_id: str, region: str) -> InstanceStatus:
        """Get the current state of an instance."""
        try:
            instance_info = await self.ec2_client.describe_instance(instance_id)
            if not instance_info:
                return InstanceStatus.UNKNOWN

            ec2_state = instance_info.get("State", {}).get("Name", "unknown")
            state_mapping = {
                "pending": InstanceStatus.PENDING,
                "running": InstanceStatus.RUNNING,
                "shutting-down": InstanceStatus.STOPPING,
                "terminated": InstanceStatus.TERMINATED,
                "stopping": InstanceStatus.STOPPING,
                "stopped": InstanceStatus.STOPPED,
            }
            return state_mapping.get(ec2_state, InstanceStatus.UNKNOWN)
        except Exception as e:
            self._handle_error(f"Failed to get instance state for {instance_id}", e)
            return InstanceStatus.UNKNOWN

    async def check_instance_reachability(
        self, instance_id: str, account_id: str, region: str
    ) -> bool:
        """Check if an instance is reachable."""
        try:
            state = await self.get_instance_state(instance_id, region)
            if state != InstanceStatus.RUNNING:
                return False

            try:
                await self.ssm_client.configure_for_account(account_id, region)
                ping_result = await self.ssm_client.send_command(
                    instance_id,
                    "AWS-RunShellScript",
                    {"commands": ['echo "ping"']},
                    timeout_seconds=30,
                )
                return ping_result.get("success", False)
            except Exception:
                return True
        except Exception as e:
            self._handle_error(f"Failed to check reachability for {instance_id}", e)
            return False

    async def validate_instance_health(self, instance: Instance) -> Dict[str, Any]:
        """Basic instance health validation."""
        health_result = {
            "instance_id": instance.instance_id,
            "overall_healthy": True,
            "checks": {},
            "issues": [],
        }

        try:
            current_state = await self.get_instance_state(
                instance.instance_id, instance.region
            )
            health_result["checks"]["instance_state"] = current_state.value

            if current_state not in [InstanceStatus.RUNNING, InstanceStatus.STOPPED]:
                health_result["overall_healthy"] = False
                health_result["issues"].append(
                    f"Instance is in {current_state.value} state"
                )

            if current_state == InstanceStatus.RUNNING:
                is_reachable = await self.check_instance_reachability(
                    instance.instance_id, instance.account_id, instance.region
                )
                health_result["checks"]["reachable"] = is_reachable
                if not is_reachable:
                    health_result["overall_healthy"] = False
                    health_result["issues"].append("Instance is not reachable")
        except Exception as e:
            health_result["overall_healthy"] = False
            health_result["issues"].append(f"Health check failed: {str(e)}")

        return health_result
