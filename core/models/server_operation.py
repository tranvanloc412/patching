"""Server operation data models."""

from dataclasses import dataclass, field
from datetime import datetime, timedelta
from enum import Enum
from typing import Dict, Any, Optional, List
from uuid import uuid4


class OperationType(Enum):
    """Types of server operations."""
    START = "start"
    STOP = "stop"
    RESTART = "restart"
    REBOOT = "reboot"
    TERMINATE = "terminate"
    HEALTH_CHECK = "health_check"
    VALIDATION = "validation"
    STATUS_CHECK = "status_check"


class OperationStatus(Enum):
    """Status of server operations."""
    PENDING = "pending"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"
    TIMEOUT = "timeout"
    SKIPPED = "skipped"


class OperationPriority(Enum):
    """Priority levels for operations."""
    LOW = "low"
    NORMAL = "normal"
    HIGH = "high"
    CRITICAL = "critical"


@dataclass
class OperationContext:
    """Context information for an operation."""
    workflow_id: Optional[str] = None
    phase: Optional[str] = None
    landing_zone: Optional[str] = None
    user: Optional[str] = None
    dry_run: bool = False
    
    # Retry configuration
    max_retries: int = 3
    retry_delay: int = 5  # seconds
    current_retry: int = 0
    
    # Timeout configuration
    timeout_seconds: int = 300
    
    # Additional metadata
    metadata: Dict[str, Any] = field(default_factory=dict)


