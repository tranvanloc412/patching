"""AWS SSM client for Systems Manager operations."""

import logging
import asyncio
from typing import List, Dict, Any, Optional, Tuple
from datetime import datetime, timedelta

from botocore.exceptions import ClientError
from .session_manager import AWSSessionManager
from core.models.instance import SSMStatus


class SSMClient:
    """AWS SSM client wrapper for Systems Manager operations."""
    
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
        
        # Get SSM client
        self._client = self.session_manager.get_client(
            'ssm',
            account_id=account_id,
            role_name=role_name,
            external_id=external_id,
            region=region
        )
    
    async def describe_instance_information(
        self,
        instance_ids: Optional[List[str]] = None,
        filters: Optional[List[Dict[str, Any]]] = None,
        max_results: Optional[int] = None
    ) -> List[Dict[str, Any]]:
        """Get SSM instance information."""
        try:
            self.logger.debug(f"Getting SSM instance information for {len(instance_ids) if instance_ids else 'all'} instances")
            
            params = {}
            
            if instance_ids:
                # Convert to SSM instance ID format if needed
                ssm_filters = [{
                    'Key': 'InstanceIds',
                    'Values': instance_ids
                }]
                params['Filters'] = ssm_filters
            
            if filters:
                if 'Filters' in params:
                    params['Filters'].extend(filters)
                else:
                    params['Filters'] = filters
            
            if max_results:
                params['MaxResults'] = max_results
            
            # Get instance information
            instances = []
            paginator = self._client.get_paginator('describe_instance_information')
            
            for page in paginator.paginate(**params):
                instances.extend(page['InstanceInformationList'])
            
            self.logger.debug(f"Found {len(instances)} SSM-managed instances")
            return instances
            
        except ClientError as e:
            self.logger.error(f"Failed to describe SSM instance information: {str(e)}")
            raise
        except Exception as e:
            self.logger.error(f"Unexpected error describing SSM instance information: {str(e)}")
            raise
    
    async def get_instance_patch_state(
        self,
        instance_ids: List[str]
    ) -> List[Dict[str, Any]]:
        """Get patch state for instances."""
        try:
            self.logger.debug(f"Getting patch state for {len(instance_ids)} instances")
            
            # Get patch states in batches (SSM has limits)
            batch_size = 50
            all_patch_states = []
            
            for i in range(0, len(instance_ids), batch_size):
                batch = instance_ids[i:i + batch_size]
                
                response = self._client.describe_instance_patch_states(
                    InstanceIds=batch
                )
                
                all_patch_states.extend(response['InstancePatchStates'])
            
            self.logger.debug(f"Retrieved patch state for {len(all_patch_states)} instances")
            return all_patch_states
            
        except ClientError as e:
            error_code = e.response['Error']['Code']
            
            if error_code == 'InvalidInstanceId':
                self.logger.error(f"One or more instance IDs not found in SSM: {instance_ids}")
            else:
                self.logger.error(f"Error getting patch state: {error_code}")
            
            raise
        except Exception as e:
            self.logger.error(f"Unexpected error getting patch state: {str(e)}")
            raise
    
    async def get_patch_summary_for_instance(
        self,
        instance_id: str
    ) -> Dict[str, Any]:
        """Get patch summary for a single instance."""
        try:
            self.logger.debug(f"Getting patch summary for instance {instance_id}")
            
            response = self._client.describe_instance_patch_states_for_patch_group(
                PatchGroup='*',
                Filters=[
                    {
                        'Key': 'InstanceId',
                        'Values': [instance_id]
                    }
                ]
            )
            
            patch_states = response['InstancePatchStates']
            
            if patch_states:
                return patch_states[0]
            else:
                # Try alternative method
                response = self._client.describe_instance_patch_states(
                    InstanceIds=[instance_id]
                )
                
                if response['InstancePatchStates']:
                    return response['InstancePatchStates'][0]
                else:
                    return {}
            
        except ClientError as e:
            error_code = e.response['Error']['Code']
            
            if error_code == 'InvalidInstanceId':
                self.logger.warning(f"Instance {instance_id} not found in SSM")
                return {}
            else:
                self.logger.error(f"Error getting patch summary: {error_code}")
                raise
        except Exception as e:
            self.logger.error(f"Unexpected error getting patch summary: {str(e)}")
            raise
    
    async def send_command(
        self,
        instance_ids: List[str],
        document_name: str,
        parameters: Optional[Dict[str, List[str]]] = None,
        timeout_seconds: int = 3600,
        comment: Optional[str] = None
    ) -> Dict[str, Any]:
        """Send a command to instances via SSM."""
        try:
            self.logger.info(f"Sending command '{document_name}' to {len(instance_ids)} instances")
            
            params = {
                'InstanceIds': instance_ids,
                'DocumentName': document_name,
                'TimeoutSeconds': timeout_seconds
            }
            
            if parameters:
                params['Parameters'] = parameters
            
            if comment:
                params['Comment'] = comment
            
            response = self._client.send_command(**params)
            
            command = response['Command']
            command_id = command['CommandId']
            
            result = {
                'command_id': command_id,
                'command': command,
                'timestamp': datetime.utcnow().isoformat()
            }
            
            self.logger.info(f"Command sent successfully: {command_id}")
            return result
            
        except ClientError as e:
            error_code = e.response['Error']['Code']
            
            if error_code == 'InvalidInstanceId':
                self.logger.error(f"One or more instance IDs not found in SSM: {instance_ids}")
            elif error_code == 'InvalidDocument':
                self.logger.error(f"Invalid document name: {document_name}")
            else:
                self.logger.error(f"Error sending command: {error_code}")
            
            raise
        except Exception as e:
            self.logger.error(f"Unexpected error sending command: {str(e)}")
            raise
    
    async def get_command_invocation(
        self,
        command_id: str,
        instance_id: str
    ) -> Dict[str, Any]:
        """Get command invocation details for a specific instance."""
        try:
            self.logger.debug(f"Getting command invocation for {command_id} on {instance_id}")
            
            response = self._client.get_command_invocation(
                CommandId=command_id,
                InstanceId=instance_id
            )
            
            return {
                'command_id': command_id,
                'instance_id': instance_id,
                'status': response['Status'],
                'status_details': response.get('StatusDetails', ''),
                'standard_output': response.get('StandardOutputContent', ''),
                'standard_error': response.get('StandardErrorContent', ''),
                'response_code': response.get('ResponseCode', -1),
                'execution_start_time': response.get('ExecutionStartDateTime'),
                'execution_end_time': response.get('ExecutionEndDateTime')
            }
            
        except ClientError as e:
            error_code = e.response['Error']['Code']
            
            if error_code == 'InvocationDoesNotExist':
                self.logger.warning(f"Command invocation not found: {command_id} on {instance_id}")
                return {}
            else:
                self.logger.error(f"Error getting command invocation: {error_code}")
                raise
        except Exception as e:
            self.logger.error(f"Unexpected error getting command invocation: {str(e)}")
            raise
    
    async def list_command_invocations(
        self,
        command_id: Optional[str] = None,
        instance_id: Optional[str] = None,
        filters: Optional[List[Dict[str, Any]]] = None
    ) -> List[Dict[str, Any]]:
        """List command invocations."""
        try:
            self.logger.debug("Listing command invocations")
            
            params = {}
            
            if command_id:
                params['CommandId'] = command_id
            
            if instance_id:
                params['InstanceId'] = instance_id
            
            if filters:
                params['Filters'] = filters
            
            # Get command invocations
            invocations = []
            paginator = self._client.get_paginator('list_command_invocations')
            
            for page in paginator.paginate(**params):
                invocations.extend(page['CommandInvocations'])
            
            self.logger.debug(f"Found {len(invocations)} command invocations")
            return invocations
            
        except ClientError as e:
            self.logger.error(f"Failed to list command invocations: {str(e)}")
            raise
        except Exception as e:
            self.logger.error(f"Unexpected error listing command invocations: {str(e)}")
            raise
    
    async def wait_for_command_completion(
        self,
        command_id: str,
        instance_ids: List[str],
        max_wait_time: int = 3600,
        poll_interval: int = 30
    ) -> Dict[str, Any]:
        """Wait for command to complete on all instances."""
        try:
            self.logger.info(f"Waiting for command {command_id} to complete on {len(instance_ids)} instances")
            
            start_time = datetime.utcnow()
            completed_instances = set()
            failed_instances = set()
            results = {}
            
            while (datetime.utcnow() - start_time).total_seconds() < max_wait_time:
                # Check status for each instance
                for instance_id in instance_ids:
                    if instance_id in completed_instances or instance_id in failed_instances:
                        continue
                    
                    try:
                        invocation = await self.get_command_invocation(command_id, instance_id)
                        
                        if invocation:
                            status = invocation['status']
                            results[instance_id] = invocation
                            
                            if status in ['Success', 'Failed', 'Cancelled', 'TimedOut']:
                                if status == 'Success':
                                    completed_instances.add(instance_id)
                                else:
                                    failed_instances.add(instance_id)
                    
                    except Exception as e:
                        self.logger.warning(f"Error checking command status for {instance_id}: {str(e)}")
                
                # Check if all instances are done
                total_done = len(completed_instances) + len(failed_instances)
                if total_done >= len(instance_ids):
                    break
                
                # Wait before next poll
                await asyncio.sleep(poll_interval)
            
            # Prepare final result
            result = {
                'command_id': command_id,
                'completed_instances': list(completed_instances),
                'failed_instances': list(failed_instances),
                'results': results,
                'total_instances': len(instance_ids),
                'success_count': len(completed_instances),
                'failure_count': len(failed_instances),
                'timestamp': datetime.utcnow().isoformat()
            }
            
            if total_done < len(instance_ids):
                result['timed_out'] = True
                result['pending_instances'] = [
                    iid for iid in instance_ids 
                    if iid not in completed_instances and iid not in failed_instances
                ]
            
            self.logger.info(f"Command completion: {len(completed_instances)} success, {len(failed_instances)} failed")
            return result
            
        except Exception as e:
            self.logger.error(f"Error waiting for command completion: {str(e)}")
            raise
    
    async def get_patch_baseline_for_instance(
        self,
        instance_id: str
    ) -> Dict[str, Any]:
        """Get patch baseline for an instance."""
        try:
            self.logger.debug(f"Getting patch baseline for instance {instance_id}")
            
            response = self._client.get_patch_baseline_for_patch_group(
                PatchGroup=instance_id
            )
            
            return {
                'baseline_id': response.get('BaselineId'),
                'patch_group': response.get('PatchGroup'),
                'operating_system': response.get('OperatingSystem')
            }
            
        except ClientError as e:
            error_code = e.response['Error']['Code']
            
            if error_code == 'DoesNotExistException':
                self.logger.warning(f"No patch baseline found for instance {instance_id}")
                return {}
            else:
                self.logger.error(f"Error getting patch baseline: {error_code}")
                raise
        except Exception as e:
            self.logger.error(f"Unexpected error getting patch baseline: {str(e)}")
            raise
    
    async def describe_patch_baselines(
        self,
        filters: Optional[List[Dict[str, Any]]] = None
    ) -> List[Dict[str, Any]]:
        """Describe patch baselines."""
        try:
            self.logger.debug("Describing patch baselines")
            
            params = {}
            
            if filters:
                params['Filters'] = filters
            
            # Get patch baselines
            baselines = []
            paginator = self._client.get_paginator('describe_patch_baselines')
            
            for page in paginator.paginate(**params):
                baselines.extend(page['BaselineIdentities'])
            
            self.logger.debug(f"Found {len(baselines)} patch baselines")
            return baselines
            
        except ClientError as e:
            self.logger.error(f"Failed to describe patch baselines: {str(e)}")
            raise
        except Exception as e:
            self.logger.error(f"Unexpected error describing patch baselines: {str(e)}")
            raise
    
    async def get_maintenance_window_execution(
        self,
        window_execution_id: str
    ) -> Dict[str, Any]:
        """Get maintenance window execution details."""
        try:
            self.logger.debug(f"Getting maintenance window execution {window_execution_id}")
            
            response = self._client.get_maintenance_window_execution(
                WindowExecutionId=window_execution_id
            )
            
            return {
                'window_execution_id': window_execution_id,
                'task_ids': response.get('TaskIds', []),
                'status': response.get('Status'),
                'status_details': response.get('StatusDetails'),
                'start_time': response.get('StartTime'),
                'end_time': response.get('EndTime')
            }
            
        except ClientError as e:
            error_code = e.response['Error']['Code']
            
            if error_code == 'DoesNotExistException':
                self.logger.warning(f"Maintenance window execution not found: {window_execution_id}")
                return {}
            else:
                self.logger.error(f"Error getting maintenance window execution: {error_code}")
                raise
        except Exception as e:
            self.logger.error(f"Unexpected error getting maintenance window execution: {str(e)}")
            raise
    
    async def ping_instance(self, instance_id: str) -> Dict[str, Any]:
        """Ping an instance to check SSM connectivity."""
        try:
            self.logger.debug(f"Pinging instance {instance_id} via SSM")
            
            # Send a simple ping command
            command_result = await self.send_command(
                instance_ids=[instance_id],
                document_name='AWS-RunShellScript',
                parameters={
                    'commands': ['echo "SSM ping successful"']
                },
                timeout_seconds=60,
                comment='SSM connectivity test'
            )
            
            command_id = command_result['command_id']
            
            # Wait for command completion
            wait_result = await self.wait_for_command_completion(
                command_id=command_id,
                instance_ids=[instance_id],
                max_wait_time=120,
                poll_interval=5
            )
            
            success = instance_id in wait_result['completed_instances']
            
            return {
                'instance_id': instance_id,
                'ssm_reachable': success,
                'command_id': command_id,
                'result': wait_result.get('results', {}).get(instance_id, {}),
                'timestamp': datetime.utcnow().isoformat()
            }
            
        except Exception as e:
            self.logger.error(f"Error pinging instance {instance_id}: {str(e)}")
            return {
                'instance_id': instance_id,
                'ssm_reachable': False,
                'error': str(e),
                'timestamp': datetime.utcnow().isoformat()
            }
    
    def _map_ssm_status(self, ping_status: str) -> SSMStatus:
        """Map SSM ping status to our SSMStatus enum."""
        status_mapping = {
            'Online': SSMStatus.ONLINE,
            'Connection Lost': SSMStatus.CONNECTION_LOST,
            'Inactive': SSMStatus.INACTIVE,
            'Stopped': SSMStatus.STOPPED
        }
        
        return status_mapping.get(ping_status, SSMStatus.UNKNOWN)
    
    async def get_parameters(
        self,
        names: List[str],
        with_decryption: bool = False
    ) -> Dict[str, Any]:
        """Get SSM parameters."""
        try:
            self.logger.debug(f"Getting {len(names)} SSM parameters")
            
            # Get parameters in batches (SSM has limits)
            batch_size = 10
            all_parameters = []
            invalid_parameters = []
            
            for i in range(0, len(names), batch_size):
                batch = names[i:i + batch_size]
                
                try:
                    response = self._client.get_parameters(
                        Names=batch,
                        WithDecryption=with_decryption
                    )
                    
                    all_parameters.extend(response['Parameters'])
                    invalid_parameters.extend(response.get('InvalidParameters', []))
                    
                except ClientError as e:
                    self.logger.warning(f"Error getting parameter batch: {str(e)}")
                    invalid_parameters.extend(batch)
            
            return {
                'parameters': all_parameters,
                'invalid_parameters': invalid_parameters
            }
            
        except Exception as e:
            self.logger.error(f"Unexpected error getting parameters: {str(e)}")
            raise