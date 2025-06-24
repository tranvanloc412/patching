#!/usr/bin/env python3
"""
Demo script to create AMI backup for a server in cmsnonprod landing zone.

This script demonstrates how to:
1. Initialize the required services
2. Create a mock instance from cmsnonprod
3. Use the AMI backup service to create a backup
4. Monitor the backup progress
"""

import asyncio
import logging
from datetime import datetime
from typing import Optional

from core.services.ami_backup_service import AMIBackupService
from core.services.config_service import ConfigService
from core.models.instance import (
    Instance,
    Platform,
    InstanceStatus,
    InstanceTags,
    InstanceNetworking,
    InstanceSpecs,
    SSMInfo,
    SSMStatus
)
from core.models.ami_backup import BackupType, BackupStatus
from infrastructure.aws.ec2_client import EC2Client
from infrastructure.aws.session_manager import AWSSessionManager


class AMIBackupDemo:
    """Demo class for AMI backup operations."""

    def __init__(self):
        self.logger = logging.getLogger(__name__)
        self.config_service: Optional[ConfigService] = None
        self.ami_backup_service: Optional[AMIBackupService] = None
        self.ec2_client: Optional[EC2Client] = None

    async def initialize_services(self) -> None:
        """Initialize all required services."""
        try:
            # Initialize configuration service
            self.config_service = ConfigService()
            await self.config_service.load_config()
            
            # Initialize AWS session manager and EC2 client
            session_manager = AWSSessionManager()
            self.ec2_client = EC2Client(session_manager)
            
            # Initialize AMI backup service
            self.ami_backup_service = AMIBackupService(
                config_service=self.config_service,
                ec2_client=self.ec2_client
            )
            
            self.logger.info("Services initialized successfully")
            
        except Exception as e:
            self.logger.error(f"Failed to initialize services: {e}")
            raise

    def create_sample_instance(self) -> Instance:
        """Create a sample instance from cmsnonprod for demonstration."""
        # Create instance tags
        tags = InstanceTags(
            name="demo-server-01",
            environment="nonprod",
            application="cms",
            owner="demo-team",
            backup_required=True,
            patch_group="cms-nonprod-group",
            additional_tags={
                "Name": "demo-server-01",
                "Environment": "nonprod",
                "Application": "cms"
            }
        )
        
        # Create networking info
        networking = InstanceNetworking(
            vpc_id="vpc-12345678",
            subnet_id="subnet-87654321",
            private_ip="10.0.1.100",
            availability_zone="ap-southeast-2a",
            security_groups=["sg-12345678"]
        )
        
        # Create instance specs
        specs = InstanceSpecs(
            instance_type="t3.medium",
            cpu_cores=2,
            memory_gb=4.0,
            storage_gb=20,
            architecture="x86_64"
        )
        
        # Create SSM info
        ssm_info = SSMInfo(
            status=SSMStatus.ONLINE,
            agent_version="3.1.1732.0",
            last_ping=datetime.now(),
            platform_type="Linux",
            platform_name="Amazon Linux",
            platform_version="2",
            is_latest_version=True,
            ping_status="Online"
        )
        
        # Create the instance
        instance = Instance(
            instance_id="i-1234567890abcdef0",
            landing_zone="cmsnonprod",
            region="ap-southeast-2",
            account_id="954976297051",  # From inventory
            status=InstanceStatus.RUNNING,
            platform=Platform.LINUX,
            tags=tags,
            networking=networking,
            specs=specs,
            ssm_info=ssm_info,
            ami_id="ami-0abcdef1234567890",
            ami_name="amzn2-ami-hvm-2.0.20231116.0-x86_64-gp2",
            launch_time=datetime.now(),
            is_managed=True,
            is_patchable=True
        )
        
        self.logger.info(f"Created sample instance: {instance.display_name} ({instance.instance_id})")
        return instance

    async def create_ami_backup(self, instance: Instance) -> None:
        """Create AMI backup for the given instance."""
        try:
            self.logger.info(f"Starting AMI backup for instance: {instance.display_name}")
            
            # Create the backup
            backup = await self.ami_backup_service.create_backup(
                instance=instance,
                backup_type=BackupType.PRE_PATCH
            )
            
            self.logger.info(f"Backup initiated: {backup.backup_id}")
            self.logger.info(f"Backup status: {backup.status.value}")
            
            # Wait for backup completion (with timeout)
            self.logger.info("Waiting for backup to complete...")
            success = await self.ami_backup_service.wait_for_completion(
                backup=backup,
                timeout_minutes=30  # Reduced timeout for demo
            )
            
            if success:
                self.logger.info(f"Backup completed successfully!")
                self.logger.info(f"AMI ID: {backup.ami_id}")
                self.logger.info(f"AMI Name: {backup.ami_name}")
                self.logger.info(f"Backup Duration: {backup.duration_minutes} minutes")
            else:
                self.logger.error(f"Backup failed or timed out")
                self.logger.error(f"Error: {backup.error_message}")
                
        except Exception as e:
            self.logger.error(f"Error during backup creation: {e}")
            raise

    async def run_demo(self) -> None:
        """Run the complete AMI backup demonstration."""
        try:
            self.logger.info("=== AMI Backup Demo Started ===")
            
            # Initialize services
            await self.initialize_services()
            
            # Create sample instance
            instance = self.create_sample_instance()
            
            # Verify instance requires backup
            if not instance.requires_backup:
                self.logger.warning("Instance does not require backup (backup_required=False)")
                return
            
            # Create AMI backup
            await self.create_ami_backup(instance)
            
            self.logger.info("=== AMI Backup Demo Completed ===")
            
        except Exception as e:
            self.logger.error(f"Demo failed: {e}")
            raise


def setup_logging() -> None:
    """Setup logging configuration."""
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
        handlers=[
            logging.StreamHandler(),
            logging.FileHandler('ami_backup_demo.log')
        ]
    )


async def main() -> None:
    """Main entry point for the demo."""
    setup_logging()
    
    demo = AMIBackupDemo()
    await demo.run_demo()


if __name__ == "__main__":
    # Run the demo
    asyncio.run(main())