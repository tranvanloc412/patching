"""Report service for generating comprehensive workflow reports."""

import logging
from datetime import datetime
from typing import List, Dict, Any, Optional
from pathlib import Path

from core.models.report import (
    Report,
    ReportSection,
    ReportMetrics,
    ReportType,
    ReportFormat,
)
from core.models.workflow import WorkflowResult, PhaseResult
from core.models.instance import Instance
from core.interfaces.storage_interface import IStorageService
from core.utils.logger import setup_logger


class ReportService:
    """Service for generating and managing reports."""

    def __init__(self, storage_service: IStorageService):
        self.storage_service = storage_service
        self.logger = setup_logger(__name__)

    def _handle_error(self, operation: str, error: Exception) -> None:
        """Centralized error handling and logging."""
        self.logger.error(f"Error {operation}: {str(error)}")
        raise error

    async def generate_workflow_report(
        self,
        workflow_result: WorkflowResult,
        instances: List[Instance],
        phase_results: Dict[str, PhaseResult],
        output_path: Optional[str] = None,
    ) -> Report:
        """Generate a comprehensive workflow report."""
        try:
            sections = [
                await self._create_phase_section(phase_name, phase_result, instances)
                for phase_name, phase_result in phase_results.items()
            ]

            metrics = self._calculate_workflow_metrics(
                workflow_result, instances, phase_results
            )

            report = Report(
                workflow_id=workflow_result.workflow_id,
                workflow_name=workflow_result.workflow_name,
                report_type=ReportType.WORKFLOW_SUMMARY,
                start_time=workflow_result.start_time,
                end_time=workflow_result.end_time,
                status=workflow_result.status.value,
                sections=sections,
                metrics=metrics,
            )

            if workflow_result.error_message:
                report.add_error(
                    workflow_result.error_message,
                    workflow_result.end_time or datetime.utcnow(),
                )

            if output_path:
                await self._save_report_csv_format(report, output_path)

            return report

        except Exception as e:
            self._handle_error("generating workflow report", e)

    async def generate_phase_report(
        self,
        phase_name: str,
        phase_result: PhaseResult,
        instances: List[Instance],
        output_path: Optional[str] = None,
    ) -> Report:
        """Generate a detailed report for a specific phase."""
        try:
            section = await self._create_detailed_phase_section(
                phase_name, phase_result, instances
            )
            metrics = self._calculate_phase_metrics(phase_result, instances)

            report = Report(
                workflow_id=f"phase_{phase_name}_{datetime.utcnow().strftime('%Y%m%d_%H%M%S')}",
                workflow_name=f"Phase Report: {phase_name}",
                report_type=ReportType.PHASE_DETAIL,
                start_time=phase_result.start_time,
                end_time=phase_result.end_time,
                status=phase_result.status.value,
                sections=[section],
                metrics=metrics,
            )

            for error in phase_result.errors:
                report.add_error(error, phase_result.end_time or datetime.utcnow())

            if output_path:
                await self._save_report_csv_format(report, output_path)

            return report

        except Exception as e:
            self._handle_error("generating phase report", e)

    async def generate_instance_summary_report(
        self, instances: List[Instance], output_path: Optional[str] = None
    ) -> Report:
        """Generate a summary report of all discovered instances."""
        try:
            instance_groups = self._group_instances(instances)

            sections = [
                self._create_platform_section(instance_groups["by_platform"]),
                self._create_status_section(instance_groups["by_status"]),
                self._create_region_section(instance_groups["by_region"]),
            ]

            if instance_groups["by_landing_zone"]:
                sections.append(
                    self._create_landing_zone_section(
                        instance_groups["by_landing_zone"]
                    )
                )

            metrics = self._calculate_instance_metrics(instances)

            report = Report(
                workflow_id=f"instance_summary_{datetime.utcnow().strftime('%Y%m%d_%H%M%S')}",
                workflow_name="Instance Discovery Summary",
                report_type=ReportType.INSTANCE_SUMMARY,
                start_time=datetime.utcnow(),
                end_time=datetime.utcnow(),
                status="completed",
                sections=sections,
                metrics=metrics,
            )

            if output_path:
                await self._save_report_csv_format(report, output_path)

            return report

        except Exception as e:
            self._handle_error("generating instance summary report", e)

    async def _create_phase_section(
        self, phase_name: str, phase_result: PhaseResult, instances: List[Instance]
    ) -> ReportSection:
        """Create a report section for a workflow phase."""
        instance_results = {
            instance_id: {
                "status": result.get("status", "unknown"),
                "message": result.get("message", ""),
                "duration": result.get("duration", 0),
            }
            for instance_id, result in (phase_result.instance_results or {}).items()
        }

        section = ReportSection(
            name=phase_name.replace("_", " ").title(),
            status=phase_result.status.value,
            start_time=phase_result.start_time,
            end_time=phase_result.end_time,
            duration_seconds=phase_result.duration_seconds,
            instance_results=instance_results,
            errors=[
                {"message": error, "timestamp": datetime.utcnow()}
                for error in phase_result.errors
            ],
        )

        if phase_result.metrics:
            section.metadata = {
                "instances_processed": phase_result.metrics.instances_processed,
                "successful_operations": phase_result.metrics.successful_operations,
                "failed_operations": phase_result.metrics.failed_operations,
                "average_duration": phase_result.metrics.average_duration_seconds,
                "total_duration": phase_result.metrics.total_duration_seconds,
            }

        return section

    async def _create_detailed_phase_section(
        self, phase_name: str, phase_result: PhaseResult, instances: List[Instance]
    ) -> ReportSection:
        """Create a detailed report section for a specific phase."""
        instance_results = {
            instance.instance_id: {
                "instance_name": instance.name or "N/A",
                "platform": instance.platform.value,
                "status": phase_result.instance_results.get(
                    instance.instance_id, {}
                ).get("status", "not_processed"),
                "message": phase_result.instance_results.get(
                    instance.instance_id, {}
                ).get("message", ""),
                "duration": phase_result.instance_results.get(
                    instance.instance_id, {}
                ).get("duration", 0),
                "region": instance.region,
                "availability_zone": instance.availability_zone,
                "instance_type": instance.instance_type,
                "private_ip": instance.private_ip_address,
                "public_ip": instance.public_ip_address or "N/A",
            }
            for instance in instances
        }

        return ReportSection(
            name=f"Detailed {phase_name.replace('_', ' ').title()} Report",
            status=phase_result.status.value,
            start_time=phase_result.start_time,
            end_time=phase_result.end_time,
            duration_seconds=phase_result.duration_seconds,
            instance_results=instance_results,
            errors=[
                {"message": error, "timestamp": datetime.utcnow()}
                for error in phase_result.errors
            ],
        )

    def _group_instances(
        self, instances: List[Instance]
    ) -> Dict[str, Dict[str, List[Instance]]]:
        """Group instances by various criteria."""
        from collections import defaultdict

        groups = {
            "by_platform": defaultdict(list),
            "by_status": defaultdict(list),
            "by_landing_zone": defaultdict(list),
            "by_region": defaultdict(list),
        }

        for instance in instances:
            groups["by_platform"][instance.platform.value].append(instance)
            groups["by_status"][instance.status.value].append(instance)
            groups["by_landing_zone"][
                getattr(instance, "landing_zone", "unknown")
            ].append(instance)
            groups["by_region"][instance.region].append(instance)

        return {k: dict(v) for k, v in groups.items()}

    def _create_grouping_section(
        self, name: str, groups: Dict[str, List[Instance]]
    ) -> ReportSection:
        """Create a section for instance groupings."""
        instance_results = {
            group_key: {
                "count": len(instances),
                "instances": [inst.instance_id for inst in instances],
            }
            for group_key, instances in groups.items()
        }

        return ReportSection(
            name=name,
            status="completed",
            start_time=datetime.utcnow(),
            end_time=datetime.utcnow(),
            duration_seconds=0,
            instance_results=instance_results,
            errors=[],
        )

    def _create_platform_section(
        self, platform_groups: Dict[str, List[Instance]]
    ) -> ReportSection:
        """Create a section showing instances grouped by platform."""
        return self._create_grouping_section("Instances by Platform", platform_groups)

    def _create_status_section(
        self, status_groups: Dict[str, List[Instance]]
    ) -> ReportSection:
        """Create a section showing instances grouped by status."""
        return self._create_grouping_section("Instances by Status", status_groups)

    def _create_landing_zone_section(
        self, lz_groups: Dict[str, List[Instance]]
    ) -> ReportSection:
        """Create a section showing instances grouped by landing zone."""
        return self._create_grouping_section("Instances by Landing Zone", lz_groups)

    def _create_region_section(
        self, region_groups: Dict[str, List[Instance]]
    ) -> ReportSection:
        """Create a section showing instances grouped by region."""
        return self._create_grouping_section("Instances by Region", region_groups)

    def _calculate_workflow_metrics(
        self,
        workflow_result: WorkflowResult,
        instances: List[Instance],
        phase_results: Dict[str, PhaseResult],
    ) -> ReportMetrics:
        """Calculate overall workflow metrics."""
        total_instances = len(instances)
        total_phases = len(phase_results)
        successful_phases = len(
            [pr for pr in phase_results.values() if pr.status.value == "completed"]
        )
        failed_phases = total_phases - successful_phases

        if workflow_result.status.value == "completed":
            successful_instances = total_instances
            failed_instances = 0
        else:
            failed_instance_ids = set()
            for phase_result in phase_results.values():
                for error in phase_result.errors:
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
            failed_phases=failed_phases,
        )

    def _calculate_phase_metrics(
        self, phase_result: PhaseResult, instances: List[Instance]
    ) -> ReportMetrics:
        """Calculate metrics for a specific phase."""
        total_instances = len(instances)

        if phase_result.metrics:
            successful_instances = phase_result.metrics.successful_operations
            failed_instances = phase_result.metrics.failed_operations
        else:
            failed_instances = len(phase_result.errors)
            successful_instances = max(0, total_instances - failed_instances)

        return ReportMetrics(
            total_instances=total_instances,
            successful_instances=successful_instances,
            failed_instances=failed_instances,
            total_phases=1,
            successful_phases=1 if phase_result.status.value == "completed" else 0,
            failed_phases=1 if phase_result.status.value == "failed" else 0,
        )

    def _calculate_instance_metrics(self, instances: List[Instance]) -> ReportMetrics:
        """Calculate metrics for instance discovery."""
        from core.models.instance import InstanceStatus

        total_instances = len(instances)
        running_instances = len(
            [inst for inst in instances if inst.status == InstanceStatus.RUNNING]
        )
        stopped_instances = len(
            [inst for inst in instances if inst.status == InstanceStatus.STOPPED]
        )

        return ReportMetrics(
            total_instances=total_instances,
            successful_instances=running_instances,
            failed_instances=stopped_instances,
            total_phases=1,
            successful_phases=1,
            failed_phases=0,
        )

    async def _save_report_csv_format(self, report: Report, base_path: str) -> None:
        """Save report in CSV format."""
        try:
            output_dir = Path(base_path).parent
            await self.storage_service.ensure_directory_exists(str(output_dir))
            file_path = f"{base_path}.csv"
            await self.storage_service.save_report(report, file_path, ReportFormat.CSV)
            self.logger.info(f"Report saved: {file_path}")
        except Exception as e:
            await self._handle_error("Error saving CSV report", e)
