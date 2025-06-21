"""Report data models."""

from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Dict, Any, List, Optional, Union


class ReportType(Enum):
    """Types of reports."""
    WORKFLOW_SUMMARY = "workflow_summary"
    INSTANCE_DETAILS = "instance_details"
    ERROR_REPORT = "error_report"
    METRICS_REPORT = "metrics_report"
    COMPLIANCE_REPORT = "compliance_report"
    PERFORMANCE_REPORT = "performance_report"


class ReportFormat(Enum):
    """Report output formats."""
    JSON = "json"
    CSV = "csv"
    HTML = "html"
    PDF = "pdf"
    YAML = "yaml"
    XML = "xml"


@dataclass
class ReportMetrics:
    """Metrics data for reports."""
    
    # Instance metrics
    total_instances: int = 0
    scanned_instances: int = 0
    managed_instances: int = 0
    patchable_instances: int = 0
    
    # Platform breakdown
    windows_instances: int = 0
    linux_instances: int = 0
    
    # Status breakdown
    running_instances: int = 0
    stopped_instances: int = 0
    
    # SSM metrics
    ssm_online_instances: int = 0
    ssm_offline_instances: int = 0
    
    # Backup metrics
    backup_required_instances: int = 0
    backup_completed_instances: int = 0
    backup_failed_instances: int = 0
    
    # Operation metrics
    successful_operations: int = 0
    failed_operations: int = 0
    skipped_operations: int = 0
    
    # Timing metrics
    total_execution_time: Optional[float] = None  # seconds
    average_operation_time: Optional[float] = None  # seconds
    
    # Error metrics
    total_errors: int = 0
    total_warnings: int = 0
    
    @property
    def success_rate(self) -> float:
        """Calculate success rate percentage."""
        total_ops = self.successful_operations + self.failed_operations
        if total_ops == 0:
            return 0.0
        return (self.successful_operations / total_ops) * 100
    
    @property
    def failure_rate(self) -> float:
        """Calculate failure rate percentage."""
        total_ops = self.successful_operations + self.failed_operations
        if total_ops == 0:
            return 0.0
        return (self.failed_operations / total_ops) * 100
    
    @property
    def ssm_connectivity_rate(self) -> float:
        """Calculate SSM connectivity rate percentage."""
        total_ssm = self.ssm_online_instances + self.ssm_offline_instances
        if total_ssm == 0:
            return 0.0
        return (self.ssm_online_instances / total_ssm) * 100


@dataclass
class ReportSection:
    """A section within a report."""
    title: str
    content: Union[str, Dict[str, Any], List[Any]]
    section_type: str = "text"  # text, table, chart, metrics
    metadata: Dict[str, Any] = field(default_factory=dict)
    
    # Formatting options
    include_in_summary: bool = True
    order: int = 0
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert section to dictionary."""
        return {
            'title': self.title,
            'content': self.content,
            'section_type': self.section_type,
            'metadata': self.metadata,
            'include_in_summary': self.include_in_summary,
            'order': self.order
        }


@dataclass
class ReportError:
    """Error information for reports."""
    error_id: str
    message: str
    error_type: str
    timestamp: datetime
    phase: Optional[str] = None
    instance_id: Optional[str] = None
    landing_zone: Optional[str] = None
    details: Dict[str, Any] = field(default_factory=dict)
    severity: str = "error"  # error, warning, critical
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert error to dictionary."""
        return {
            'error_id': self.error_id,
            'message': self.message,
            'error_type': self.error_type,
            'timestamp': self.timestamp.isoformat(),
            'phase': self.phase,
            'instance_id': self.instance_id,
            'landing_zone': self.landing_zone,
            'details': self.details,
            'severity': self.severity
        }


