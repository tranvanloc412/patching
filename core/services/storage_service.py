"""Storage service implementation."""

import os
import csv
import json
import shutil
import logging
from pathlib import Path
from datetime import datetime, timedelta
from typing import List, Dict, Any, Optional, Union
from dataclasses import asdict

from core.interfaces.storage_interface import IStorageService
from core.models.instance import Instance
from core.models.report import Report, ReportFormat
from core.models.workflow import WorkflowResult


class StorageService(IStorageService):
    """Implementation of storage service."""

    def __init__(self, base_directory: str = "./data"):
        self.base_directory = Path(base_directory)
        self.logger = logging.getLogger(__name__)

        # Ensure base directory exists
        self.ensure_directory_exists(str(self.base_directory))

        # Create standard subdirectories
        self.instances_dir = self.base_directory / "instances"
        self.reports_dir = self.base_directory / "reports"
        self.backups_dir = self.base_directory / "backups"
        self.logs_dir = self.base_directory / "logs"

        for directory in [
            self.instances_dir,
            self.reports_dir,
            self.backups_dir,
            self.logs_dir,
        ]:
            self.ensure_directory_exists(str(directory))

    def _handle_error(self, message: str, exception: Exception) -> None:
        """Centralized error handling and logging."""
        self.logger.error(f"{message}: {str(exception)}")

    async def save_instances_to_csv(
        self, instances: List[Instance], file_path: str
    ) -> bool:
        """Save instances to CSV file."""
        try:
            file_path_obj = Path(file_path)
            self.ensure_directory_exists(str(file_path_obj.parent))

            headers = [
                "instance_id",
                "name",
                "platform",
                "status",
                "instance_type",
                "region",
                "account_id",
                "landing_zone",
                "ami_id",
                "launch_time",
                "private_ip",
                "public_ip",
                "vpc_id",
                "subnet_id",
                "security_groups",
                "ssm_agent_status",
                "ssm_ping_status",
                "ssm_last_ping",
                "cpu_cores",
                "memory_gb",
                "storage_gb",
                "network_performance",
                "tags",
                "requires_backup",
                "patching_group",
                "maintenance_window",
            ]

            with open(file_path, "w", newline="", encoding="utf-8") as csvfile:
                writer = csv.DictWriter(csvfile, fieldnames=headers)
                writer.writeheader()
                for instance in instances:
                    writer.writerow(self._instance_to_csv_row(instance))
            return True
        except Exception as e:
            self._handle_error(f"Error saving {len(instances)} instances to CSV", e)
            return False

    async def load_instances_from_csv(self, file_path: str) -> List[Instance]:
        """Load instances from CSV file."""
        try:
            if not Path(file_path).exists():
                return []

            instances = []
            with open(file_path, "r", encoding="utf-8") as csvfile:
                reader = csv.DictReader(csvfile)
                for row in reader:
                    try:
                        instances.append(self._csv_row_to_instance(row))
                    except Exception:
                        continue
            return instances
        except Exception as e:
            self._handle_error("Error loading instances from CSV", e)
            return []

    async def save_report(
        self, report: Report, file_path: str, format: ReportFormat = ReportFormat.CSV
    ) -> bool:
        """Save report to file in CSV format."""
        try:
            file_path_obj = Path(file_path)
            self.ensure_directory_exists(str(file_path_obj.parent))

            if format == ReportFormat.CSV:
                return await self._save_report_csv(report, file_path)
            else:
                raise ValueError(f"Only CSV format is supported. Requested: {format}")
        except Exception as e:
            self._handle_error("Error saving report", e)
            return False

    async def load_report(
        self, file_path: str, format: ReportFormat = ReportFormat.CSV
    ) -> Optional[Report]:
        """Load report from CSV file."""
        try:
            if not Path(file_path).exists():
                return None

            if format == ReportFormat.CSV:
                return await self._load_report_csv(file_path)
            else:
                raise ValueError(
                    f"Only CSV format is supported for loading. Requested: {format}"
                )
        except Exception as e:
            self._handle_error("Error loading report", e)
            return None

    async def create_backup(
        self, source_path: str, backup_name: Optional[str] = None
    ) -> str:
        """Create a backup of a file or directory."""
        source_path_obj = Path(source_path)

        if not source_path_obj.exists():
            raise FileNotFoundError(f"Source path does not exist: {source_path}")

        if not backup_name:
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            backup_name = f"{source_path_obj.name}_{timestamp}"

        backup_path = self.backups_dir / backup_name

        try:
            if source_path_obj.is_file():
                shutil.copy2(source_path, backup_path)
            else:
                shutil.copytree(source_path, backup_path)
            return str(backup_path)
        except Exception as e:
            self._handle_error("Error creating backup", e)
            raise

    async def list_files(
        self, directory_path: str, pattern: str = "*", recursive: bool = False
    ) -> List[str]:
        """List files in a directory matching a pattern."""
        try:
            directory = Path(directory_path)
            if not directory.exists() or not directory.is_dir():
                return []

            files = (
                list(directory.rglob(pattern))
                if recursive
                else list(directory.glob(pattern))
            )
            return sorted([str(f) for f in files if f.is_file()])
        except Exception as e:
            self._handle_error(f"Error listing files in {directory_path}", e)
            return []

    def ensure_directory_exists(self, directory_path: str) -> bool:
        """Ensure a directory exists, creating it if necessary."""
        try:
            Path(directory_path).mkdir(parents=True, exist_ok=True)
            return True
        except Exception as e:
            self._handle_error(f"Error creating directory {directory_path}", e)
            return False

    async def cleanup_old_files(
        self,
        directory_path: str,
        max_age_days: int = 30,
        pattern: str = "*",
        dry_run: bool = False,
    ) -> List[str]:
        """Clean up old files in a directory."""
        try:
            directory = Path(directory_path)
            if not directory.exists():
                return []

            cutoff_time = datetime.now() - timedelta(days=max_age_days)
            deleted_files = []

            for file_path in directory.glob(pattern):
                if file_path.is_file():
                    file_mtime = datetime.fromtimestamp(file_path.stat().st_mtime)
                    if file_mtime < cutoff_time:
                        if not dry_run:
                            try:
                                file_path.unlink()
                            except Exception:
                                continue
                        deleted_files.append(str(file_path))

            return deleted_files
        except Exception as e:
            self._handle_error("Error during cleanup", e)
            return []

    def _instance_to_csv_row(self, instance: Instance) -> Dict[str, str]:
        """Convert Instance object to CSV row dictionary."""
        tags_json = json.dumps(instance.tags.to_dict() if instance.tags else {})
        security_groups = (
            ",".join(instance.networking.security_groups) if instance.networking else ""
        )

        return {
            "instance_id": instance.instance_id,
            "name": instance.name or "",
            "platform": instance.platform.value,
            "status": instance.status.value,
            "instance_type": instance.instance_type or "",
            "region": instance.region,
            "account_id": instance.account_id,
            "landing_zone": instance.landing_zone,
            "ami_id": instance.ami_id or "",
            "launch_time": (
                instance.launch_time.isoformat() if instance.launch_time else ""
            ),
            "private_ip": instance.networking.private_ip if instance.networking else "",
            "public_ip": instance.networking.public_ip if instance.networking else "",
            "vpc_id": instance.networking.vpc_id if instance.networking else "",
            "subnet_id": instance.networking.subnet_id if instance.networking else "",
            "security_groups": security_groups,
            "ssm_agent_status": (
                instance.ssm_info.agent_status if instance.ssm_info else ""
            ),
            "ssm_ping_status": (
                instance.ssm_info.ping_status if instance.ssm_info else ""
            ),
            "ssm_last_ping": (
                instance.ssm_info.last_ping_time.isoformat()
                if instance.ssm_info and instance.ssm_info.last_ping_time
                else ""
            ),
            "cpu_cores": str(instance.specs.cpu_cores) if instance.specs else "",
            "memory_gb": str(instance.specs.memory_gb) if instance.specs else "",
            "storage_gb": str(instance.specs.storage_gb) if instance.specs else "",
            "network_performance": (
                instance.specs.network_performance if instance.specs else ""
            ),
            "tags": tags_json,
            "requires_backup": str(instance.requires_backup),
            "patching_group": instance.patching_group or "",
            "maintenance_window": instance.maintenance_window or "",
        }

    def _csv_row_to_instance(self, row: Dict[str, str]) -> Instance:
        """Convert CSV row dictionary to Instance object."""
        from core.models.instance import (
            Platform,
            InstanceStatus,
            InstanceTags,
            InstanceNetworking,
            InstanceSpecs,
            SSMInfo,
            SSMStatus,
        )

        instance_id = row["instance_id"]
        platform = Platform(row["platform"])
        status = InstanceStatus(row["status"])

        launch_time = None
        if row.get("launch_time"):
            try:
                launch_time = datetime.fromisoformat(row["launch_time"])
            except ValueError:
                pass

        tags = None
        if row.get("tags"):
            try:
                tags_dict = json.loads(row["tags"])
                tags = InstanceTags(**tags_dict)
            except (json.JSONDecodeError, TypeError):
                pass

        networking = None
        if any(
            row.get(field)
            for field in ["private_ip", "public_ip", "vpc_id", "subnet_id"]
        ):
            security_groups = (
                row.get("security_groups", "").split(",")
                if row.get("security_groups")
                else []
            )
            networking = InstanceNetworking(
                private_ip=row.get("private_ip") or None,
                public_ip=row.get("public_ip") or None,
                vpc_id=row.get("vpc_id") or None,
                subnet_id=row.get("subnet_id") or None,
                security_groups=[sg.strip() for sg in security_groups if sg.strip()],
            )

        specs = None
        if any(row.get(field) for field in ["cpu_cores", "memory_gb", "storage_gb"]):
            specs = InstanceSpecs(
                cpu_cores=(
                    int(row["cpu_cores"])
                    if row.get("cpu_cores") and row["cpu_cores"].isdigit()
                    else 0
                ),
                memory_gb=float(row["memory_gb"]) if row.get("memory_gb") else 0.0,
                storage_gb=(
                    int(row["storage_gb"])
                    if row.get("storage_gb") and row["storage_gb"].isdigit()
                    else 0
                ),
                network_performance=row.get("network_performance") or None,
            )

        ssm_info = None
        if row.get("ssm_agent_status"):
            last_ping_time = None
            if row.get("ssm_last_ping"):
                try:
                    last_ping_time = datetime.fromisoformat(row["ssm_last_ping"])
                except ValueError:
                    pass

            ssm_info = SSMInfo(
                agent_status=SSMStatus(row["ssm_agent_status"]),
                ping_status=SSMStatus(row.get("ssm_ping_status", "Unknown")),
                last_ping_time=last_ping_time,
            )
        instance = Instance(
            instance_id=instance_id,
            name=row.get("name") or None,
            platform=platform,
            status=status,
            instance_type=row.get("instance_type") or None,
            region=row["region"],
            account_id=row["account_id"],
            landing_zone=row["landing_zone"],
            ami_id=row.get("ami_id") or None,
            launch_time=launch_time,
            tags=tags,
            networking=networking,
            specs=specs,
            ssm_info=ssm_info,
            requires_backup=row.get("requires_backup", "False").lower() == "true",
            patching_group=row.get("patching_group") or None,
            maintenance_window=row.get("maintenance_window") or None,
        )

        return instance

    async def _save_report_csv(self, report: Report, file_path: str) -> bool:
        """Save report in CSV format."""
        try:
            rows = []

            summary_row = {
                "type": "summary",
                "workflow_id": report.workflow_id,
                "workflow_name": report.workflow_name,
                "start_time": report.start_time.isoformat(),
                "end_time": report.end_time.isoformat() if report.end_time else "",
                "duration_seconds": report.duration_seconds,
                "status": report.status,
                "total_instances": (
                    report.metrics.total_instances if report.metrics else 0
                ),
                "successful_instances": (
                    report.metrics.successful_instances if report.metrics else 0
                ),
                "failed_instances": (
                    report.metrics.failed_instances if report.metrics else 0
                ),
            }
            rows.append(summary_row)

            for section in report.sections:
                section_row = {
                    "type": "section",
                    "section_name": section.name,
                    "section_status": section.status,
                    "section_duration": section.duration_seconds,
                    "section_instances": len(section.instance_results),
                    "section_errors": len(section.errors),
                }
                rows.append(section_row)

            if rows:
                with open(file_path, "w", newline="", encoding="utf-8") as csvfile:
                    fieldnames = rows[0].keys()
                    writer = csv.DictWriter(csvfile, fieldnames=fieldnames)
                    writer.writeheader()
                    writer.writerows(rows)

            return True
        except Exception as e:
            self._handle_error("Error saving CSV report", e)
            return False

    async def _load_report_csv(self, file_path: str) -> Optional[Report]:
        """Load report from CSV format."""
        self.logger.warning(f"CSV report loading not yet implemented: {file_path}")
        return None