@dataclass
class OperationResult:
    """Result of a server operation."""
    
    # Operation identification
    operation_id: str = field(default_factory=lambda: str(uuid4()))
    operation_type: OperationType = OperationType.STATUS_CHECK
    instance_id: str = ""
    
    # Execution status
    status: OperationStatus = OperationStatus.PENDING
    
    # Timing information
    start_time: Optional[datetime] = None
    end_time: Optional[datetime] = None
    
    # Result data
    success: bool = False
    error_message: Optional[str] = None
    error_code: Optional[str] = None
    
    # State information
    previous_state: Optional[str] = None
    current_state: Optional[str] = None
    target_state: Optional[str] = None
    
    # Operation details
    details: Dict[str, Any] = field(default_factory=dict)
    logs: List[str] = field(default_factory=list)
    
    # Context
    context: Optional[OperationContext] = None
    
    def __post_init__(self):
        """Initialize operation result."""
        if self.start_time is None:
            self.start_time = datetime.utcnow()
    
    @property
    def duration(self) -> Optional[timedelta]:
        """Calculate operation duration."""
        if self.start_time and self.end_time:
            return self.end_time - self.start_time
        return None
    
    @property
    def is_completed(self) -> bool:
        """Check if operation completed successfully."""
        return self.status == OperationStatus.COMPLETED and self.success
    
    @property
    def is_failed(self) -> bool:
        """Check if operation failed."""
        return self.status in [OperationStatus.FAILED, OperationStatus.TIMEOUT]
    
    @property
    def is_running(self) -> bool:
        """Check if operation is currently running."""
        return self.status == OperationStatus.RUNNING
    
    @property
    def can_retry(self) -> bool:
        """Check if operation can be retried."""
        if not self.context:
            return False
        return (self.is_failed and 
                self.context.current_retry < self.context.max_retries)
    
    def add_log(self, message: str, level: str = "INFO") -> None:
        """Add a log entry."""
        timestamp = datetime.utcnow().isoformat()
        log_entry = f"[{timestamp}] {level}: {message}"
        self.logs.append(log_entry)
    
    def mark_completed(self, current_state: Optional[str] = None,
                      details: Optional[Dict[str, Any]] = None) -> None:
        """Mark operation as completed successfully."""
        self.status = OperationStatus.COMPLETED
        self.success = True
        self.end_time = datetime.utcnow()
        if current_state:
            self.current_state = current_state
        if details:
            self.details.update(details)
        self.add_log(f"Operation {self.operation_type.value} completed successfully")
    
    def mark_failed(self, error_message: str, error_code: Optional[str] = None,
                   details: Optional[Dict[str, Any]] = None) -> None:
        """Mark operation as failed."""
        self.status = OperationStatus.FAILED
        self.success = False
        self.end_time = datetime.utcnow()
        self.error_message = error_message
        self.error_code = error_code
        if details:
            self.details.update(details)
        self.add_log(f"Operation {self.operation_type.value} failed: {error_message}", "ERROR")
    
    def mark_timeout(self) -> None:
        """Mark operation as timed out."""
        self.status = OperationStatus.TIMEOUT
        self.success = False
        self.end_time = datetime.utcnow()
        self.error_message = "Operation timed out"
        self.add_log(f"Operation {self.operation_type.value} timed out", "ERROR")
    
    def mark_cancelled(self) -> None:
        """Mark operation as cancelled."""
        self.status = OperationStatus.CANCELLED
        self.success = False
        self.end_time = datetime.utcnow()
        self.add_log(f"Operation {self.operation_type.value} was cancelled", "WARNING")
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert operation result to dictionary."""
        return {
            'operation_id': self.operation_id,
            'operation_type': self.operation_type.value,
            'instance_id': self.instance_id,
            'status': self.status.value,
            'success': self.success,
            'start_time': self.start_time.isoformat() if self.start_time else None,
            'end_time': self.end_time.isoformat() if self.end_time else None,
            'duration_seconds': self.duration.total_seconds() if self.duration else None,
            'error_message': self.error_message,
            'error_code': self.error_code,
            'previous_state': self.previous_state,
            'current_state': self.current_state,
            'target_state': self.target_state,
            'details': self.details,
            'logs': self.logs,
            'context': self.context.__dict__ if self.context else None
        }


@dataclass
class ServerOperation:
    """Server operation request."""
    
    # Operation identification
    operation_id: str = field(default_factory=lambda: str(uuid4()))
    operation_type: OperationType = OperationType.STATUS_CHECK
    instance_id: str = ""
    
    # Operation configuration
    priority: OperationPriority = OperationPriority.NORMAL
    target_state: Optional[str] = None
    
    # Scheduling
    scheduled_time: Optional[datetime] = None
    created_time: datetime = field(default_factory=datetime.utcnow)
    
    # Context and configuration
    context: Optional[OperationContext] = None
    parameters: Dict[str, Any] = field(default_factory=dict)
    
    # Dependencies
    depends_on: List[str] = field(default_factory=list)  # operation IDs
    
    # Status tracking
    status: OperationStatus = OperationStatus.PENDING
    result: Optional[OperationResult] = None
    
    def __post_init__(self):
        """Initialize server operation."""
        if not self.instance_id:
            raise ValueError("instance_id is required")
        
        # Initialize context if not provided
        if self.context is None:
            self.context = OperationContext()
        
        # Set target state based on operation type
        if self.target_state is None:
            state_map = {
                OperationType.START: "running",
                OperationType.STOP: "stopped",
                OperationType.RESTART: "running",
                OperationType.REBOOT: "running"
            }
            self.target_state = state_map.get(self.operation_type)
    
    @property
    def is_ready_to_execute(self) -> bool:
        """Check if operation is ready for execution."""
        if self.status != OperationStatus.PENDING:
            return False
        
        # Check if scheduled time has passed
        if self.scheduled_time and datetime.utcnow() < self.scheduled_time:
            return False
        
        # Check dependencies (simplified - would need dependency resolver)
        return len(self.depends_on) == 0
    
    @property
    def is_completed(self) -> bool:
        """Check if operation is completed."""
        return self.status in [
            OperationStatus.COMPLETED,
            OperationStatus.FAILED,
            OperationStatus.CANCELLED,
            OperationStatus.TIMEOUT,
            OperationStatus.SKIPPED
        ]
    
    def create_result(self) -> OperationResult:
        """Create an operation result for this operation."""
        result = OperationResult(
            operation_id=self.operation_id,
            operation_type=self.operation_type,
            instance_id=self.instance_id,
            target_state=self.target_state,
            context=self.context
        )
        self.result = result
        return result
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert operation to dictionary."""
        return {
            'operation_id': self.operation_id,
            'operation_type': self.operation_type.value,
            'instance_id': self.instance_id,
            'priority': self.priority.value,
            'target_state': self.target_state,
            'scheduled_time': self.scheduled_time.isoformat() if self.scheduled_time else None,
            'created_time': self.created_time.isoformat(),
            'status': self.status.value,
            'parameters': self.parameters,
            'depends_on': self.depends_on,
            'context': self.context.__dict__ if self.context else None,
            'result': self.result.to_dict() if self.result else None
        }