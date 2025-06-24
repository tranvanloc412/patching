from dataclasses import dataclass, field
from datetime import datetime, timedelta
from enum import Enum
from typing import Dict, List, Optional, Any
from uuid import uuid4


class WorkflowPhase(Enum):
    """Workflow execution phases."""
    SCANNER = "scanner"
    AMI_BACKUP = "ami_backup"
    SERVER_MANAGER = "server_manager"
    VALIDATION = "validation"


class PhaseStatus(Enum):
    """Phase execution status."""
    PENDING = "pending"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    SKIPPED = "skipped"


class WorkflowStatus(Enum):
    """Overall workflow status."""
    PENDING = "pending"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    PARTIAL_SUCCESS = "partial_success"


@dataclass
class PhaseResult:
    """Result of a workflow phase execution."""
    phase: WorkflowPhase
    status: PhaseStatus = PhaseStatus.PENDING
    
    # Timing
    start_time: Optional[datetime] = None
    end_time: Optional[datetime] = None
    
    # Basic metrics
    total_items: int = 0
    successful_items: int = 0
    failed_items: int = 0
    
    # Error tracking
    error_message: Optional[str] = None
    errors: List[str] = field(default_factory=list)
    
    # Results
    results: Dict[str, Any] = field(default_factory=dict)
    
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
    
    def mark_started(self) -> None:
        """Mark phase as started."""
        self.status = PhaseStatus.RUNNING
        self.start_time = datetime.utcnow()
    
    def mark_completed(self, results: Optional[Dict[str, Any]] = None) -> None:
        """Mark phase as completed."""
        self.status = PhaseStatus.COMPLETED
        self.end_time = datetime.utcnow()
        if results:
            self.results.update(results)
    
    def mark_failed(self, error: str) -> None:
        """Mark phase as failed."""
        self.status = PhaseStatus.FAILED
        self.end_time = datetime.utcnow()
        self.error_message = error
        self.errors.append(error)
    
    def mark_skipped(self, reason: str = "Skipped by configuration") -> None:
        """Mark phase as skipped."""
        self.status = PhaseStatus.SKIPPED
        self.end_time = datetime.utcnow()
        self.error_message = reason


@dataclass
class WorkflowResult:
    """Complete workflow execution result."""
    
    # Basic identification
    workflow_id: str = field(default_factory=lambda: str(uuid4()))
    workflow_name: str = "Pre-Patch Workflow"
    
    # Status and timing
    status: WorkflowStatus = WorkflowStatus.PENDING
    start_time: Optional[datetime] = None
    end_time: Optional[datetime] = None
    
    # Phase results
    phase_results: Dict[WorkflowPhase, PhaseResult] = field(default_factory=dict)
    
    # Overall metrics
    total_instances: int = 0
    successful_instances: int = 0
    failed_instances: int = 0
    
    # Error tracking
    errors: List[str] = field(default_factory=list)
    
    # Output files
    output_files: List[str] = field(default_factory=list)
    
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
    def success_rate(self) -> float:
        """Calculate overall success rate."""
        if self.total_instances == 0:
            return 0.0
        return (self.successful_instances / self.total_instances) * 100
    
    def get_phase_result(self, phase: WorkflowPhase) -> Optional[PhaseResult]:
        """Get result for a specific phase."""
        return self.phase_results.get(phase)
    
    def add_phase_result(self, phase_result: PhaseResult) -> None:
        """Add a phase result."""
        self.phase_results[phase_result.phase] = phase_result
    
    def add_error(self, error: str) -> None:
        """Add an error to the workflow result."""
        self.errors.append(error)
    
    def mark_started(self) -> None:
        """Mark workflow as started."""
        self.status = WorkflowStatus.RUNNING
        if self.start_time is None:
            self.start_time = datetime.utcnow()
    
    def mark_completed(self) -> None:
        """Mark workflow as completed."""
        self.status = WorkflowStatus.COMPLETED
        self.end_time = datetime.utcnow()
    
    def mark_failed(self, error: str) -> None:
        """Mark workflow as failed."""
        self.status = WorkflowStatus.FAILED
        self.end_time = datetime.utcnow()
        self.add_error(error)
    
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
            'success_rate': round(self.success_rate, 2),
            'phases_completed': len([p for p in self.phase_results.values() if p.is_successful]),
            'phases_failed': len([p for p in self.phase_results.values() if p.is_failed]),
            'total_errors': len(self.errors),
            'output_files': len(self.output_files)
        }