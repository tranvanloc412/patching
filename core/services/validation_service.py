import logging
import asyncio
from datetime import datetime
from typing import List, Dict, Any, Optional
from pathlib import Path

from core.models.instance import Instance, InstanceStatus
from core.models.config import WorkflowConfig, LandingZoneConfig
from core.interfaces.config_interface import IConfigService
from core.interfaces.server_manager_interface import IServerManagerService


class ValidationService:
    """Simplified validation service for basic configuration and instance validation."""

    def __init__(
        self,
        config_service: IConfigService,
        server_manager_service: IServerManagerService,
    ):
        self.config_service = config_service
        self.server_manager_service = server_manager_service
        self.logger = logging.getLogger(__name__)

    def _handle_error(self, message: str, exception: Exception = None) -> None:
        """Centralized error handling."""
        error_msg = f"{message}: {str(exception)}" if exception else message
        self.logger.error(error_msg)

    async def validate_workflow_config(self, config_file: str) -> Dict[str, Any]:
        """Validate workflow configuration file."""
        self.logger.info(f"Validating workflow configuration: {config_file}")

        validation_result = {
            "valid": True,
            "errors": [],
            "warnings": [],
            "config_file": config_file,
            "validation_time": datetime.utcnow().isoformat(),
        }

        try:
            if not Path(config_file).exists():
                validation_result["valid"] = False
                validation_result["errors"].append(
                    f"Configuration file not found: {config_file}"
                )
                return validation_result

            try:
                workflow_config = self.config_service.load_workflow_config(config_file)
                config_errors = workflow_config.validate()
                if config_errors:
                    validation_result["valid"] = False
                    validation_result["errors"].extend(config_errors)
            except Exception as e:
                validation_result["valid"] = False
                validation_result["errors"].append(
                    f"Failed to load configuration: {str(e)}"
                )
                return validation_result

            if not workflow_config.landing_zones:
                validation_result["valid"] = False
                validation_result["errors"].append("No landing zones configured")

            if not workflow_config.aws.region:
                validation_result["valid"] = False
                validation_result["errors"].append("AWS region not specified")

            if not workflow_config.aws.role_name:
                validation_result["valid"] = False
                validation_result["errors"].append("AWS role name not specified")

            self.logger.info(
                f"Configuration validation completed: {'PASSED' if validation_result['valid'] else 'FAILED'}"
            )

        except Exception as e:
            validation_result["valid"] = False
            validation_result["errors"].append(f"Unexpected validation error: {str(e)}")
            self._handle_error("Configuration validation failed", e)

        return validation_result

    async def validate_instance_health(self, instance: Instance) -> Dict[str, Any]:
        """Basic instance health validation."""
        self.logger.info(f"Validating health for instance: {instance.instance_id}")

        health_result = {
            "instance_id": instance.instance_id,
            "overall_healthy": True,
            "checks": {},
            "validation_time": datetime.utcnow().isoformat(),
        }

        try:
            status_check = self._validate_instance_status(instance)
            health_result["checks"]["instance_status"] = status_check
            if not status_check["healthy"]:
                health_result["overall_healthy"] = False

            connectivity_check = await self._validate_basic_connectivity(instance)
            health_result["checks"]["connectivity"] = connectivity_check
            if not connectivity_check["healthy"]:
                health_result["overall_healthy"] = False

            self.logger.info(
                f"Instance health validation completed: {'HEALTHY' if health_result['overall_healthy'] else 'UNHEALTHY'}"
            )

        except Exception as e:
            health_result["overall_healthy"] = False
            health_result["error"] = str(e)
            self._handle_error("Instance health validation failed", e)

        return health_result

    async def validate_multiple_instances(
        self, instances: List[Instance], max_concurrent: int = 5
    ) -> Dict[str, Any]:
        """Validate health for multiple instances concurrently."""
        self.logger.info(f"Validating health for {len(instances)} instances")

        validation_result = {
            "total_instances": len(instances),
            "healthy_instances": 0,
            "unhealthy_instances": 0,
            "instance_results": {},
            "validation_time": datetime.utcnow().isoformat(),
        }

        try:
            semaphore = asyncio.Semaphore(max_concurrent)

            async def validate_single_instance(instance: Instance):
                async with semaphore:
                    try:
                        result = await self.validate_instance_health(instance)
                        return instance.instance_id, result
                    except Exception as e:
                        self._handle_error(
                            f"Validation failed for {instance.instance_id}", e
                        )
                        return instance.instance_id, {
                            "instance_id": instance.instance_id,
                            "overall_healthy": False,
                            "error": str(e),
                            "validation_time": datetime.utcnow().isoformat(),
                        }

            tasks = [validate_single_instance(instance) for instance in instances]
            results = await asyncio.gather(*tasks, return_exceptions=True)

            for result in results:
                if isinstance(result, Exception):
                    self._handle_error("Instance validation error", result)
                    continue

                instance_id, health_result = result
                validation_result["instance_results"][instance_id] = health_result

                if health_result["overall_healthy"]:
                    validation_result["healthy_instances"] += 1
                else:
                    validation_result["unhealthy_instances"] += 1

            self.logger.info(
                f"Multiple instance validation completed: "
                f"{validation_result['healthy_instances']} healthy, "
                f"{validation_result['unhealthy_instances']} unhealthy"
            )

        except Exception as e:
            self._handle_error("Multiple instance validation failed", e)
            validation_result["error"] = str(e)

        return validation_result

    def _validate_instance_status(self, instance: Instance) -> Dict[str, Any]:
        """Validate basic instance status."""
        status_result = {
            "healthy": True,
            "status": instance.status.value if instance.status else "unknown",
            "issues": [],
        }

        if instance.status in [InstanceStatus.TERMINATED, InstanceStatus.TERMINATING]:
            status_result["healthy"] = False
            status_result["issues"].append(f"Instance is {instance.status.value}")

        if instance.status == InstanceStatus.PENDING:
            status_result["healthy"] = False
            status_result["issues"].append("Instance is still pending")

        return status_result

    async def _validate_basic_connectivity(self, instance: Instance) -> Dict[str, Any]:
        """Basic connectivity validation."""
        connectivity_result = {"healthy": True, "reachable": False, "issues": []}

        try:
            is_reachable = (
                await self.server_manager_service.check_instance_reachability(
                    instance.instance_id, instance.account_id, instance.region
                )
            )

            connectivity_result["reachable"] = is_reachable

            if not is_reachable:
                connectivity_result["healthy"] = False
                connectivity_result["issues"].append("Instance is not reachable")

        except Exception as e:
            connectivity_result["healthy"] = False
            connectivity_result["issues"].append(f"Connectivity check failed: {str(e)}")

        return connectivity_result
