import asyncio
import logging
from datetime import datetime
from typing import List, Any
from uuid import uuid4

from core.interfaces.workflow_interface import IWorkflowOrchestrator
from core.interfaces.scanner_interface import IScannerService
from core.interfaces.ami_backup_interface import IAMIBackupService
from core.interfaces.server_manager_interface import IServerManagerService
from core.interfaces.config_interface import IConfigService
from core.interfaces.storage_interface import IStorageService
from core.models.instance import Instance
from core.models.workflow import WorkflowResult, WorkflowStatus
from core.models.config import WorkflowConfig
from core.models.report import Report, ReportType


class WorkflowOrchestrator(IWorkflowOrchestrator):
    """Workflow orchestrator for pre-patch operations."""
    
    def __init__(
        self,
        config_service: IConfigService,
        scanner_service: IScannerService,
        ami_backup_service: IAMIBackupService,
        server_manager_service: IServerManagerService,
        storage_service: IStorageService
    ):
        self.config_service = config_service
        self.scanner_service = scanner_service
        self.ami_backup_service = ami_backup_service
        self.server_manager_service = server_manager_service
        self.storage_service = storage_service
        self.logger = logging.getLogger(__name__)
    
    def _handle_error(self, message: str, error: Exception) -> None:
        """Centralized error handling."""
        error_msg = f"{message}: {str(error)}"
        self.logger.error(error_msg)
        return error_msg
    
    async def run_prepatch_workflow(self, config_file: str) -> WorkflowResult:
        """Run the complete pre-patch workflow."""
        self.logger.info(f"Starting workflow: {config_file}")
        
        workflow_config = self.config_service.load_workflow_config(config_file)
        config_errors = workflow_config.validate()
        if config_errors:
            raise ValueError(f"Config validation failed: {'; '.join(config_errors)}")
        
        workflow_result = WorkflowResult(
            workflow_id=str(uuid4()),
            workflow_name=workflow_config.name,
            config_file=config_file,
            start_time=datetime.utcnow(),
            status=WorkflowStatus.RUNNING
        )
        
        try:
            instances = await self._run_scanner_phase(workflow_config)
            workflow_result.instances_found = len(instances)
            
            if not workflow_config.skip_backup and workflow_config.ami_backup.enabled:
                backup_results = await self._run_ami_backup_phase(instances, workflow_config)
                workflow_result.backups_created = len([r for r in backup_results if r.success])
            
            if workflow_config.server_manager.enabled:
                server_results = await self._run_server_management_phase(instances, workflow_config)
                workflow_result.servers_managed = len([r for r in server_results if r.success])
            
            workflow_result.status = WorkflowStatus.COMPLETED
            workflow_result.end_time = datetime.utcnow()
            
            await self._generate_report(workflow_result, instances)
            self.logger.info(f"Workflow completed: {workflow_result.workflow_id}")
            
        except Exception as e:
            workflow_result.status = WorkflowStatus.FAILED
            workflow_result.end_time = datetime.utcnow()
            workflow_result.error_message = str(e)
            self._handle_error("Workflow failed", e)
            raise
        
        return workflow_result
    
    async def _run_scanner_phase(self, config: WorkflowConfig) -> List[Instance]:
        """Discover instances across landing zones."""
        if not config.landing_zones:
            raise ValueError("No landing zones configured")
        
        all_instances = []
        
        for lz_name in config.landing_zones:
            try:
                lz_config = self.config_service.load_landing_zone_config(lz_name)
                instances = await self.scanner_service.scan_landing_zone(
                    account_id=lz_config.account_id,
                    region=config.aws.region,
                    role_name=config.aws.role_name
                )
                
                for instance in instances:
                    instance.landing_zone = lz_name
                
                all_instances.extend(instances)
                self.logger.info(f"Found {len(instances)} instances in {lz_name}")
                
            except Exception as e:
                self._handle_error(f"Error scanning {lz_name}", e)
                if not config.continue_on_error:
                    raise
        
        self.logger.info(f"Total instances found: {len(all_instances)}")
        return all_instances
    
    async def _run_ami_backup_phase(self, instances: List[Instance], config: WorkflowConfig) -> List[Any]:
        """Create AMI backups for instances."""
        backup_results = []
        semaphore = asyncio.Semaphore(config.ami_backup.max_concurrent)
        
        async def backup_instance(instance: Instance):
            async with semaphore:
                try:
                    result = await self.ami_backup_service.create_backup(
                        instance_id=instance.instance_id,
                        account_id=instance.account_id,
                        region=instance.region,
                        role_name=config.aws.role_name,
                        timeout_minutes=config.ami_backup.timeout_minutes
                    )
                    backup_results.append(result)
                    return result
                except Exception as e:
                    self._handle_error(f"Backup failed for {instance.instance_id}", e)
                    if not config.continue_on_error:
                        raise
        
        await asyncio.gather(*[backup_instance(instance) for instance in instances], return_exceptions=True)
        
        successful = len([r for r in backup_results if r.success])
        self.logger.info(f"Backups: {successful}/{len(instances)} successful")
        return backup_results
    
    async def _run_server_management_phase(self, instances: List[Instance], config: WorkflowConfig) -> List[Any]:
        """Manage server instances."""
        management_results = []
        semaphore = asyncio.Semaphore(config.server_manager.max_concurrent)
        
        async def manage_instance(instance: Instance):
            async with semaphore:
                try:
                    result = await self.server_manager_service.start_instance(
                        instance_id=instance.instance_id,
                        account_id=instance.account_id,
                        region=instance.region,
                        role_name=config.aws.role_name,
                        timeout_minutes=config.server_manager.timeout_minutes
                    )
                    management_results.append(result)
                    return result
                except Exception as e:
                    self._handle_error(f"Server management failed for {instance.instance_id}", e)
                    if not config.continue_on_error:
                        raise
        
        await asyncio.gather(*[manage_instance(instance) for instance in instances], return_exceptions=True)
        
        successful = len([r for r in management_results if r.success])
        self.logger.info(f"Server management: {successful}/{len(instances)} successful")
        return management_results
    
    async def _generate_report(self, workflow_result: WorkflowResult, instances: List[Instance]) -> None:
        """Generate and save workflow report."""
        try:
            report = Report(
                report_id=str(uuid4()),
                workflow_id=workflow_result.workflow_id,
                report_type=ReportType.WORKFLOW_SUMMARY,
                generated_at=datetime.utcnow(),
                instances=instances,
                summary={
                    'workflow_name': workflow_result.workflow_name,
                    'status': workflow_result.status.value,
                    'instances_found': workflow_result.instances_found,
                    'backups_created': getattr(workflow_result, 'backups_created', 0),
                    'servers_managed': getattr(workflow_result, 'servers_managed', 0),
                    'duration': str(workflow_result.end_time - workflow_result.start_time) if workflow_result.end_time else None
                }
            )
            
            await self.storage_service.save_report(report)
            self.logger.info(f"Report saved: {report.report_id}")
            
        except Exception as e:
            self._handle_error("Report generation failed", e)