"""Server manager service implementation."""

import asyncio
import logging
from datetime import datetime, timedelta
from typing import List, Dict, Any, Optional, Set

from core.interfaces.server_manager_interface import IServerManagerService
from core.interfaces.config_interface import IConfigService
from core.models.instance import Instance, InstanceStatus
from core.models.server_operation import (
    ServerOperation, OperationType, OperationStatus, OperationPriority,
    OperationResult, OperationContext
)
from infrastructure.aws.ec2_client import EC2Client
from infrastructure.aws.ssm_client import SSMClient


class ServerManagerService(IServerManagerService):
    """Implementation of server manager service."""
    
    def __init__(self, config_service: IConfigService, ec2_client: EC2Client, ssm_client: SSMClient):
        self.config_service = config_service
        self.ec2_client = ec2_client
        self.ssm_client = ssm_client
        self.logger = logging.getLogger(__name__)
        self._active_operations: Dict[str, ServerOperation] = {}
        self._operation_history: List[ServerOperation] = []
    
    async def start_instance(self, instance: Instance, wait_for_ready: bool = True) -> OperationResult:
        """Start a single EC2 instance."""
        self.logger.info(f"Starting instance {instance.instance_id}")
        
        operation = ServerOperation(
            instance_id=instance.instance_id,
            operation_type=OperationType.START,
            priority=OperationPriority.NORMAL,
            context=OperationContext(
                region=instance.region,
                account_id=instance.account_id,
                landing_zone=instance.landing_zone,
                platform=instance.platform.value,
                wait_for_ready=wait_for_ready
            )
        )
        
        return await self._execute_operation(operation)
    
    async def stop_instance(self, instance: Instance, force: bool = False) -> OperationResult:
        """Stop a single EC2 instance."""
        self.logger.info(f"Stopping instance {instance.instance_id} (force={force})")
        
        operation = ServerOperation(
            instance_id=instance.instance_id,
            operation_type=OperationType.STOP,
            priority=OperationPriority.NORMAL,
            context=OperationContext(
                region=instance.region,
                account_id=instance.account_id,
                landing_zone=instance.landing_zone,
                platform=instance.platform.value,
                force=force
            )
        )
        
        return await self._execute_operation(operation)
    
    async def restart_instance(self, instance: Instance, wait_for_ready: bool = True) -> OperationResult:
        """Restart a single EC2 instance."""
        self.logger.info(f"Restarting instance {instance.instance_id}")
        
        operation = ServerOperation(
            instance_id=instance.instance_id,
            operation_type=OperationType.RESTART,
            priority=OperationPriority.NORMAL,
            context=OperationContext(
                region=instance.region,
                account_id=instance.account_id,
                landing_zone=instance.landing_zone,
                platform=instance.platform.value,
                wait_for_ready=wait_for_ready
            )
        )
        
        return await self._execute_operation(operation)
    
    async def start_multiple_instances(self, instances: List[Instance],
                                      max_concurrent: int = 10,
                                      wait_for_ready: bool = True) -> List[OperationResult]:
        """Start multiple instances concurrently."""
        self.logger.info(f"Starting {len(instances)} instances")
        
        # Filter instances that can be started
        startable_instances = [
            inst for inst in instances 
            if inst.status in [InstanceStatus.STOPPED, InstanceStatus.STOPPING]
        ]
        
        if not startable_instances:
            self.logger.info("No instances in startable state")
            return []
        
        self.logger.info(f"Filtered to {len(startable_instances)} startable instances")
        
        # Create semaphore to limit concurrent operations
        semaphore = asyncio.Semaphore(max_concurrent)
        
        async def start_with_semaphore(instance: Instance) -> OperationResult:
            async with semaphore:
                return await self.start_instance(instance, wait_for_ready)
        
        # Execute operations concurrently
        tasks = [start_with_semaphore(instance) for instance in startable_instances]
        results = await asyncio.gather(*tasks, return_exceptions=True)
        
        # Process results
        operation_results = []
        for i, result in enumerate(results):
            if isinstance(result, Exception):
                instance = startable_instances[i]
                self.logger.error(f"Start operation failed for instance {instance.instance_id}: {str(result)}")
                
                # Create a failed operation result
                failed_result = OperationResult(
                    operation_id=f"start_{instance.instance_id}_{datetime.utcnow().isoformat()}",
                    instance_id=instance.instance_id,
                    operation_type=OperationType.START,
                    status=OperationStatus.FAILED,
                    error_message=str(result)
                )
                operation_results.append(failed_result)
            else:
                operation_results.append(result)
        
        successful_ops = len([r for r in operation_results if r.status == OperationStatus.COMPLETED])
        self.logger.info(f"Start operations complete: {successful_ops}/{len(operation_results)} successful")
        
        return operation_results
    
    async def stop_multiple_instances(self, instances: List[Instance],
                                     max_concurrent: int = 10,
                                     force: bool = False) -> List[OperationResult]:
        """Stop multiple instances concurrently."""
        self.logger.info(f"Stopping {len(instances)} instances (force={force})")
        
        # Filter instances that can be stopped
        stoppable_instances = [
            inst for inst in instances 
            if inst.status in [InstanceStatus.RUNNING, InstanceStatus.PENDING]
        ]
        
        if not stoppable_instances:
            self.logger.info("No instances in stoppable state")
            return []
        
        self.logger.info(f"Filtered to {len(stoppable_instances)} stoppable instances")
        
        # Create semaphore to limit concurrent operations
        semaphore = asyncio.Semaphore(max_concurrent)
        
        async def stop_with_semaphore(instance: Instance) -> OperationResult:
            async with semaphore:
                return await self.stop_instance(instance, force)
        
        # Execute operations concurrently
        tasks = [stop_with_semaphore(instance) for instance in stoppable_instances]
        results = await asyncio.gather(*tasks, return_exceptions=True)
        
        # Process results
        operation_results = []
        for i, result in enumerate(results):
            if isinstance(result, Exception):
                instance = stoppable_instances[i]
                self.logger.error(f"Stop operation failed for instance {instance.instance_id}: {str(result)}")
                
                # Create a failed operation result
                failed_result = OperationResult(
                    operation_id=f"stop_{instance.instance_id}_{datetime.utcnow().isoformat()}",
                    instance_id=instance.instance_id,
                    operation_type=OperationType.STOP,
                    status=OperationStatus.FAILED,
                    error_message=str(result)
                )
                operation_results.append(failed_result)
            else:
                operation_results.append(result)
        
        successful_ops = len([r for r in operation_results if r.status == OperationStatus.COMPLETED])
        self.logger.info(f"Stop operations complete: {successful_ops}/{len(operation_results)} successful")
        
        return operation_results
    
    async def get_instance_state(self, instance_id: str, region: str) -> InstanceStatus:
        """Get the current state of an instance."""
        try:
            # Configure EC2 client for the region
            await self.ec2_client.configure_for_region(region)
            
            # Get instance information
            instance_info = await self.ec2_client.describe_instance(instance_id)
            
            if not instance_info:
                return InstanceStatus.UNKNOWN
            
            # Map AWS state to our enum
            aws_state = instance_info.get('State', {}).get('Name', 'unknown')
            return self._map_aws_state_to_status(aws_state)
            
        except Exception as e:
            self.logger.warning(f"Error getting state for instance {instance_id}: {str(e)}")
            return InstanceStatus.UNKNOWN
    
    async def validate_instance_health(self, instance: Instance) -> Dict[str, Any]:
        """Validate the health of an instance."""
        self.logger.debug(f"Validating health for instance {instance.instance_id}")
        
        health_check = {
            'instance_id': instance.instance_id,
            'timestamp': datetime.utcnow().isoformat(),
            'overall_healthy': False,
            'checks': {}
        }
        
        try:
            # Configure clients
            await self.ec2_client.configure_for_region(instance.region)
            await self.ssm_client.configure_for_region(instance.region)
            
            # Check EC2 instance status
            ec2_health = await self._check_ec2_health(instance)
            health_check['checks']['ec2'] = ec2_health
            
            # Check SSM connectivity if applicable
            if instance.ssm_info and instance.ssm_info.agent_status == 'Online':
                ssm_health = await self._check_ssm_health(instance)
                health_check['checks']['ssm'] = ssm_health
            else:
                health_check['checks']['ssm'] = {
                    'healthy': False,
                    'reason': 'SSM agent not online',
                    'details': {}
                }
            
            # Check system status
            system_health = await self._check_system_status(instance)
            health_check['checks']['system'] = system_health
            
            # Determine overall health
            all_checks_healthy = all(
                check.get('healthy', False) 
                for check in health_check['checks'].values()
            )
            
            health_check['overall_healthy'] = all_checks_healthy
            
            if all_checks_healthy:
                self.logger.info(f"Instance {instance.instance_id} passed all health checks")
            else:
                failed_checks = [
                    check_name for check_name, check_result in health_check['checks'].items()
                    if not check_result.get('healthy', False)
                ]
                self.logger.warning(f"Instance {instance.instance_id} failed health checks: {failed_checks}")
            
        except Exception as e:
            self.logger.error(f"Error validating health for instance {instance.instance_id}: {str(e)}")
            health_check['checks']['validation_error'] = {
                'healthy': False,
                'reason': f"Health validation failed: {str(e)}",
                'details': {}
            }
        
        return health_check
    
    async def wait_for_state(self, instance_id: str, region: str,
                           target_state: InstanceStatus,
                           timeout_minutes: int = 10) -> bool:
        """Wait for an instance to reach a specific state."""
        self.logger.info(f"Waiting for instance {instance_id} to reach state {target_state.value}")
        
        timeout_time = datetime.utcnow() + timedelta(minutes=timeout_minutes)
        check_interval = 15  # seconds
        
        while datetime.utcnow() < timeout_time:
            try:
                current_state = await self.get_instance_state(instance_id, region)
                
                if current_state == target_state:
                    self.logger.info(f"Instance {instance_id} reached target state {target_state.value}")
                    return True
                
                # Check for error states
                if current_state in [InstanceStatus.TERMINATED, InstanceStatus.UNKNOWN]:
                    self.logger.error(f"Instance {instance_id} entered error state: {current_state.value}")
                    return False
                
                self.logger.debug(f"Instance {instance_id} current state: {current_state.value}, waiting...")
                await asyncio.sleep(check_interval)
                
            except Exception as e:
                self.logger.warning(f"Error checking instance state: {str(e)}")
                await asyncio.sleep(check_interval)
        
        # Timeout reached
        self.logger.error(f"Timeout waiting for instance {instance_id} to reach state {target_state.value}")
        return False
    
    async def get_operation_status(self, operation_id: str) -> Optional[ServerOperation]:
        """Get the status of a specific operation."""
        return self._active_operations.get(operation_id)
    
    async def cancel_operation(self, operation_id: str) -> bool:
        """Cancel a running operation."""
        operation = self._active_operations.get(operation_id)
        if operation and operation.status == OperationStatus.RUNNING:
            operation.mark_cancelled("Operation cancelled by user")
            self.logger.info(f"Cancelled operation {operation_id}")
            return True
        return False
    
    async def get_active_operations(self) -> List[ServerOperation]:
        """Get all currently active operations."""
        return list(self._active_operations.values())
    
    async def _execute_operation(self, operation: ServerOperation) -> OperationResult:
        """Execute a server operation."""
        try:
            # Track the operation
            self._active_operations[operation.operation_id] = operation
            operation.mark_started()
            
            # Configure EC2 client
            await self.ec2_client.configure_for_region(operation.context.region)
            
            # Execute based on operation type
            if operation.operation_type == OperationType.START:
                result = await self._execute_start_operation(operation)
            elif operation.operation_type == OperationType.STOP:
                result = await self._execute_stop_operation(operation)
            elif operation.operation_type == OperationType.RESTART:
                result = await self._execute_restart_operation(operation)
            else:
                raise ValueError(f"Unsupported operation type: {operation.operation_type}")
            
            # Mark operation as completed
            operation.mark_completed(result.to_dict())
            
            return result
            
        except Exception as e:
            # Mark operation as failed
            operation.mark_failed(str(e))
            
            # Create failed result
            result = OperationResult(
                operation_id=operation.operation_id,
                instance_id=operation.instance_id,
                operation_type=operation.operation_type,
                status=OperationStatus.FAILED,
                error_message=str(e)
            )
            
            return result
            
        finally:
            # Move to history and remove from active
            self._operation_history.append(operation)
            self._active_operations.pop(operation.operation_id, None)
    
    async def _execute_start_operation(self, operation: ServerOperation) -> OperationResult:
        """Execute a start operation."""
        instance_id = operation.instance_id
        
        # Start the instance
        response = await self.ec2_client.start_instances([instance_id])
        
        result = OperationResult(
            operation_id=operation.operation_id,
            instance_id=instance_id,
            operation_type=OperationType.START,
            status=OperationStatus.COMPLETED,
            details={'aws_response': response}
        )
        
        # Wait for ready state if requested
        if operation.context.wait_for_ready:
            self.logger.info(f"Waiting for instance {instance_id} to be ready")
            
            # Wait for running state
            if await self.wait_for_state(instance_id, operation.context.region, InstanceStatus.RUNNING):
                # Additional wait for system checks
                await asyncio.sleep(30)  # Allow time for system initialization
                result.details['ready'] = True
            else:
                result.status = OperationStatus.FAILED
                result.error_message = "Instance failed to reach running state"
        
        return result
    
    async def _execute_stop_operation(self, operation: ServerOperation) -> OperationResult:
        """Execute a stop operation."""
        instance_id = operation.instance_id
        force = operation.context.force
        
        # Stop the instance
        if force:
            response = await self.ec2_client.stop_instances([instance_id], force=True)
        else:
            response = await self.ec2_client.stop_instances([instance_id])
        
        result = OperationResult(
            operation_id=operation.operation_id,
            instance_id=instance_id,
            operation_type=OperationType.STOP,
            status=OperationStatus.COMPLETED,
            details={'aws_response': response, 'force': force}
        )
        
        return result
    
    async def _execute_restart_operation(self, operation: ServerOperation) -> OperationResult:
        """Execute a restart operation."""
        instance_id = operation.instance_id
        
        # Reboot the instance
        response = await self.ec2_client.reboot_instances([instance_id])
        
        result = OperationResult(
            operation_id=operation.operation_id,
            instance_id=instance_id,
            operation_type=OperationType.RESTART,
            status=OperationStatus.COMPLETED,
            details={'aws_response': response}
        )
        
        # Wait for ready state if requested
        if operation.context.wait_for_ready:
            self.logger.info(f"Waiting for instance {instance_id} to be ready after restart")
            
            # Wait a bit for the restart to begin
            await asyncio.sleep(10)
            
            # Wait for running state
            if await self.wait_for_state(instance_id, operation.context.region, InstanceStatus.RUNNING):
                # Additional wait for system checks
                await asyncio.sleep(30)  # Allow time for system initialization
                result.details['ready'] = True
            else:
                result.status = OperationStatus.FAILED
                result.error_message = "Instance failed to be ready after restart"
        
        return result
    
    async def _check_ec2_health(self, instance: Instance) -> Dict[str, Any]:
        """Check EC2 instance health."""
        try:
            # Get instance status
            status_info = await self.ec2_client.describe_instance_status(instance.instance_id)
            
            if not status_info:
                return {
                    'healthy': False,
                    'reason': 'Instance status not available',
                    'details': {}
                }
            
            instance_status = status_info.get('InstanceStatus', {}).get('Status', 'unknown')
            system_status = status_info.get('SystemStatus', {}).get('Status', 'unknown')
            
            healthy = instance_status == 'ok' and system_status == 'ok'
            
            return {
                'healthy': healthy,
                'reason': 'All status checks passed' if healthy else f"Status checks failed: instance={instance_status}, system={system_status}",
                'details': {
                    'instance_status': instance_status,
                    'system_status': system_status,
                    'status_info': status_info
                }
            }
            
        except Exception as e:
            return {
                'healthy': False,
                'reason': f"EC2 health check failed: {str(e)}",
                'details': {}
            }
    
    async def _check_ssm_health(self, instance: Instance) -> Dict[str, Any]:
        """Check SSM connectivity health."""
        try:
            # Test SSM connectivity with a simple command
            command_result = await self.ssm_client.send_command(
                instance_ids=[instance.instance_id],
                document_name="AWS-RunShellScript",
                parameters={'commands': ['echo "SSM connectivity test"']},
                timeout_seconds=30
            )
            
            if command_result and command_result.get('status') == 'Success':
                return {
                    'healthy': True,
                    'reason': 'SSM connectivity test passed',
                    'details': {
                        'command_id': command_result.get('command_id'),
                        'response_time': command_result.get('response_time')
                    }
                }
            else:
                return {
                    'healthy': False,
                    'reason': 'SSM connectivity test failed',
                    'details': command_result or {}
                }
                
        except Exception as e:
            return {
                'healthy': False,
                'reason': f"SSM health check failed: {str(e)}",
                'details': {}
            }
    
    async def _check_system_status(self, instance: Instance) -> Dict[str, Any]:
        """Check system-level health."""
        try:
            # Get detailed instance information
            instance_info = await self.ec2_client.describe_instance(instance.instance_id)
            
            if not instance_info:
                return {
                    'healthy': False,
                    'reason': 'Instance information not available',
                    'details': {}
                }
            
            state = instance_info.get('State', {}).get('Name', 'unknown')
            
            # Check if instance is in a healthy state
            healthy_states = ['running', 'stopped']
            healthy = state in healthy_states
            
            details = {
                'state': state,
                'launch_time': instance_info.get('LaunchTime'),
                'instance_type': instance_info.get('InstanceType'),
                'vpc_id': instance_info.get('VpcId'),
                'subnet_id': instance_info.get('SubnetId')
            }
            
            return {
                'healthy': healthy,
                'reason': f"Instance state is {state}" if healthy else f"Instance in unhealthy state: {state}",
                'details': details
            }
            
        except Exception as e:
            return {
                'healthy': False,
                'reason': f"System status check failed: {str(e)}",
                'details': {}
            }
    
    def _map_aws_state_to_status(self, aws_state: str) -> InstanceStatus:
        """Map AWS instance state to our InstanceStatus enum."""
        state_mapping = {
            'pending': InstanceStatus.PENDING,
            'running': InstanceStatus.RUNNING,
            'shutting-down': InstanceStatus.STOPPING,
            'terminated': InstanceStatus.TERMINATED,
            'stopping': InstanceStatus.STOPPING,
            'stopped': InstanceStatus.STOPPED
        }
        
        return state_mapping.get(aws_state.lower(), InstanceStatus.UNKNOWN)