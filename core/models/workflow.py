"""Workflow execution models."""

from dataclasses import dataclass, field
from datetime import datetime, timedelta
from enum import Enum
from typing import Dict, Any, List, Optional, Union
from uuid import uuid4


class WorkflowPhase(Enum):
    """Workflow execution phases."""
    SCANNER = "scanner"
    AMI_BACKUP = "ami_backup"
    SERVER_MANAGER = "server_manager"
    VALIDATION = "validation"
    CLEANUP = "cleanup"


class PhaseStatus(Enum):
    """Phase execution status."""
    PENDING = "pending"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    SKIPPED = "skipped"
    CANCELLED = "cancelled"


class WorkflowStatus(Enum):
    """Overall workflow status."""
    PENDING = "pending"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"
    PARTIAL_SUCCESS = "partial_success"


@dataclass
class PhaseMetrics:
    """Metrics for a workflow phase."""
    total_items: int = 0
    processed_items: int = 0
    successful_items: int = 0
    failed_items: int = 0
    skipped_items: int = 0
    
    start_time: Optional[datetime] = None
    end_time: Optional[datetime] = None
    
    @property
    def duration(self) -> Optional[timedelta]:
        """Calculate phase duration."""
        if self.start_time and self.end_time:
            return self.end_time - self.start_time
        return None
    
    @property
    def success_rate(self) -> float:
        """Calculate success rate as percentage."""
        if self.processed_items == 0:
            return 0.0
        return (self.successful_items / self.processed_items) * 100
    
    @property
    def failure_rate(self) -> float:
        """Calculate failure rate as percentage."""
        if self.processed_items == 0:
            return 0.0
        return (self.failed_items / self.processed_items) * 100
    
    @property
    def progress_percentage(self) -> float:
        """Calculate progress as percentage."""
        if self.total_items == 0:
            return 100.0
        return (self.processed_items / self.total_items) * 100


@dataclass
class PhaseResult:
    """Result of a workflow phase execution."""
    phase: WorkflowPhase
    status: PhaseStatus
    metrics: PhaseMetrics = field(default_factory=PhaseMetrics)
    
    # Execution details
    start_time: Optional[datetime] = None
    end_time: Optional[datetime] = None
    error_message: Optional[str] = None
    
    # Results data
    results: Dict[str, Any] = field(default_factory=dict)
    errors: List[Dict[str, Any]] = field(default_factory=list)
    warnings: List[Dict[str, Any]] = field(default_factory=list)
    
    # Output files
    output_files: List[str] = field(default_factory=list)
    
    def __post_init__(self):
        """Set start time if not provided."""
        if self.start_time is None and self.status == PhaseStatus.RUNNING:
            self.start_time = datetime.utcnow()
    
    @property
    def duration(self) -> Optional[timedelta]:
        """Calculate phase duration."""
        if self.start_time and self.end_time:
            return self.end_time - self.start_time
        return None
    
    @property
    def is_successful(self) -> bool:
        """Check if phase completed successfully."""
        return self.status == PhaseStatus.COMPLETED
    
    @property
    def is_failed(self) -> bool:
        """Check if phase failed."""
        return self.status == PhaseStatus.FAILED
    
    @property
    def is_running(self) -> bool:
        """Check if phase is currently running."""
        return self.status == PhaseStatus.RUNNING
    
    def add_error(self, error: str, details: Optional[Dict[str, Any]] = None) -> None:
        """Add an error to the phase result."""
        error_entry = {
            'message': error,
            'timestamp': datetime.utcnow().isoformat(),
            'details': details or {}
        }
        self.errors.append(error_entry)
    
    def add_warning(self, warning: str, details: Optional[Dict[str, Any]] = None) -> None:
        """Add a warning to the phase result."""
        warning_entry = {
            'message': warning,
            'timestamp': datetime.utcnow().isoformat(),
            'details': details or {}
        }
        self.warnings.append(warning_entry)
    
    def mark_completed(self, results: Optional[Dict[str, Any]] = None) -> None:
        """Mark phase as completed."""
        self.status = PhaseStatus.COMPLETED
        self.end_time = datetime.utcnow()
        if results:
            self.results.update(results)
    
    def mark_failed(self, error: str, details: Optional[Dict[str, Any]] = None) -> None:
        """Mark phase as failed."""
        self.status = PhaseStatus.FAILED
        self.end_time = datetime.utcnow()
        self.error_message = error
        self.add_error(error, details)


@dataclass
class WorkflowContext:
    """Context information for workflow execution."""
    workflow_id: str = field(default_factory=lambda: str(uuid4()))
    user: Optional[str] = None
    environment: Optional[str] = None
    dry_run: bool = False
    
    # Configuration
    config_file: Optional[str] = None
    landing_zones: List[str] = field(default_factory=list)
    
    # Skip options
    skip_scanner: bool = False
    skip_ami_backup: bool = False
    skip_server_manager: bool = False
    skip_validation: bool = False
    
    # Runtime options
    max_parallel_operations: int = 10
    timeout_minutes: int = 120
    
    # Metadata
    metadata: Dict[str, Any] = field(default_factory=dict)