@dataclass
class Report:
    """Comprehensive report data structure."""
    
    # Report metadata
    report_id: str
    report_type: ReportType
    title: str
    description: str = ""
    
    # Generation info
    generated_at: datetime = field(default_factory=datetime.utcnow)
    generated_by: Optional[str] = None
    workflow_id: Optional[str] = None
    
    # Report content
    sections: List[ReportSection] = field(default_factory=list)
    metrics: Optional[ReportMetrics] = None
    errors: List[ReportError] = field(default_factory=list)
    
    # Configuration
    format: ReportFormat = ReportFormat.JSON
    include_raw_data: bool = False
    include_charts: bool = False
    
    # Output information
    output_path: Optional[str] = None
    file_size_bytes: Optional[int] = None
    
    # Metadata
    metadata: Dict[str, Any] = field(default_factory=dict)
    
    def add_section(self, section: ReportSection) -> None:
        """Add a section to the report."""
        self.sections.append(section)
        # Sort sections by order
        self.sections.sort(key=lambda x: x.order)
    
    def add_error(self, error: ReportError) -> None:
        """Add an error to the report."""
        self.errors.append(error)
    
    def get_section(self, title: str) -> Optional[ReportSection]:
        """Get a section by title."""
        for section in self.sections:
            if section.title == title:
                return section
        return None
    
    def get_summary_sections(self) -> List[ReportSection]:
        """Get sections marked for inclusion in summary."""
        return [s for s in self.sections if s.include_in_summary]
    
    def get_errors_by_severity(self, severity: str) -> List[ReportError]:
        """Get errors filtered by severity."""
        return [e for e in self.errors if e.severity == severity]
    
    def get_errors_by_phase(self, phase: str) -> List[ReportError]:
        """Get errors filtered by workflow phase."""
        return [e for e in self.errors if e.phase == phase]
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert report to dictionary representation."""
        return {
            'report_id': self.report_id,
            'report_type': self.report_type.value,
            'title': self.title,
            'description': self.description,
            'generated_at': self.generated_at.isoformat(),
            'generated_by': self.generated_by,
            'workflow_id': self.workflow_id,
            'format': self.format.value,
            'sections': [s.to_dict() for s in self.sections],
            'metrics': self.metrics.__dict__ if self.metrics else None,
            'errors': [e.to_dict() for e in self.errors],
            'metadata': self.metadata,
            'output_path': self.output_path,
            'file_size_bytes': self.file_size_bytes
        }
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'Report':
        """Create report from dictionary representation."""
        # Convert enum values
        if 'report_type' in data:
            data['report_type'] = ReportType(data['report_type'])
        if 'format' in data:
            data['format'] = ReportFormat(data['format'])
        
        # Convert datetime
        if 'generated_at' in data and isinstance(data['generated_at'], str):
            data['generated_at'] = datetime.fromisoformat(data['generated_at'])
        
        # Convert sections
        if 'sections' in data:
            sections = []
            for section_data in data['sections']:
                section = ReportSection(
                    title=section_data['title'],
                    content=section_data['content'],
                    section_type=section_data.get('section_type', 'text'),
                    metadata=section_data.get('metadata', {}),
                    include_in_summary=section_data.get('include_in_summary', True),
                    order=section_data.get('order', 0)
                )
                sections.append(section)
            data['sections'] = sections
        
        # Convert metrics
        if 'metrics' in data and data['metrics']:
            data['metrics'] = ReportMetrics(**data['metrics'])
        
        # Convert errors
        if 'errors' in data:
            errors = []
            for error_data in data['errors']:
                if 'timestamp' in error_data and isinstance(error_data['timestamp'], str):
                    error_data['timestamp'] = datetime.fromisoformat(error_data['timestamp'])
                error = ReportError(**error_data)
                errors.append(error)
            data['errors'] = errors
        
        return cls(**data)
    
    def get_file_extension(self) -> str:
        """Get appropriate file extension for the report format."""
        extension_map = {
            ReportFormat.JSON: '.json',
            ReportFormat.CSV: '.csv',
            ReportFormat.HTML: '.html',
            ReportFormat.PDF: '.pdf',
            ReportFormat.YAML: '.yaml',
            ReportFormat.XML: '.xml'
        }
        return extension_map.get(self.format, '.txt')
    
    def get_mime_type(self) -> str:
        """Get MIME type for the report format."""
        mime_map = {
            ReportFormat.JSON: 'application/json',
            ReportFormat.CSV: 'text/csv',
            ReportFormat.HTML: 'text/html',
            ReportFormat.PDF: 'application/pdf',
            ReportFormat.YAML: 'application/x-yaml',
            ReportFormat.XML: 'application/xml'
        }
        return mime_map.get(self.format, 'text/plain')