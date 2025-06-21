"""Workflow orchestrator service implementation."""

import asyncio
import logging
from datetime import datetime, timedelta
from typing import List, Dict, Any, Optional, Set
from uuid import uuid4

from core.interfaces.workflow_interface import IWorkflowOrchestrator
from core.interfaces.scanner_interface import IScannerService
from core.interfaces.ami_backup_interface import IAMIBackupService
from core.interfaces.server_manager_interface import IServerManagerService
from core.interfaces.config_interface import IConfigService
from core.interfaces.storage_interface import IStorageService
from core.models.instance import Instance
from core.models.workflow import (
    WorkflowResult, WorkflowPhase, WorkflowStatus, PhaseResult,
    PhaseStatus, WorkflowContext, PhaseMetrics
)
from core.models.config import WorkflowConfig
from core.models.report import Report, ReportSection, ReportMetrics, ReportType
from core.models.ami_backup import BackupType


class WorkflowOrchestrator(IWorkflowOrchestrator):
    """Implementation of workflow orchestrator."""
    
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
        
        # Track active workflows
        self._active_workflows: Dict[str, WorkflowResult] = {}
        self._workflow_contexts: Dict[str, WorkflowContext] = {}
        self._cancellation_tokens: Dict[str, bool] = {}
    
    async def run_prepatch_workflow(self, config_file: str) -> WorkflowResult:
        """Run the complete pre-patch workflow."""
        self.logger.info(f"Starting pre-patch workflow with config: {config_file}")
        
        # Load configuration
        workflow_config = self.config_service.load_workflow_config(config_file)
        
        # Validate configuration
        config_errors = self.config_service.validate_config()
        if config_errors:
            error_msg = f"Configuration validation failed: {'; '.join(config_errors)}"
            self.logger.error(error_msg)
            raise ValueError(error_msg)
        
        # Create workflow result
        workflow_id = str(uuid4())
        workflow_result = WorkflowResult(
            workflow_id=workflow_id,
            workflow_name=workflow_config.name,
            config_file=config_file,
            start_time=datetime.utcnow(),
            status=WorkflowStatus.RUNNING,
            phases=workflow_config.phases
        )
        
        # Create workflow context
        context = WorkflowContext(
            workflow_id=workflow_id,
            config=workflow_config,
            instances=[],
            phase_results={},
            metadata={}
        )
        
        # Track workflow
        self._active_workflows[workflow_id] = workflow_result
        self._workflow_contexts[workflow_id] = context
        self._cancellation_tokens[workflow_id] = False
        
        try:
            # Run workflow phases
            await self._execute_workflow_phases(workflow_result, context)
            
            # Mark workflow as completed
            workflow_result.mark_completed()
            
            # Generate final report
            await self._generate_workflow_report(workflow_result, context)
            
            self.logger.info(f"Pre-patch workflow completed successfully: {workflow_id}")
            
        except Exception as e:
            # Mark workflow as failed
            workflow_result.mark_failed(str(e))
            self.logger.error(f"Pre-patch workflow failed: {str(e)}")
            
            # Generate failure report
            await self._generate_workflow_report(workflow_result, context)
            
        finally:
            # Cleanup
            self._active_workflows.pop(workflow_id, None)
            self._workflow_contexts.pop(workflow_id, None)
            self._cancellation_tokens.pop(workflow_id, None)
        
        return workflow_result
    
    async def run_workflow_phase(self, workflow_id: str, phase: WorkflowPhase) -> PhaseResult:
        """Run a specific workflow phase."""
        self.logger.info(f"Running workflow phase: {phase.value} for workflow {workflow_id}")
        
        workflow_result = self._active_workflows.get(workflow_id)
        context = self._workflow_contexts.get(workflow_id)
        
        if not workflow_result or not context:
            raise ValueError(f"Workflow {workflow_id} not found or not active")
        
        # Check for cancellation
        if self._cancellation_tokens.get(workflow_id, False):
            raise asyncio.CancelledError("Workflow was cancelled")
        
        # Create phase result
        phase_result = PhaseResult(
            phase=phase,
            start_time=datetime.utcnow(),
            status=PhaseStatus.RUNNING
        )
        
        try:
            # Execute phase based on type
            if phase == WorkflowPhase.SCANNER:
                await self._run_scanner_phase(phase_result, context)
            elif phase == WorkflowPhase.AMI_BACKUP:
                await self._run_ami_backup_phase(phase_result, context)
            elif phase == WorkflowPhase.START_SERVERS:
                await self._run_start_servers_phase(phase_result, context)
            elif phase == WorkflowPhase.VALIDATION:
                await self._run_validation_phase(phase_result, context)
            else:
                raise ValueError(f"Unsupported workflow phase: {phase}")
            
            # Mark phase as completed
            phase_result.mark_completed()
            
        except Exception as e:
            # Mark phase as failed
            phase_result.mark_failed(str(e))
            self.logger.error(f"Phase {phase.value} failed: {str(e)}")
        
        # Store phase result
        context.phase_results[phase] = phase_result
        workflow_result.phase_results[phase] = phase_result
        
        return phase_result
    
    async def get_workflow_status(self, workflow_id: str) -> Optional[WorkflowResult]:
        """Get the status of a workflow."""
        return self._active_workflows.get(workflow_id)
    
    async def cancel_workflow(self, workflow_id: str) -> bool:
        """Cancel a running workflow."""
        if workflow_id in self._cancellation_tokens:
            self._cancellation_tokens[workflow_id] = True
            self.logger.info(f"Cancellation requested for workflow {workflow_id}")
            return True
        return False
    
    async def get_workflow_progress(self, workflow_id: str) -> Dict[str, Any]:
        """Get detailed progress information for a workflow."""
        workflow_result = self._active_workflows.get(workflow_id)
        context = self._workflow_contexts.get(workflow_id)
        
        if not workflow_result:
            return {}
        
        progress = {
            'workflow_id': workflow_id,
            'status': workflow_result.status.value,
            'start_time': workflow_result.start_time.isoformat(),
            'current_phase': workflow_result.current_phase.value if workflow_result.current_phase else None,
            'completed_phases': [p.value for p in workflow_result.completed_phases],
            'total_phases': len(workflow_result.phases),
            'progress_percentage': (len(workflow_result.completed_phases) / len(workflow_result.phases)) * 100,
            'instances_discovered': len(context.instances) if context else 0,
            'phase_details': {}
        }
        
        # Add phase details
        if context:
            for phase, result in context.phase_results.items():
                progress['phase_details'][phase.value] = {
                    'status': result.status.value,
                    'start_time': result.start_time.isoformat(),
                    'end_time': result.end_time.isoformat() if result.end_time else None,
                    'duration_seconds': result.duration_seconds,
                    'instances_processed': len(result.instance_results),
                    'errors': len(result.errors)
                }
        
        return progress
    
    async def list_active_workflows(self) -> List[Dict[str, Any]]:
        """List all currently active workflows."""
        active_workflows = []
        
        for workflow_id, workflow_result in self._active_workflows.items():
            workflow_info = {
                'workflow_id': workflow_id,
                'name': workflow_result.workflow_name,
                'status': workflow_result.status.value,
                'start_time': workflow_result.start_time.isoformat(),
                'current_phase': workflow_result.current_phase.value if workflow_result.current_phase else None,
                'progress_percentage': (len(workflow_result.completed_phases) / len(workflow_result.phases)) * 100
            }
            active_workflows.append(workflow_info)
        
        return active_workflows
    
    async def validate_workflow_config(self, config_file: str) -> List[str]:
        """Validate workflow configuration without running it."""
        try:
            # Load and validate configuration
            self.config_service.load_workflow_config(config_file)
            return self.config_service.validate_config()
        except Exception as e:
            return [f"Configuration loading error: {str(e)}"]
    
    async def _execute_workflow_phases(self, workflow_result: WorkflowResult, context: WorkflowContext) -> None:
        """Execute all workflow phases in sequence."""
        for phase_name in context.config.phases:
            try:
                # Map phase name to enum
                phase = WorkflowPhase(phase_name)
                
                # Update current phase
                workflow_result.current_phase = phase
                
                # Run the phase
                await self.run_workflow_phase(workflow_result.workflow_id, phase)
                
                # Add to completed phases
                workflow_result.completed_phases.append(phase)
                
                self.logger.info(f"Completed phase: {phase.value}")
                
            except Exception as e:
                self.logger.error(f"Phase {phase_name} failed: {str(e)}")
                raise
    
    async def _run_scanner_phase(self, phase_result: PhaseResult, context: WorkflowContext) -> None:
        """Run the scanner phase to discover instances."""
        self.logger.info("Running scanner phase")
        
        try:
            # Get landing zones from configuration
            landing_zones = context.config.landing_zones
            
            if not landing_zones:
                raise ValueError("No landing zones configured for scanning")
            
            # Scan all landing zones
            all_instances = []
            
            for lz in landing_zones:
                if not lz.enabled:
                    self.logger.info(f"Skipping disabled landing zone: {lz.name}")
                    continue
                
                self.logger.info(f"Scanning landing zone: {lz.name}")
                
                try:
                    # Scan landing zone
                    lz_instances = await self.scanner_service.scan_landing_zone(
                        lz.account_id,
                        lz.regions,
                        lz.role_name,
                        lz.filters
                    )
                    
                    # Add landing zone info to instances
                    for instance in lz_instances:
                        instance.landing_zone = lz.name
                    
                    all_instances.extend(lz_instances)
                    
                    self.logger.info(f"Found {len(lz_instances)} instances in landing zone {lz.name}")
                    
                except Exception as e:
                    error_msg = f"Error scanning landing zone {lz.name}: {str(e)}"
                    self.logger.error(error_msg)
                    phase_result.add_error(error_msg)
                    continue
            
            # Store discovered instances
            context.instances = all_instances
            
            # Update phase metrics
            phase_result.metrics = PhaseMetrics(
                instances_processed=len(all_instances),
                successful_operations=len(all_instances),
                failed_operations=len(phase_result.errors)
            )
            
            # Save instances to storage
            timestamp = datetime.utcnow().strftime("%Y%m%d_%H%M%S")
            instances_file = f"./data/instances/discovered_instances_{timestamp}.csv"
            
            await self.storage_service.save_instances_to_csv(all_instances, instances_file)
            
            self.logger.info(f"Scanner phase completed: discovered {len(all_instances)} instances")
            
        except Exception as e:
            self.logger.error(f"Scanner phase failed: {str(e)}")
            raise
    
    async def _run_ami_backup_phase(self, phase_result: PhaseResult, context: WorkflowContext) -> None:
        """Run the AMI backup phase."""
        self.logger.info("Running AMI backup phase")
        
        try:
            # Filter instances that require backup
            backup_instances = [inst for inst in context.instances if inst.requires_backup]
            
            if not backup_instances:
                self.logger.info("No instances require backup")
                phase_result.metrics = PhaseMetrics(
                    instances_processed=0,
                    successful_operations=0,
                    failed_operations=0
                )
                return
            
            self.logger.info(f"Creating backups for {len(backup_instances)} instances")
            
            # Get backup configuration
            backup_config = context.config.ami_backup
            max_concurrent = backup_config.max_concurrent_backups if backup_config else 10
            
            # Create backups
            backup_results = await self.ami_backup_service.create_multiple_backups(
                backup_instances,
                BackupType.PRE_PATCH,
                max_concurrent
            )
            
            # Wait for backups to complete if configured
            if backup_config and backup_config.enabled:
                timeout_minutes = backup_config.timeout_minutes
                
                self.logger.info(f"Waiting for backups to complete (timeout: {timeout_minutes} minutes)")
                
                completed_backups = 0
                failed_backups = 0
                
                for backup in backup_results:
                    try:
                        success = await self.ami_backup_service.wait_for_completion(
                            backup, timeout_minutes
                        )
                        
                        if success:
                            completed_backups += 1
                        else:
                            failed_backups += 1
                            phase_result.add_error(f"Backup failed for instance {backup.instance_id}")
                            
                    except Exception as e:
                        failed_backups += 1
                        error_msg = f"Backup error for instance {backup.instance_id}: {str(e)}"
                        phase_result.add_error(error_msg)
                
                self.logger.info(f"Backup phase completed: {completed_backups} successful, {failed_backups} failed")
            
            # Update phase metrics
            successful_backups = len([b for b in backup_results if not b.is_failed])
            failed_backups = len(backup_results) - successful_backups
            
            phase_result.metrics = PhaseMetrics(
                instances_processed=len(backup_instances),
                successful_operations=successful_backups,
                failed_operations=failed_backups
            )
            
            # Store backup results in context
            context.metadata['backup_results'] = backup_results
            
        except Exception as e:
            self.logger.error(f"AMI backup phase failed: {str(e)}")
            raise
    
    async def _run_start_servers_phase(self, phase_result: PhaseResult, context: WorkflowContext) -> None:
        """Run the start servers phase."""
        self.logger.info("Running start servers phase")
        
        try:
            # Filter instances that need to be started (currently stopped)
            from core.models.instance import InstanceStatus
            
            stopped_instances = [
                inst for inst in context.instances 
                if inst.status in [InstanceStatus.STOPPED, InstanceStatus.STOPPING]
            ]
            
            if not stopped_instances:
                self.logger.info("No stopped instances to start")
                phase_result.metrics = PhaseMetrics(
                    instances_processed=0,
                    successful_operations=0,
                    failed_operations=0
                )
                return
            
            self.logger.info(f"Starting {len(stopped_instances)} instances")
            
            # Get server manager configuration
            server_config = context.config.server_manager
            max_concurrent = server_config.max_concurrent_operations if server_config else 10
            wait_for_ready = server_config.validate_health_after_start if server_config else True
            
            # Start instances
            start_results = await self.server_manager_service.start_multiple_instances(
                stopped_instances,
                max_concurrent,
                wait_for_ready
            )
            
            # Process results
            successful_starts = len([r for r in start_results if r.status.value == 'completed'])
            failed_starts = len(start_results) - successful_starts
            
            # Add errors for failed starts
            for result in start_results:
                if result.status.value != 'completed':
                    error_msg = f"Failed to start instance {result.instance_id}: {result.error_message or 'Unknown error'}"
                    phase_result.add_error(error_msg)
            
            # Update phase metrics
            phase_result.metrics = PhaseMetrics(
                instances_processed=len(stopped_instances),
                successful_operations=successful_starts,
                failed_operations=failed_starts
            )
            
            # Store start results in context
            context.metadata['start_results'] = start_results
            
            self.logger.info(f"Start servers phase completed: {successful_starts} successful, {failed_starts} failed")
            
        except Exception as e:
            self.logger.error(f"Start servers phase failed: {str(e)}")
            raise
    
    async def _run_validation_phase(self, phase_result: PhaseResult, context: WorkflowContext) -> None:
        """Run the validation phase."""
        self.logger.info("Running validation phase")
        
        try:
            # Get validation configuration
            validation_config = context.config.validation
            
            if not validation_config or not validation_config.enabled:
                self.logger.info("Validation phase is disabled")
                return
            
            # Validate all instances
            validation_results = []
            
            for instance in context.instances:
                try:
                    # Validate instance health
                    health_check = await self.server_manager_service.validate_instance_health(instance)
                    validation_results.append(health_check)
                    
                    # Check if validation failed
                    if not health_check.get('overall_healthy', False):
                        error_msg = f"Health validation failed for instance {instance.instance_id}"
                        phase_result.add_error(error_msg)
                        
                        # Stop workflow if configured to fail on validation error
                        if validation_config.fail_on_validation_error:
                            raise Exception(error_msg)
                    
                except Exception as e:
                    error_msg = f"Validation error for instance {instance.instance_id}: {str(e)}"
                    phase_result.add_error(error_msg)
                    validation_results.append({
                        'instance_id': instance.instance_id,
                        'overall_healthy': False,
                        'error': str(e)
                    })
            
            # Calculate metrics
            healthy_instances = len([r for r in validation_results if r.get('overall_healthy', False)])
            unhealthy_instances = len(validation_results) - healthy_instances
            
            phase_result.metrics = PhaseMetrics(
                instances_processed=len(context.instances),
                successful_operations=healthy_instances,
                failed_operations=unhealthy_instances
            )
            
            # Store validation results in context
            context.metadata['validation_results'] = validation_results
            
            self.logger.info(f"Validation phase completed: {healthy_instances} healthy, {unhealthy_instances} unhealthy")
            
        except Exception as e:
            self.logger.error(f"Validation phase failed: {str(e)}")
            raise
    
    async def _generate_workflow_report(self, workflow_result: WorkflowResult, context: WorkflowContext) -> None:
        """Generate a comprehensive workflow report."""
        try:
            self.logger.info("Generating workflow report")
            
            # Create report sections
            sections = []
            
            for phase, phase_result in context.phase_results.items():
                section = ReportSection(
                    name=phase.value.replace('_', ' ').title(),
                    status=phase_result.status.value,
                    start_time=phase_result.start_time,
                    end_time=phase_result.end_time,
                    duration_seconds=phase_result.duration_seconds,
                    instance_results={},  # Could be populated with detailed results
                    errors=[{'message': error, 'timestamp': datetime.utcnow()} for error in phase_result.errors]
                )
                sections.append(section)
            
            # Calculate overall metrics
            total_instances = len(context.instances)
            total_errors = sum(len(pr.errors) for pr in context.phase_results.values())
            
            metrics = ReportMetrics(
                total_instances=total_instances,
                successful_instances=total_instances - min(total_errors, total_instances),
                failed_instances=min(total_errors, total_instances),
                total_phases=len(context.phase_results),
                successful_phases=len([pr for pr in context.phase_results.values() if pr.status == PhaseStatus.COMPLETED]),
                failed_phases=len([pr for pr in context.phase_results.values() if pr.status == PhaseStatus.FAILED])
            )
            
            # Create report
            report = Report(
                workflow_id=workflow_result.workflow_id,
                workflow_name=workflow_result.workflow_name,
                report_type=ReportType.WORKFLOW_SUMMARY,
                start_time=workflow_result.start_time,
                end_time=workflow_result.end_time,
                status=workflow_result.status.value,
                sections=sections,
                metrics=metrics
            )
            
            # Save report in multiple formats
            timestamp = datetime.utcnow().strftime("%Y%m%d_%H%M%S")
            report_base_path = f"./data/reports/workflow_report_{workflow_result.workflow_id}_{timestamp}"
            
            # Save as JSON
            await self.storage_service.save_report(
                report, f"{report_base_path}.json", ReportFormat.JSON
            )
            
            # Save as HTML
            await self.storage_service.save_report(
                report, f"{report_base_path}.html", ReportFormat.HTML
            )
            
            # Save as CSV
            await self.storage_service.save_report(
                report, f"{report_base_path}.csv", ReportFormat.CSV
            )
            
            self.logger.info(f"Workflow report generated: {report_base_path}")
            
        except Exception as e:
            self.logger.error(f"Error generating workflow report: {str(e)}")