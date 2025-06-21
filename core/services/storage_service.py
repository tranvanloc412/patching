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
        
        for directory in [self.instances_dir, self.reports_dir, self.backups_dir, self.logs_dir]:
            self.ensure_directory_exists(str(directory))
    
    async def save_instances_to_csv(self, instances: List[Instance], file_path: str) -> bool:
        """Save instances to CSV file."""
        self.logger.info(f"Saving {len(instances)} instances to CSV: {file_path}")
        
        try:
            # Ensure directory exists
            file_path_obj = Path(file_path)
            self.ensure_directory_exists(str(file_path_obj.parent))
            
            # Define CSV headers
            headers = [
                'instance_id', 'name', 'platform', 'status', 'instance_type',
                'region', 'account_id', 'landing_zone', 'ami_id', 'launch_time',
                'private_ip', 'public_ip', 'vpc_id', 'subnet_id', 'security_groups',
                'ssm_agent_status', 'ssm_ping_status', 'ssm_last_ping',
                'cpu_cores', 'memory_gb', 'storage_gb', 'network_performance',
                'tags', 'requires_backup', 'patching_group', 'maintenance_window'
            ]
            
            # Write CSV file
            with open(file_path, 'w', newline='', encoding='utf-8') as csvfile:
                writer = csv.DictWriter(csvfile, fieldnames=headers)
                writer.writeheader()
                
                for instance in instances:
                    row = self._instance_to_csv_row(instance)
                    writer.writerow(row)
            
            self.logger.info(f"Successfully saved instances to CSV: {file_path}")
            return True
            
        except Exception as e:
            self.logger.error(f"Error saving instances to CSV: {str(e)}")
            return False
    
    async def load_instances_from_csv(self, file_path: str) -> List[Instance]:
        """Load instances from CSV file."""
        self.logger.info(f"Loading instances from CSV: {file_path}")
        
        try:
            if not Path(file_path).exists():
                self.logger.warning(f"CSV file not found: {file_path}")
                return []
            
            instances = []
            
            with open(file_path, 'r', encoding='utf-8') as csvfile:
                reader = csv.DictReader(csvfile)
                
                for row in reader:
                    try:
                        instance = self._csv_row_to_instance(row)
                        instances.append(instance)
                    except Exception as e:
                        self.logger.warning(f"Error parsing CSV row: {str(e)}")
                        continue
            
            self.logger.info(f"Successfully loaded {len(instances)} instances from CSV")
            return instances
            
        except Exception as e:
            self.logger.error(f"Error loading instances from CSV: {str(e)}")
            return []
    
    async def save_report(self, report: Report, file_path: str, format: ReportFormat = ReportFormat.JSON) -> bool:
        """Save report to file in specified format."""
        self.logger.info(f"Saving report to {format.value} format: {file_path}")
        
        try:
            # Ensure directory exists
            file_path_obj = Path(file_path)
            self.ensure_directory_exists(str(file_path_obj.parent))
            
            if format == ReportFormat.JSON:
                return await self._save_report_json(report, file_path)
            elif format == ReportFormat.CSV:
                return await self._save_report_csv(report, file_path)
            elif format == ReportFormat.HTML:
                return await self._save_report_html(report, file_path)
            elif format == ReportFormat.XML:
                return await self._save_report_xml(report, file_path)
            else:
                raise ValueError(f"Unsupported report format: {format}")
                
        except Exception as e:
            self.logger.error(f"Error saving report: {str(e)}")
            return False
    
    async def load_report(self, file_path: str, format: ReportFormat = ReportFormat.JSON) -> Optional[Report]:
        """Load report from file."""
        self.logger.info(f"Loading report from {format.value} format: {file_path}")
        
        try:
            if not Path(file_path).exists():
                self.logger.warning(f"Report file not found: {file_path}")
                return None
            
            if format == ReportFormat.JSON:
                return await self._load_report_json(file_path)
            else:
                raise ValueError(f"Loading from {format.value} format not yet supported")
                
        except Exception as e:
            self.logger.error(f"Error loading report: {str(e)}")
            return None
    
    async def create_backup(self, source_path: str, backup_name: Optional[str] = None) -> str:
        """Create a backup of a file or directory."""
        source_path_obj = Path(source_path)
        
        if not source_path_obj.exists():
            raise FileNotFoundError(f"Source path does not exist: {source_path}")
        
        # Generate backup name if not provided
        if not backup_name:
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            backup_name = f"{source_path_obj.name}_{timestamp}"
        
        backup_path = self.backups_dir / backup_name
        
        try:
            if source_path_obj.is_file():
                # Backup single file
                shutil.copy2(source_path, backup_path)
                self.logger.info(f"Created file backup: {backup_path}")
            else:
                # Backup directory
                shutil.copytree(source_path, backup_path)
                self.logger.info(f"Created directory backup: {backup_path}")
            
            return str(backup_path)
            
        except Exception as e:
            self.logger.error(f"Error creating backup: {str(e)}")
            raise
    
    async def list_files(self, directory_path: str, pattern: str = "*", recursive: bool = False) -> List[str]:
        """List files in a directory matching a pattern."""
        try:
            directory = Path(directory_path)
            
            if not directory.exists() or not directory.is_dir():
                return []
            
            if recursive:
                files = list(directory.rglob(pattern))
            else:
                files = list(directory.glob(pattern))
            
            # Filter to only files (not directories) and convert to strings
            file_paths = [str(f) for f in files if f.is_file()]
            
            return sorted(file_paths)
            
        except Exception as e:
            self.logger.warning(f"Error listing files in {directory_path}: {str(e)}")
            return []
    
    def ensure_directory_exists(self, directory_path: str) -> bool:
        """Ensure a directory exists, creating it if necessary."""
        try:
            Path(directory_path).mkdir(parents=True, exist_ok=True)
            return True
        except Exception as e:
            self.logger.error(f"Error creating directory {directory_path}: {str(e)}")
            return False
    
    async def cleanup_old_files(self, directory_path: str, max_age_days: int = 30,
                               pattern: str = "*", dry_run: bool = False) -> List[str]:
        """Clean up old files in a directory."""
        self.logger.info(f"Cleaning up files older than {max_age_days} days in {directory_path}")
        
        try:
            directory = Path(directory_path)
            
            if not directory.exists():
                return []
            
            cutoff_time = datetime.now() - timedelta(days=max_age_days)
            deleted_files = []
            
            # Find files matching pattern
            files = list(directory.glob(pattern))
            
            for file_path in files:
                if file_path.is_file():
                    # Check file modification time
                    file_mtime = datetime.fromtimestamp(file_path.stat().st_mtime)
                    
                    if file_mtime < cutoff_time:
                        if dry_run:
                            self.logger.info(f"Would delete old file: {file_path}")
                        else:
                            try:
                                file_path.unlink()
                                self.logger.info(f"Deleted old file: {file_path}")
                            except Exception as e:
                                self.logger.warning(f"Failed to delete file {file_path}: {str(e)}")
                                continue
                        
                        deleted_files.append(str(file_path))
            
            if not dry_run:
                self.logger.info(f"Cleanup complete: deleted {len(deleted_files)} files")
            else:
                self.logger.info(f"Dry run complete: would delete {len(deleted_files)} files")
            
            return deleted_files
            
        except Exception as e:
            self.logger.error(f"Error during cleanup: {str(e)}")
            return []
    
    def _instance_to_csv_row(self, instance: Instance) -> Dict[str, str]:
        """Convert Instance object to CSV row dictionary."""
        # Convert tags to JSON string
        tags_json = json.dumps(instance.tags.to_dict() if instance.tags else {})
        
        # Convert security groups list to comma-separated string
        security_groups = ",".join(instance.networking.security_groups) if instance.networking else ""
        
        return {
            'instance_id': instance.instance_id,
            'name': instance.name or '',
            'platform': instance.platform.value,
            'status': instance.status.value,
            'instance_type': instance.instance_type or '',
            'region': instance.region,
            'account_id': instance.account_id,
            'landing_zone': instance.landing_zone,
            'ami_id': instance.ami_id or '',
            'launch_time': instance.launch_time.isoformat() if instance.launch_time else '',
            'private_ip': instance.networking.private_ip if instance.networking else '',
            'public_ip': instance.networking.public_ip if instance.networking else '',
            'vpc_id': instance.networking.vpc_id if instance.networking else '',
            'subnet_id': instance.networking.subnet_id if instance.networking else '',
            'security_groups': security_groups,
            'ssm_agent_status': instance.ssm_info.agent_status if instance.ssm_info else '',
            'ssm_ping_status': instance.ssm_info.ping_status if instance.ssm_info else '',
            'ssm_last_ping': instance.ssm_info.last_ping_time.isoformat() if instance.ssm_info and instance.ssm_info.last_ping_time else '',
            'cpu_cores': str(instance.specs.cpu_cores) if instance.specs else '',
            'memory_gb': str(instance.specs.memory_gb) if instance.specs else '',
            'storage_gb': str(instance.specs.storage_gb) if instance.specs else '',
            'network_performance': instance.specs.network_performance if instance.specs else '',
            'tags': tags_json,
            'requires_backup': str(instance.requires_backup),
            'patching_group': instance.patching_group or '',
            'maintenance_window': instance.maintenance_window or ''
        }
    
    def _csv_row_to_instance(self, row: Dict[str, str]) -> Instance:
        """Convert CSV row dictionary to Instance object."""
        from core.models.instance import (
            Platform, InstanceStatus, InstanceTags, InstanceNetworking,
            InstanceSpecs, SSMInfo, SSMStatus
        )
        
        # Parse basic fields
        instance_id = row['instance_id']
        platform = Platform(row['platform'])
        status = InstanceStatus(row['status'])
        
        # Parse optional datetime fields
        launch_time = None
        if row.get('launch_time'):
            try:
                launch_time = datetime.fromisoformat(row['launch_time'])
            except ValueError:
                pass
        
        # Parse tags
        tags = None
        if row.get('tags'):
            try:
                tags_dict = json.loads(row['tags'])
                tags = InstanceTags(**tags_dict)
            except (json.JSONDecodeError, TypeError):
                pass
        
        # Parse networking
        networking = None
        if any(row.get(field) for field in ['private_ip', 'public_ip', 'vpc_id', 'subnet_id']):
            security_groups = row.get('security_groups', '').split(',') if row.get('security_groups') else []
            networking = InstanceNetworking(
                private_ip=row.get('private_ip') or None,
                public_ip=row.get('public_ip') or None,
                vpc_id=row.get('vpc_id') or None,
                subnet_id=row.get('subnet_id') or None,
                security_groups=[sg.strip() for sg in security_groups if sg.strip()]
            )
        
        # Parse specs
        specs = None
        if any(row.get(field) for field in ['cpu_cores', 'memory_gb', 'storage_gb']):
            specs = InstanceSpecs(
                cpu_cores=int(row['cpu_cores']) if row.get('cpu_cores') and row['cpu_cores'].isdigit() else 0,
                memory_gb=float(row['memory_gb']) if row.get('memory_gb') else 0.0,
                storage_gb=int(row['storage_gb']) if row.get('storage_gb') and row['storage_gb'].isdigit() else 0,
                network_performance=row.get('network_performance') or None
            )
        
        # Parse SSM info
        ssm_info = None
        if row.get('ssm_agent_status'):
            last_ping_time = None
            if row.get('ssm_last_ping'):
                try:
                    last_ping_time = datetime.fromisoformat(row['ssm_last_ping'])
                except ValueError:
                    pass
            
            ssm_info = SSMInfo(
                agent_status=SSMStatus(row['ssm_agent_status']),
                ping_status=SSMStatus(row.get('ssm_ping_status', 'Unknown')),
                last_ping_time=last_ping_time
            )
        
        # Create instance
        instance = Instance(
            instance_id=instance_id,
            name=row.get('name') or None,
            platform=platform,
            status=status,
            instance_type=row.get('instance_type') or None,
            region=row['region'],
            account_id=row['account_id'],
            landing_zone=row['landing_zone'],
            ami_id=row.get('ami_id') or None,
            launch_time=launch_time,
            tags=tags,
            networking=networking,
            specs=specs,
            ssm_info=ssm_info,
            requires_backup=row.get('requires_backup', 'False').lower() == 'true',
            patching_group=row.get('patching_group') or None,
            maintenance_window=row.get('maintenance_window') or None
        )
        
        return instance
    
    async def _save_report_json(self, report: Report, file_path: str) -> bool:
        """Save report in JSON format."""
        try:
            report_dict = report.to_dict()
            
            with open(file_path, 'w', encoding='utf-8') as f:
                json.dump(report_dict, f, indent=2, default=str)
            
            return True
        except Exception as e:
            self.logger.error(f"Error saving JSON report: {str(e)}")
            return False
    
    async def _save_report_csv(self, report: Report, file_path: str) -> bool:
        """Save report in CSV format."""
        try:
            # Create a flattened view of the report for CSV
            rows = []
            
            # Add summary information
            summary_row = {
                'type': 'summary',
                'workflow_id': report.workflow_id,
                'workflow_name': report.workflow_name,
                'start_time': report.start_time.isoformat(),
                'end_time': report.end_time.isoformat() if report.end_time else '',
                'duration_seconds': report.duration_seconds,
                'status': report.status,
                'total_instances': report.metrics.total_instances if report.metrics else 0,
                'successful_instances': report.metrics.successful_instances if report.metrics else 0,
                'failed_instances': report.metrics.failed_instances if report.metrics else 0
            }
            rows.append(summary_row)
            
            # Add section information
            for section in report.sections:
                section_row = {
                    'type': 'section',
                    'section_name': section.name,
                    'section_status': section.status,
                    'section_duration': section.duration_seconds,
                    'section_instances': len(section.instance_results),
                    'section_errors': len(section.errors)
                }
                rows.append(section_row)
            
            # Write CSV
            if rows:
                with open(file_path, 'w', newline='', encoding='utf-8') as csvfile:
                    fieldnames = rows[0].keys()
                    writer = csv.DictWriter(csvfile, fieldnames=fieldnames)
                    writer.writeheader()
                    writer.writerows(rows)
            
            return True
        except Exception as e:
            self.logger.error(f"Error saving CSV report: {str(e)}")
            return False
    
    async def _save_report_html(self, report: Report, file_path: str) -> bool:
        """Save report in HTML format."""
        try:
            html_content = self._generate_html_report(report)
            
            with open(file_path, 'w', encoding='utf-8') as f:
                f.write(html_content)
            
            return True
        except Exception as e:
            self.logger.error(f"Error saving HTML report: {str(e)}")
            return False
    
    async def _save_report_xml(self, report: Report, file_path: str) -> bool:
        """Save report in XML format."""
        try:
            xml_content = self._generate_xml_report(report)
            
            with open(file_path, 'w', encoding='utf-8') as f:
                f.write(xml_content)
            
            return True
        except Exception as e:
            self.logger.error(f"Error saving XML report: {str(e)}")
            return False
    
    async def _load_report_json(self, file_path: str) -> Report:
        """Load report from JSON format."""
        with open(file_path, 'r', encoding='utf-8') as f:
            report_dict = json.load(f)
        
        return Report.from_dict(report_dict)
    
    def _generate_html_report(self, report: Report) -> str:
        """Generate HTML report content."""
        html = f"""
<!DOCTYPE html>
<html>
<head>
    <title>Patching Workflow Report - {report.workflow_name}</title>
    <style>
        body {{ font-family: Arial, sans-serif; margin: 20px; }}
        .header {{ background-color: #f0f0f0; padding: 20px; border-radius: 5px; }}
        .section {{ margin: 20px 0; padding: 15px; border: 1px solid #ddd; border-radius: 5px; }}
        .success {{ background-color: #d4edda; }}
        .error {{ background-color: #f8d7da; }}
        .warning {{ background-color: #fff3cd; }}
        table {{ width: 100%; border-collapse: collapse; margin: 10px 0; }}
        th, td {{ border: 1px solid #ddd; padding: 8px; text-align: left; }}
        th {{ background-color: #f2f2f2; }}
    </style>
</head>
<body>
    <div class="header">
        <h1>Patching Workflow Report</h1>
        <p><strong>Workflow:</strong> {report.workflow_name}</p>
        <p><strong>ID:</strong> {report.workflow_id}</p>
        <p><strong>Status:</strong> {report.status}</p>
        <p><strong>Start Time:</strong> {report.start_time}</p>
        <p><strong>End Time:</strong> {report.end_time or 'In Progress'}</p>
        <p><strong>Duration:</strong> {report.duration_seconds} seconds</p>
    </div>
"""
        
        # Add metrics if available
        if report.metrics:
            html += f"""
    <div class="section">
        <h2>Summary Metrics</h2>
        <table>
            <tr><th>Metric</th><th>Value</th></tr>
            <tr><td>Total Instances</td><td>{report.metrics.total_instances}</td></tr>
            <tr><td>Successful</td><td>{report.metrics.successful_instances}</td></tr>
            <tr><td>Failed</td><td>{report.metrics.failed_instances}</td></tr>
            <tr><td>Success Rate</td><td>{report.metrics.success_rate:.1%}</td></tr>
        </table>
    </div>
"""
        
        # Add sections
        for section in report.sections:
            status_class = "success" if section.status == "completed" else "error" if section.status == "failed" else "warning"
            html += f"""
    <div class="section {status_class}">
        <h3>{section.name}</h3>
        <p><strong>Status:</strong> {section.status}</p>
        <p><strong>Duration:</strong> {section.duration_seconds} seconds</p>
        <p><strong>Instances:</strong> {len(section.instance_results)}</p>
        <p><strong>Errors:</strong> {len(section.errors)}</p>
    </div>
"""
        
        html += """
</body>
</html>
"""
        
        return html
    
    def _generate_xml_report(self, report: Report) -> str:
        """Generate XML report content."""
        xml = f"""<?xml version="1.0" encoding="UTF-8"?>
<report>
    <workflow_id>{report.workflow_id}</workflow_id>
    <workflow_name>{report.workflow_name}</workflow_name>
    <status>{report.status}</status>
    <start_time>{report.start_time}</start_time>
    <end_time>{report.end_time or ''}</end_time>
    <duration_seconds>{report.duration_seconds}</duration_seconds>
"""
        
        if report.metrics:
            xml += f"""
    <metrics>
        <total_instances>{report.metrics.total_instances}</total_instances>
        <successful_instances>{report.metrics.successful_instances}</successful_instances>
        <failed_instances>{report.metrics.failed_instances}</failed_instances>
        <success_rate>{report.metrics.success_rate}</success_rate>
    </metrics>
"""
        
        xml += "    <sections>\n"
        for section in report.sections:
            xml += f"""
        <section>
            <name>{section.name}</name>
            <status>{section.status}</status>
            <duration_seconds>{section.duration_seconds}</duration_seconds>
            <instance_count>{len(section.instance_results)}</instance_count>
            <error_count>{len(section.errors)}</error_count>
        </section>
"""
        xml += "    </sections>\n</report>"
        
        return xml