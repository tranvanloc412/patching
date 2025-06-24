"""AWS SSM client for Systems Manager operations."""

import asyncio
from typing import List, Dict, Any, Optional
from datetime import datetime

from botocore.exceptions import ClientError
from .session_manager import AWSSessionManager
from core.models.instance import SSMStatus
from core.utils.logger import get_infrastructure_logger


class SSMClient:
    """AWS SSM client wrapper for Systems Manager operations."""

    def __init__(
        self,
        region: str,
        account_id: Optional[str] = None,
        role_name: Optional[str] = None,
        run_mode: Optional[str] = None,
    ):
        self.region = region
        self.logger = get_infrastructure_logger(__name__)
        self.session_manager = AWSSessionManager(region=region)

        session = self.session_manager.get_session(
            account_id=account_id, role_name=role_name, run_mode=run_mode
        )
        self._client = session.client("ssm", region_name=region)

    def _handle_error(self, operation: str, error: Exception) -> None:
        """Centralized error handling and logging."""
        if isinstance(error, ClientError):
            error_code = error.response["Error"]["Code"]
            self.logger.error(f"{operation} failed: {error_code}")
        else:
            self.logger.error(f"{operation} failed: {str(error)}")
        raise error

    async def describe_instance_information(
        self,
        instance_ids: Optional[List[str]] = None,
        filters: Optional[List[Dict[str, Any]]] = None,
        max_results: Optional[int] = None,
    ) -> List[Dict[str, Any]]:
        """Get SSM instance information."""
        try:
            params = {}

            if instance_ids:
                params["Filters"] = [{"Key": "InstanceIds", "Values": instance_ids}]

            if filters:
                if "Filters" in params:
                    params["Filters"].extend(filters)
                else:
                    params["Filters"] = filters

            if max_results:
                params["MaxResults"] = max_results

            instances = []
            paginator = self._client.get_paginator("describe_instance_information")

            for page in paginator.paginate(**params):
                instances.extend(page["InstanceInformationList"])

            return instances

        except Exception as e:
            self._handle_error("describe_instance_information", e)

    async def get_managed_instances(self) -> List[Dict[str, Any]]:
        """Get all SSM managed instances."""
        try:
            return await self.describe_instance_information()
        except Exception as e:
            self._handle_error("get_managed_instances", e)

    async def get_instance_patch_state(
        self, instance_ids: List[str]
    ) -> List[Dict[str, Any]]:
        """Get patch state for instances."""
        try:
            batch_size = 50
            all_patch_states = []

            for i in range(0, len(instance_ids), batch_size):
                batch = instance_ids[i : i + batch_size]
                response = self._client.describe_instance_patch_states(
                    InstanceIds=batch
                )
                all_patch_states.extend(response["InstancePatchStates"])

            return all_patch_states

        except Exception as e:
            self._handle_error("get_instance_patch_state", e)

    async def get_patch_summary_for_instance(self, instance_id: str) -> Dict[str, Any]:
        """Get patch summary for a single instance."""
        try:
            response = self._client.describe_instance_patch_states_for_patch_group(
                PatchGroup="*", Filters=[{"Key": "InstanceId", "Values": [instance_id]}]
            )

            patch_states = response["InstancePatchStates"]
            if patch_states:
                return patch_states[0]

            # Try alternative method
            response = self._client.describe_instance_patch_states(
                InstanceIds=[instance_id]
            )

            return (
                response["InstancePatchStates"][0]
                if response["InstancePatchStates"]
                else {}
            )

        except ClientError as e:
            if e.response["Error"]["Code"] == "InvalidInstanceId":
                return {}
            self._handle_error("get_patch_summary_for_instance", e)
        except Exception as e:
            self._handle_error("get_patch_summary_for_instance", e)

    async def send_command(
        self,
        instance_ids: List[str],
        document_name: str,
        parameters: Optional[Dict[str, List[str]]] = None,
        timeout_seconds: int = 3600,
        comment: Optional[str] = None,
    ) -> Dict[str, Any]:
        """Send a command to instances via SSM."""
        try:
            params = {
                "InstanceIds": instance_ids,
                "DocumentName": document_name,
                "TimeoutSeconds": timeout_seconds,
            }

            if parameters:
                params["Parameters"] = parameters

            if comment:
                params["Comment"] = comment

            response = self._client.send_command(**params)
            command = response["Command"]

            return {
                "command_id": command["CommandId"],
                "command": command,
                "timestamp": datetime.utcnow().isoformat(),
            }

        except Exception as e:
            self._handle_error("send_command", e)

    async def get_command_invocation(
        self, command_id: str, instance_id: str
    ) -> Dict[str, Any]:
        """Get command invocation details for a specific instance."""
        try:
            response = self._client.get_command_invocation(
                CommandId=command_id, InstanceId=instance_id
            )

            return {
                "command_id": command_id,
                "instance_id": instance_id,
                "status": response["Status"],
                "status_details": response.get("StatusDetails", ""),
                "standard_output": response.get("StandardOutputContent", ""),
                "standard_error": response.get("StandardErrorContent", ""),
                "response_code": response.get("ResponseCode", -1),
                "execution_start_time": response.get("ExecutionStartDateTime"),
                "execution_end_time": response.get("ExecutionEndDateTime"),
            }

        except ClientError as e:
            if e.response["Error"]["Code"] == "InvocationDoesNotExist":
                return {}
            self._handle_error("get_command_invocation", e)
        except Exception as e:
            self._handle_error("get_command_invocation", e)

    async def list_command_invocations(
        self,
        command_id: Optional[str] = None,
        instance_id: Optional[str] = None,
        filters: Optional[List[Dict[str, Any]]] = None,
    ) -> List[Dict[str, Any]]:
        """List command invocations."""
        try:
            params = {}

            if command_id:
                params["CommandId"] = command_id

            if instance_id:
                params["InstanceId"] = instance_id

            if filters:
                params["Filters"] = filters

            invocations = []
            paginator = self._client.get_paginator("list_command_invocations")

            for page in paginator.paginate(**params):
                invocations.extend(page["CommandInvocations"])

            return invocations

        except Exception as e:
            self._handle_error("list_command_invocations", e)

    async def wait_for_command_completion(
        self,
        command_id: str,
        instance_ids: List[str],
        max_wait_time: int = 3600,
        poll_interval: int = 30,
    ) -> Dict[str, Any]:
        """Wait for command to complete on all instances."""
        try:
            start_time = datetime.utcnow()
            completed_instances = set()
            failed_instances = set()
            results = {}

            while (datetime.utcnow() - start_time).total_seconds() < max_wait_time:
                for instance_id in instance_ids:
                    if (
                        instance_id in completed_instances
                        or instance_id in failed_instances
                    ):
                        continue

                    try:
                        invocation = await self.get_command_invocation(
                            command_id, instance_id
                        )

                        if invocation:
                            status = invocation["status"]
                            results[instance_id] = invocation

                            if status in ["Success", "Failed", "Cancelled", "TimedOut"]:
                                if status == "Success":
                                    completed_instances.add(instance_id)
                                else:
                                    failed_instances.add(instance_id)

                    except Exception:
                        pass  # Continue checking other instances

                if len(completed_instances) + len(failed_instances) >= len(
                    instance_ids
                ):
                    break

                await asyncio.sleep(poll_interval)

            result = {
                "command_id": command_id,
                "completed_instances": list(completed_instances),
                "failed_instances": list(failed_instances),
                "results": results,
                "total_instances": len(instance_ids),
                "success_count": len(completed_instances),
                "failure_count": len(failed_instances),
                "timestamp": datetime.utcnow().isoformat(),
            }

            total_done = len(completed_instances) + len(failed_instances)
            if total_done < len(instance_ids):
                result["timed_out"] = True
                result["pending_instances"] = [
                    iid
                    for iid in instance_ids
                    if iid not in completed_instances and iid not in failed_instances
                ]

            return result

        except Exception as e:
            self._handle_error("wait_for_command_completion", e)

    async def get_patch_baseline_for_instance(self, instance_id: str) -> Dict[str, Any]:
        """Get patch baseline for an instance."""
        try:
            response = self._client.get_patch_baseline_for_patch_group(
                PatchGroup=instance_id
            )

            return {
                "baseline_id": response.get("BaselineId"),
                "patch_group": response.get("PatchGroup"),
                "operating_system": response.get("OperatingSystem"),
            }

        except ClientError as e:
            if e.response["Error"]["Code"] == "DoesNotExistException":
                return {}
            self._handle_error("get_patch_baseline_for_instance", e)
        except Exception as e:
            self._handle_error("get_patch_baseline_for_instance", e)

    async def describe_patch_baselines(
        self, filters: Optional[List[Dict[str, Any]]] = None
    ) -> List[Dict[str, Any]]:
        """Describe patch baselines."""
        try:
            params = {}

            if filters:
                params["Filters"] = filters

            baselines = []
            paginator = self._client.get_paginator("describe_patch_baselines")

            for page in paginator.paginate(**params):
                baselines.extend(page["BaselineIdentities"])

            return baselines

        except Exception as e:
            self._handle_error("describe_patch_baselines", e)

    async def get_maintenance_window_execution(
        self, window_execution_id: str
    ) -> Dict[str, Any]:
        """Get maintenance window execution details."""
        try:
            response = self._client.get_maintenance_window_execution(
                WindowExecutionId=window_execution_id
            )

            return {
                "window_execution_id": window_execution_id,
                "task_ids": response.get("TaskIds", []),
                "status": response.get("Status"),
                "status_details": response.get("StatusDetails"),
                "start_time": response.get("StartTime"),
                "end_time": response.get("EndTime"),
            }

        except ClientError as e:
            if e.response["Error"]["Code"] == "DoesNotExistException":
                return {}
            self._handle_error("get_maintenance_window_execution", e)
        except Exception as e:
            self._handle_error("get_maintenance_window_execution", e)

    async def ping_instance(self, instance_id: str) -> Dict[str, Any]:
        """Ping an instance to check SSM connectivity."""
        try:
            command_result = await self.send_command(
                instance_ids=[instance_id],
                document_name="AWS-RunShellScript",
                parameters={"commands": ['echo "SSM ping successful"']},
                timeout_seconds=60,
                comment="SSM connectivity test",
            )

            command_id = command_result["command_id"]

            wait_result = await self.wait_for_command_completion(
                command_id=command_id,
                instance_ids=[instance_id],
                max_wait_time=120,
                poll_interval=5,
            )

            success = instance_id in wait_result["completed_instances"]

            return {
                "instance_id": instance_id,
                "ssm_reachable": success,
                "command_id": command_id,
                "result": wait_result.get("results", {}).get(instance_id, {}),
                "timestamp": datetime.utcnow().isoformat(),
            }

        except Exception as e:
            return {
                "instance_id": instance_id,
                "ssm_reachable": False,
                "error": str(e),
                "timestamp": datetime.utcnow().isoformat(),
            }

    def _map_ssm_status(self, ping_status: str) -> SSMStatus:
        """Map SSM ping status to our SSMStatus enum."""
        status_mapping = {
            "Online": SSMStatus.ONLINE,
            "Connection Lost": SSMStatus.CONNECTION_LOST,
            "Inactive": SSMStatus.INACTIVE,
            "Stopped": SSMStatus.STOPPED,
        }

        return status_mapping.get(ping_status, SSMStatus.UNKNOWN)

    async def get_parameters(
        self, names: List[str], with_decryption: bool = False
    ) -> Dict[str, Any]:
        """Get SSM parameters."""
        try:
            batch_size = 10
            all_parameters = []
            invalid_parameters = []

            for i in range(0, len(names), batch_size):
                batch = names[i : i + batch_size]

                try:
                    response = self._client.get_parameters(
                        Names=batch, WithDecryption=with_decryption
                    )

                    all_parameters.extend(response["Parameters"])
                    invalid_parameters.extend(response.get("InvalidParameters", []))

                except ClientError:
                    invalid_parameters.extend(batch)

            return {
                "parameters": all_parameters,
                "invalid_parameters": invalid_parameters,
            }

        except Exception as e:
            self._handle_error("get_parameters", e)
