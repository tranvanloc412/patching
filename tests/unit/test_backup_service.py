import pytest
from datetime import datetime
from core.models.ami_backup import AMIBackup, BackupStatus, BackupType


class TestAMIBackup:
    """Test cases for AMIBackup model."""
    
    def test_backup_initialization(self):
        """Test AMI backup initialization with defaults."""
        backup = AMIBackup(instance_id="i-123456789")
        
        # Check required fields
        assert backup.instance_id == "i-123456789"
        assert backup.status == BackupStatus.PENDING
        assert backup.backup_type == BackupType.PRE_PATCH
        
        # Check auto-generated fields
        assert backup.backup_id is not None
        assert len(backup.backup_id) > 0
        assert backup.created_time is not None
        assert isinstance(backup.created_time, datetime)
        
        # Check optional fields
        assert backup.ami_id is None
        assert backup.start_time is None
        assert backup.completion_time is None
        assert backup.error_message is None
        
        # Check defaults
        assert backup.retention_days == 30
        assert backup.region == ""
        assert backup.account_id == ""
        
        # Check generated AMI name
        assert backup.ami_name.startswith("backup-i-123456789-")
        
        # Check default tags
        assert "Name" in backup.tags
        assert "SourceInstanceId" in backup.tags
        assert "BackupType" in backup.tags
        assert "CreatedBy" in backup.tags
        assert "CreatedDate" in backup.tags
        assert backup.tags["SourceInstanceId"] == "i-123456789"
        assert backup.tags["BackupType"] == "pre_patch"
        assert backup.tags["CreatedBy"] == "PatchingWorkflow"
    
    def test_backup_lifecycle(self):
        """Test complete backup lifecycle from pending to completed."""
        backup = AMIBackup(instance_id="i-987654321")
        
        # Initial state
        assert backup.status == BackupStatus.PENDING
        assert not backup.is_in_progress
        assert not backup.is_completed
        assert not backup.is_failed
        
        # Start backup
        backup.start()
        assert backup.status == BackupStatus.CREATING
        assert backup.is_in_progress
        assert not backup.is_completed
        assert not backup.is_failed
        assert backup.start_time is not None
        assert isinstance(backup.start_time, datetime)
        
        # Complete backup
        ami_id = "ami-0123456789abcdef0"
        backup.complete(ami_id)
        assert backup.status == BackupStatus.AVAILABLE
        assert not backup.is_in_progress
        assert backup.is_completed
        assert not backup.is_failed
        assert backup.ami_id == ami_id
        assert backup.completion_time is not None
        assert isinstance(backup.completion_time, datetime)
        
        # Verify timing order
        assert backup.completion_time >= backup.start_time
        assert backup.start_time >= backup.created_time
    
    def test_backup_with_custom_values(self):
        """Test backup creation with custom values."""
        custom_tags = {"Environment": "test", "Owner": "team-a"}
        backup = AMIBackup(
            instance_id="i-custom123",
            ami_name="custom-backup-name",
            backup_type=BackupType.MANUAL,
            region="us-west-2",
            account_id="123456789012",
            retention_days=7,
            tags=custom_tags
        )
        
        assert backup.instance_id == "i-custom123"
        assert backup.ami_name == "custom-backup-name"
        assert backup.backup_type == BackupType.MANUAL
        assert backup.region == "us-west-2"
        assert backup.account_id == "123456789012"
        assert backup.retention_days == 7
        
        # Custom tags should be preserved and defaults added
        assert "Environment" in backup.tags
        assert "Owner" in backup.tags
        assert backup.tags["Environment"] == "test"
        assert backup.tags["Owner"] == "team-a"
    
    def test_backup_status_properties(self):
        """Test backup status property methods."""
        backup = AMIBackup(instance_id="i-status-test")
        
        # Test PENDING status
        backup.status = BackupStatus.PENDING
        assert not backup.is_in_progress
        assert not backup.is_completed
        assert not backup.is_failed
        
        # Test CREATING status
        backup.status = BackupStatus.CREATING
        assert backup.is_in_progress
        assert not backup.is_completed
        assert not backup.is_failed
        
        # Test AVAILABLE status
        backup.status = BackupStatus.AVAILABLE
        assert not backup.is_in_progress
        assert backup.is_completed
        assert not backup.is_failed
        
        # Test FAILED status
        backup.status = BackupStatus.FAILED
        assert not backup.is_in_progress
        assert not backup.is_completed
        assert backup.is_failed
    
    def test_backup_ami_name_generation(self):
        """Test automatic AMI name generation."""
        backup = AMIBackup(instance_id="i-nametest")
        
        # Should generate name with timestamp
        assert backup.ami_name.startswith("backup-i-nametest-")
        assert len(backup.ami_name) > len("backup-i-nametest-")
        
        # Should contain timestamp in YYYYMMDD-HHMMSS format
        timestamp_part = backup.ami_name.split("backup-i-nametest-")[1]
        assert len(timestamp_part) == 15  # YYYYMMDD-HHMMSS
        assert timestamp_part[8] == "-"  # Separator between date and time