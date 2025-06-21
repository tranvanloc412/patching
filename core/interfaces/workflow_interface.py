"""Workflow orchestrator interface."""

from abc import ABC, abstractmethod
from typing import Dict, Any, Optional, List
from enum import Enum
from core.models.workflow import WorkflowResult, WorkflowPhase
from core.models.config import WorkflowConfig


class WorkflowStatus(Enum):
    """Workflow execution status."""
    PENDING = "pending"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"


class IWorkflowOrchestrator(ABC):
    """Interface for workflow orchestration."""
    
    @abstractmethod
    async def run_complete_workflow(self, config: WorkflowConfig,
                                   skip_scanner: bool = False,
                                   skip_ami_backup: bool = False,
                                   skip_start_servers: bool = False,
                                   skip_validation: bool = False) -> WorkflowResult:
        """Run the complete pre-patch workflow.
        
        Args:
            config: Workflow configuration
            skip_scanner: Skip the scanner phase
            skip_ami_backup: Skip AMI backup phase
            skip_start_servers: Skip server start phase
            skip_validation: Skip validation phase
            
        Returns:
            WorkflowResult with execution details
        """
        pass
    
    @abstractmethod
    async def run_scanner_only(self, config: WorkflowConfig) -> WorkflowResult:
        """Run only the scanner phase.
        
        Args:
            config: Workflow configuration
            
        Returns:
            WorkflowResult with scanner execution details
        """
        pass
    
    @abstractmethod
    async def run_phase(self, phase: WorkflowPhase, 
                       config: WorkflowConfig) -> WorkflowResult:
        """Run a specific workflow phase.
        
        Args:
            phase: The workflow phase to run
            config: Workflow configuration
            
        Returns:
            WorkflowResult with phase execution details
        """
        pass
    
    @abstractmethod
    async def get_workflow_status(self, workflow_id: str) -> WorkflowStatus:
        """Get the status of a running workflow.
        
        Args:
            workflow_id: Unique workflow identifier
            
        Returns:
            Current workflow status
        """
        pass
    
    @abstractmethod
    async def cancel_workflow(self, workflow_id: str) -> bool:
        """Cancel a running workflow.
        
        Args:
            workflow_id: Unique workflow identifier
            
        Returns:
            True if successfully cancelled
        """
        pass
    
    @abstractmethod
    async def get_workflow_progress(self, workflow_id: str) -> Dict[str, Any]:
        """Get detailed progress information for a workflow.
        
        Args:
            workflow_id: Unique workflow identifier
            
        Returns:
            Dictionary with progress details
        """
        pass
    
    @abstractmethod
    async def list_active_workflows(self) -> List[Dict[str, Any]]:
        """List all currently active workflows.
        
        Returns:
            List of active workflow information
        """
        pass
    
    @abstractmethod
    async def validate_workflow_config(self, config: WorkflowConfig) -> bool:
        """Validate workflow configuration before execution.
        
        Args:
            config: Workflow configuration to validate
            
        Returns:
            True if valid, raises exception if invalid
            
        Raises:
            ValidationError: If configuration is invalid
        """
        pass