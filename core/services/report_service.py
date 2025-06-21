"""Report service for generating comprehensive workflow reports."""

import logging
from datetime import datetime
from typing import List, Dict, Any, Optional
from pathlib import Path

from core.models.report import Report, ReportSection, ReportMetrics, ReportType, ReportFormat
from core.models.workflow import WorkflowResult, PhaseResult
from core.models.instance import Instance
from core.interfaces.storage_interface import IStorageService


class ReportService:
    """Service for generating and managing reports."""
    
    def __init__(self, storage_service: IStorageService):
        self.storage_service = storage_service
        self.logger = logging.getLogger(__name__)
    
    async def generate_workflow_report(
        self,
        workflow_result: WorkflowResult,
        instances: List[Instance],
        phase_results: Dict[str, PhaseResult],
        output_path: Optional[str] = None
    ) -> Report:
        """Generate a comprehensive workflow report."""
        self.logger.info(f"Generating workflow report for {workflow_result.workflow_id}")
        
        try:
            # Create report sections for each phase
            sections = []
            
            for phase_name, phase_result in phase_results.items():
                section = await self._create_phase_section(phase_name, phase_result, instances)
                sections.append(section)
            
            # Calculate overall metrics
            metrics = self._calculate_workflow_metrics(workflow_result, instances, phase_results)
            
            # Create the main report
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
            
            # Add workflow-level errors
            if workflow_result.error_message:
                report.add_error(workflow_result.error_message, workflow_result.end_time or datetime.utcnow())
            
            # Save report if output path is provided
            if output_path:
                await self._save_report_multiple_formats(report, output_path)
            
            self.logger.info(f"Workflow report generated successfully")
            return report
            
        except Exception as e:
            self.logger.error(f"Error generating workflow report: {str(e)}")
            raise
    
    async def generate_phase_report(
        self,
        phase_name: str,
        phase_result: PhaseResult,
        instances: List[Instance],
        output_path: Optional[str] = None
    ) -> Report:
        """Generate a detailed report for a specific phase."""
        self.logger.info(f"Generating phase report for {phase_name}")
        
        try:
            # Create detailed phase section
            section = await self._create_detailed_phase_section(phase_name, phase_result, instances)
            
            # Calculate phase metrics
            metrics = self._calculate_phase_metrics(phase_result, instances)
            
            # Create the phase report
            report = Report(
                workflow_id=f"phase_{phase_name}_{datetime.utcnow().strftime('%Y%m%d_%H%M%S')}",
                workflow_name=f"Phase Report: {phase_name}",
                report_type=ReportType.PHASE_DETAIL,
                start_time=phase_result.start_time,
                end_time=phase_result.end_time,
                status=phase_result.status.value,
                sections=[section],
                metrics=metrics
            )
            
            # Add phase-level errors
            for error in phase_result.errors:
                report.add_error(error, phase_result.end_time or datetime.utcnow())
            
            # Save report if output path is provided
            if output_path:
                await self._save_report_multiple_formats(report, output_path)
            
            self.logger.info(f"Phase report generated successfully")
            return report
            
        except Exception as e:
            self.logger.error(f"Error generating phase report: {str(e)}")
            raise
    
    async def generate_instance_summary_report(
        self,
        instances: List[Instance],
        output_path: Optional[str] = None
    ) -> Report:
        """Generate a summary report of all discovered instances."""
        self.logger.info(f"Generating instance summary report for {len(instances)} instances")
        
        try:
            # Group instances by various criteria
            instance_groups = self._group_instances(instances)
            
            # Create sections for each grouping
            sections = []
            
            # By platform
            platform_section = self._create_platform_section(instance_groups['by_platform'])
            sections.append(platform_section)
            
            # By status
            status_section = self._create_status_section(instance_groups['by_status'])
            sections.append(status_section)
            
            # By landing zone
            if instance_groups['by_landing_zone']:
                lz_section = self._create_landing_zone_section(instance_groups['by_landing_zone'])
                sections.append(lz_section)
            
            # By region
            region_section = self._create_region_section(instance_groups['by_region'])
            sections.append(region_section)
            
            # Calculate instance metrics
            metrics = self._calculate_instance_metrics(instances)
            
            # Create the instance summary report
            report = Report(
                workflow_id=f"instance_summary_{datetime.utcnow().strftime('%Y%m%d_%H%M%S')}",
                workflow_name="Instance Discovery Summary",
                report_type=ReportType.INSTANCE_SUMMARY,
                start_time=datetime.utcnow(),
                end_time=datetime.utcnow(),
                status="completed",
                sections=sections,
                metrics=metrics
            )
            
            # Save report if output path is provided
            if output_path:
                await self._save_report_multiple_formats(report, output_path)
            
            self.logger.info(f"Instance summary report generated successfully")
            return report
            
        except Exception as e:
            self.logger.error(f"Error generating instance summary report: {str(e)}")
            raise
    
    async def _create_phase_section(
        self,
        phase_name: str,
        phase_result: PhaseResult,
        instances: List[Instance]
    ) -> ReportSection:
        """Create a report section for a workflow phase."""
        # Create instance results summary
        instance_results = {}
        
        if phase_result.instance_results:
            for instance_id, result in phase_result.instance_results.items():
                instance_results[instance_id] = {
                    'status': result.get('status', 'unknown'),
                    'message': result.get('message', ''),
                    'duration': result.get('duration', 0)
                }
        
        # Create section
        section = ReportSection(
            name=phase_name.replace('_', ' ').title(),
            status=phase_result.status.value,
            start_time=phase_result.start_time,
            end_time=phase_result.end_time,
            duration_seconds=phase_result.duration_seconds,
            instance_results=instance_results,
            errors=[{'message': error, 'timestamp': datetime.utcnow()} for error in phase_result.errors]
        )
        
        # Add phase-specific metadata
        if phase_result.metrics:
            section.metadata = {
                'instances_processed': phase_result.metrics.instances_processed,
                'successful_operations': phase_result.metrics.successful_operations,
                'failed_operations': phase_result.metrics.failed_operations,
                'average_duration': phase_result.metrics.average_duration_seconds,
                'total_duration': phase_result.metrics.total_duration_seconds
            }
        
        return section
    
    async def _create_detailed_phase_section(
        self,
        phase_name: str,
        phase_result: PhaseResult,
        instances: List[Instance]
    ) -> ReportSection:
        """Create a detailed report section for a specific phase."""
        # Create detailed instance results
        instance_results = {}
        
        for instance in instances:
            instance_id = instance.instance_id
            result_data = phase_result.instance_results.get(instance_id, {})
            
            instance_results[instance_id] = {
                'instance_name': instance.name or 'N/A',
                'platform': instance.platform.value,
                'status': result_data.get('status', 'not_processed'),
                'message': result_data.get('message', ''),
                'duration': result_data.get('duration', 0),
                'region': instance.region,
                'availability_zone': instance.availability_zone,
                'instance_type': instance.instance_type,
                'private_ip': instance.private_ip_address,
                'public_ip': instance.public_ip_address or 'N/A'
            }
        
        # Create detailed section
        section = ReportSection(
            name=f"Detailed {phase_name.replace('_', ' ').title()} Report",
            status=phase_result.status.value,
            start_time=phase_result.start_time,
            end_time=phase_result.end_time,
            duration_seconds=phase_result.duration_seconds,
            instance_results=instance_results,
            errors=[{'message': error, 'timestamp': datetime.utcnow()} for error in phase_result.errors]
        )
        
        return section
    
    def _group_instances(self, instances: List[Instance]) -> Dict[str, Dict[str, List[Instance]]]:
        """Group instances by various criteria."""
        groups = {
            'by_platform': {},
            'by_status': {},
            'by_landing_zone': {},
            'by_region': {}
        }
        
        for instance in instances:
            # Group by platform
            platform = instance.platform.value
            if platform not in groups['by_platform']:
                groups['by_platform'][platform] = []
            groups['by_platform'][platform].append(instance)
            
            # Group by status
            status = instance.status.value
            if status not in groups['by_status']:
                groups['by_status'][status] = []
            groups['by_status'][status].append(instance)
            
            # Group by landing zone
            landing_zone = getattr(instance, 'landing_zone', 'unknown')
            if landing_zone not in groups['by_landing_zone']:
                groups['by_landing_zone'][landing_zone] = []
            groups['by_landing_zone'][landing_zone].append(instance)
            
            # Group by region
            region = instance.region
            if region not in groups['by_region']:
                groups['by_region'][region] = []
            groups['by_region'][region].append(instance)
        
        return groups
    
    def _create_platform_section(self, platform_groups: Dict[str, List[Instance]]) -> ReportSection:
        """Create a section showing instances grouped by platform."""
        instance_results = {}
        
        for platform, instances in platform_groups.items():
            instance_results[platform] = {
                'count': len(instances),
                'instances': [inst.instance_id for inst in instances]
            }
        
        return ReportSection(
            name="Instances by Platform",
            status="completed",
            start_time=datetime.utcnow(),
            end_time=datetime.utcnow(),
            duration_seconds=0,
            instance_results=instance_results,
            errors=[]
        )
    
    def _create_status_section(self, status_groups: Dict[str, List[Instance]]) -> ReportSection:
        """Create a section showing instances grouped by status."""
        instance_results = {}
        
        for status, instances in status_groups.items():
            instance_results[status] = {
                'count': len(instances),
                'instances': [inst.instance_id for inst in instances]
            }
        
        return ReportSection(
            name="Instances by Status",
            status="completed",
            start_time=datetime.utcnow(),
            end_time=datetime.utcnow(),
            duration_seconds=0,
            instance_results=instance_results,
            errors=[]
        )
    
    def _create_landing_zone_section(self, lz_groups: Dict[str, List[Instance]]) -> ReportSection:
        """Create a section showing instances grouped by landing zone."""
        instance_results = {}
        
        for lz, instances in lz_groups.items():
            instance_results[lz] = {
                'count': len(instances),
                'instances': [inst.instance_id for inst in instances]
            }
        
        return ReportSection(
            name="Instances by Landing Zone",
            status="completed",
            start_time=datetime.utcnow(),
            end_time=datetime.utcnow(),
            duration_seconds=0,
            instance_results=instance_results,
            errors=[]
        )
    
    def _create_region_section(self, region_groups: Dict[str, List[Instance]]) -> ReportSection:
        """Create a section showing instances grouped by region."""
        instance_results = {}
        
        for region, instances in region_groups.items():
            instance_results[region] = {
                'count': len(instances),
                'instances': [inst.instance_id for inst in instances]
            }
        
        return ReportSection(
            name="Instances by Region",
            status="completed",
            start_time=datetime.utcnow(),
            end_time=datetime.utcnow(),
            duration_seconds=0,
            instance_results=instance_results,
            errors=[]
        )
    
    def _calculate_workflow_metrics(self, workflow_result: WorkflowResult, instances: List[Instance], phase_results: Dict[str, PhaseResult]) -> ReportMetrics:
        """Calculate overall workflow metrics."""
        total_instances = len(instances)
        total_phases = len(phase_results)
        
        successful_phases = len([pr for pr in phase_results.values() if pr.status.value == 'completed'])
        failed_phases = total_phases - successful_phases
        
        # Calculate instance success/failure based on overall workflow status
        if workflow_result.status.value == 'completed':
            successful_instances = total_instances
            failed_instances = 0
        else:
            # Count instances that had errors across all phases
            failed_instance_ids = set()
            for phase_result in phase_results.values():
                for error in phase_result.errors:
                    # Try to extract instance ID from error message
                    for instance in instances:
                        if instance.instance_id in error:
                            failed_instance_ids.add(instance.instance_id)
            
            failed_instances = len(failed_instance_ids)
            successful_instances = total_instances - failed_instances
        
        return ReportMetrics(
            total_instances=total_instances,
            successful_instances=successful_instances,
            failed_instances=failed_instances,
            total_phases=total_phases,
            successful_phases=successful_phases,
            failed_phases=failed_phases
        )
    
    def _calculate_phase_metrics(self, phase_result: PhaseResult, instances: List[Instance]) -> ReportMetrics:
        """Calculate metrics for a specific phase."""
        total_instances = len(instances)
        
        if phase_result.metrics:
            successful_instances = phase_result.metrics.successful_operations
            failed_instances = phase_result.metrics.failed_operations
        else:
            # Fallback calculation
            failed_instances = len(phase_result.errors)
            successful_instances = max(0, total_instances - failed_instances)
        
        return ReportMetrics(
            total_instances=total_instances,
            successful_instances=successful_instances,
            failed_instances=failed_instances,
            total_phases=1,
            successful_phases=1 if phase_result.status.value == 'completed' else 0,
            failed_phases=1 if phase_result.status.value == 'failed' else 0
        )
    
    def _calculate_instance_metrics(self, instances: List[Instance]) -> ReportMetrics:
        """Calculate metrics for instance discovery."""
        from core.models.instance import InstanceStatus
        
        total_instances = len(instances)
        running_instances = len([inst for inst in instances if inst.status == InstanceStatus.RUNNING])
        stopped_instances = len([inst for inst in instances if inst.status == InstanceStatus.STOPPED])
        
        return ReportMetrics(
            total_instances=total_instances,
            successful_instances=running_instances,
            failed_instances=stopped_instances,
            total_phases=1,
            successful_phases=1,
            failed_phases=0
        )
    
    async def _save_report_multiple_formats(self, report: Report, base_path: str) -> None:
        """Save report in multiple formats."""
        try:
            # Ensure directory exists
            output_dir = Path(base_path).parent
            await self.storage_service.ensure_directory_exists(str(output_dir))
            
            # Save in different formats
            formats = [
                (ReportFormat.JSON, '.json'),
                (ReportFormat.HTML, '.html'),
                (ReportFormat.CSV, '.csv')
            ]
            
            for report_format, extension in formats:
                file_path = f"{base_path}{extension}"
                await self.storage_service.save_report(report, file_path, report_format)
                self.logger.info(f"Report saved: {file_path}")
                
        except Exception as e:
            self.logger.error(f"Error saving report in multiple formats: {str(e)}")
            raise