@dataclass
class WorkflowResult:
    """Complete workflow execution result."""
    
    # Workflow identification
    workflow_id: str
    workflow_name: str = "Pre-Patch Workflow"
    
    # Execution status
    status: WorkflowStatus = WorkflowStatus.PENDING
    
    # Timing
    start_time: Optional[datetime] = None
    end_time: Optional[datetime] = None
    
    # Phase results
    phase_results: Dict[WorkflowPhase, PhaseResult] = field(default_factory=dict)
    
    # Overall metrics
    total_instances: int = 0
    successful_instances: int = 0
    failed_instances: int = 0
    skipped_instances: int = 0
    
    # Landing zone results
    landing_zone_results: Dict[str, Dict[str, Any]] = field(default_factory=dict)
    
    # Error tracking
    errors: List[Dict[str, Any]] = field(default_factory=list)
    warnings: List[Dict[str, Any]] = field(default_factory=list)
    
    # Output artifacts
    output_files: List[str] = field(default_factory=list)
    reports: List[str] = field(default_factory=list)
    
    # Context
    context: Optional[WorkflowContext] = None
    
    def __post_init__(self):
        """Initialize workflow result."""
        if self.start_time is None:
            self.start_time = datetime.utcnow()
    
    @property
    def duration(self) -> Optional[timedelta]:
        """Calculate total workflow duration."""
        if self.start_time and self.end_time:
            return self.end_time - self.start_time
        return None
    
    @property
    def is_successful(self) -> bool:
        """Check if workflow completed successfully."""
        return self.status == WorkflowStatus.COMPLETED
    
    @property
    def is_failed(self) -> bool:
        """Check if workflow failed."""
        return self.status == WorkflowStatus.FAILED
    
    @property
    def is_running(self) -> bool:
        """Check if workflow is currently running."""
        return self.status == WorkflowStatus.RUNNING
    
    @property
    def success_rate(self) -> float:
        """Calculate overall success rate."""
        if self.total_instances == 0:
            return 0.0
        return (self.successful_instances / self.total_instances) * 100
    
    @property
    def failure_rate(self) -> float:
        """Calculate overall failure rate."""
        if self.total_instances == 0:
            return 0.0
        return (self.failed_instances / self.total_instances) * 100
    
    def get_phase_result(self, phase: WorkflowPhase) -> Optional[PhaseResult]:
        """Get result for a specific phase."""
        return self.phase_results.get(phase)
    
    def add_phase_result(self, phase_result: PhaseResult) -> None:
        """Add a phase result."""
        self.phase_results[phase_result.phase] = phase_result
    
    def add_error(self, error: str, phase: Optional[WorkflowPhase] = None,
                 details: Optional[Dict[str, Any]] = None) -> None:
        """Add an error to the workflow result."""
        error_entry = {
            'message': error,
            'phase': phase.value if phase else None,
            'timestamp': datetime.utcnow().isoformat(),
            'details': details or {}
        }
        self.errors.append(error_entry)
    
    def add_warning(self, warning: str, phase: Optional[WorkflowPhase] = None,
                   details: Optional[Dict[str, Any]] = None) -> None:
        """Add a warning to the workflow result."""
        warning_entry = {
            'message': warning,
            'phase': phase.value if phase else None,
            'timestamp': datetime.utcnow().isoformat(),
            'details': details or {}
        }
        self.warnings.append(warning_entry)
    
    def mark_completed(self) -> None:
        """Mark workflow as completed."""
        self.status = WorkflowStatus.COMPLETED
        self.end_time = datetime.utcnow()
    
    def mark_failed(self, error: str, details: Optional[Dict[str, Any]] = None) -> None:
        """Mark workflow as failed."""
        self.status = WorkflowStatus.FAILED
        self.end_time = datetime.utcnow()
        self.add_error(error, details=details)
    
    def mark_partial_success(self) -> None:
        """Mark workflow as partially successful."""
        self.status = WorkflowStatus.PARTIAL_SUCCESS
        self.end_time = datetime.utcnow()
    
    def get_summary(self) -> Dict[str, Any]:
        """Get workflow execution summary."""
        return {
            'workflow_id': self.workflow_id,
            'workflow_name': self.workflow_name,
            'status': self.status.value,
            'duration': str(self.duration) if self.duration else None,
            'total_instances': self.total_instances,
            'successful_instances': self.successful_instances,
            'failed_instances': self.failed_instances,
            'skipped_instances': self.skipped_instances,
            'success_rate': round(self.success_rate, 2),
            'failure_rate': round(self.failure_rate, 2),
            'phases_completed': len([p for p in self.phase_results.values() if p.is_successful]),
            'phases_failed': len([p for p in self.phase_results.values() if p.is_failed]),
            'total_errors': len(self.errors),
            'total_warnings': len(self.warnings),
            'output_files': len(self.output_files),
            'reports_generated': len(self.reports)
        }