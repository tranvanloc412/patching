#!/usr/bin/env python3
"""
Script to create AMI backup for a specific server in any configured landing zone.

Usage:
    python backup_server.py --instance-id i-1234567890abcdef0 --landing-zone cmsnonprod
    python backup_server.py --instance-id i-1234567890abcdef0 --landing-zone lz250nonprod --backup-type manual
    python backup_server.py --instance-id i-1234567890abcdef0 --landing-zone cmsnonprod --backup-type pre-patch
"""

import argparse
import asyncio
import logging
import sys
from datetime import datetime
from typing import Optional

from core.services.ami_backup_service import AMIBackupService
from core.services.config_service import ConfigService
from core.services.scanner_service import ScannerService
from core.models.ami_backup import BackupType, BackupStatus
from infrastructure.aws.ec2_client import EC2Client
from infrastructure.aws.ssm_client import SSMClient
from infrastructure.aws.session_manager import AWSSessionManager
from core.utils.logger import setup_logger


class ServerBackup:
    """Backup utility for servers in any configured landing zone."""

    def __init__(self):
        self.logger = setup_logger(__name__)
        self.config_service: Optional[ConfigService] = None
        self.scanner_service: Optional[ScannerService] = None
        self.ami_backup_service: Optional[AMIBackupService] = None
        self.session_manager: Optional[AWSSessionManager] = None
        self.ec2_client: Optional[EC2Client] = None

    async def initialize(self) -> None:
        """Initialize all required services."""
        try:
            self.logger.info("Initializing services...")
            
            # Load configuration
            self.config_service = ConfigService()
            await self.config_service.load_config()
            
            # Initialize AWS services
            self.session_manager = AWSSessionManager()
            aws_config = self.config_service.get_aws_config()
            region = aws_config.region if aws_config else "ap-southeast-2"
            self.ec2_client = EC2Client(region=region, run_mode="local")
            self.ssm_client = SSMClient(region=region, run_mode="local")
            
            # Initialize scanner service to discover instances
            self.scanner_service = ScannerService(
                config_service=self.config_service,
                ec2_client=self.ec2_client,
                ssm_client=self.ssm_client
            )
            
            # Initialize AMI backup service
            self.ami_backup_service = AMIBackupService(
                config_service=self.config_service,
                ec2_client=self.ec2_client
            )
            
            self.logger.info("Services initialized successfully")
            
        except Exception as e:
            self.logger.error(f"Failed to initialize services: {e}")
            raise

    async def find_instance(self, instance_id: str, landing_zone_name: str) -> Optional[object]:
        """Find instance in the specified landing zone."""
        try:
            self.logger.info(f"Searching for instance {instance_id} in {landing_zone_name}...")
            
            # Get landing zone configuration
            landing_zones = self.config_service.get_landing_zones()
            
            if landing_zone_name not in landing_zones:
                self.logger.error(f"{landing_zone_name} landing zone not found in configuration")
                self.logger.info(f"Available landing zones: {', '.join(landing_zones)}")
                return None
            
            # Create a simple LandingZoneConfig for the scanner
            from core.models.config import LandingZoneConfig, Environment
            aws_config = self.config_service.get_aws_config()
            region = aws_config.region if aws_config else "ap-southeast-2"
            
            target_lz_config = LandingZoneConfig(
                name=landing_zone_name,
                account_id="",  # Will be determined by scanner
                environment=Environment.NONPROD,  # Default
                enabled=True,
                tag_filters={},  # No tag filtering for direct instance lookup
                region=region
            )
            
            # Scan for the specific instance
            instances = await self.scanner_service.scan_landing_zone(target_lz_config)
            
            # Find the target instance
            target_instance = None
            for instance in instances:
                if instance.instance_id == instance_id:
                    target_instance = instance
                    break
            
            if target_instance:
                self.logger.info(f"Found instance: {target_instance.display_name} ({target_instance.instance_id})")
                self.logger.info(f"Status: {target_instance.status.value}")
                self.logger.info(f"Platform: {target_instance.platform.value}")
                self.logger.info(f"Requires backup: {target_instance.requires_backup}")
            else:
                self.logger.error(f"Instance {instance_id} not found in {landing_zone_name}")
            
            return target_instance
            
        except Exception as e:
            self.logger.error(f"Error finding instance: {e}")
            raise

    async def create_backup(self, instance_id: str, landing_zone_name: str, backup_type: BackupType = BackupType.PRE_PATCH) -> bool:
        """Create AMI backup for the specified instance."""
        try:
            # Find the instance
            instance = await self.find_instance(instance_id, landing_zone_name)
            if not instance:
                return False
            
            # Check if backup is required
            if not instance.requires_backup:
                self.logger.warning(f"Instance {instance_id} does not require backup (backup_required tag not set)")
                self.logger.info("Proceeding with backup anyway...")
            
            # Check instance status
            if not instance.is_running:
                self.logger.warning(f"Instance {instance_id} is not running (status: {instance.status.value})")
                self.logger.info("Backup can still be created for stopped instances")
            
            self.logger.info(f"Creating {backup_type.value} backup for {instance.display_name}...")
            
            # Create the backup
            backup = await self.ami_backup_service.create_backup(
                instance=instance,
                backup_type=backup_type
            )
            
            self.logger.info(f"Backup initiated successfully!")
            self.logger.info(f"Backup ID: {backup.backup_id}")
            self.logger.info(f"Initial Status: {backup.status.value}")
            
            # Monitor backup progress
            self.logger.info("Monitoring backup progress...")
            success = await self.ami_backup_service.wait_for_completion(
                backup=backup,
                timeout_minutes=60
            )
            
            if success:
                self.logger.info("\n=== BACKUP COMPLETED SUCCESSFULLY ===")
                self.logger.info(f"AMI ID: {backup.ami_id}")
                self.logger.info(f"AMI Name: {backup.ami_name}")
                self.logger.info(f"Duration: {backup.duration_minutes:.1f} minutes")
                self.logger.info(f"Created: {backup.created_at}")
                self.logger.info(f"Completed: {backup.completed_at}")
            else:
                self.logger.error("\n=== BACKUP FAILED ===")
                self.logger.error(f"Status: {backup.status.value}")
                self.logger.error(f"Error: {backup.error_message}")
            
            return success
            
        except Exception as e:
            self.logger.error(f"Error creating backup: {e}")
            return False

    async def run(self, instance_id: str, landing_zone_name: str, backup_type: BackupType = BackupType.PRE_PATCH) -> bool:
        """Run the backup process."""
        try:
            self.logger.info(f"Starting backup process for instance {instance_id}")
            self.logger.info(f"Landing Zone: {landing_zone_name}")
            self.logger.info(f"Backup Type: {backup_type.value}")
            self.logger.info(f"Timestamp: {datetime.now()}")
            
            # Initialize services
            await self.initialize()
            
            # Create backup
            success = await self.create_backup(instance_id, landing_zone_name, backup_type)
            
            if success:
                self.logger.info("Backup process completed successfully")
            else:
                self.logger.error("Backup process failed")
            
            return success
            
        except Exception as e:
            self.logger.error(f"Backup process failed: {e}")
            return False


def parse_arguments():
    """Parse command line arguments."""
    parser = argparse.ArgumentParser(
        description="Create AMI backup for a server in any configured landing zone"
    )
    
    parser.add_argument(
        "--instance-id",
        required=True,
        help="EC2 instance ID to backup (e.g., i-1234567890abcdef0)"
    )
    
    parser.add_argument(
        "--landing-zone",
        required=True,
        help="Landing zone name (e.g., cmsnonprod, lz250nonprod, fotoolspreprod)"
    )
    
    parser.add_argument(
        "--backup-type",
        choices=["pre-patch", "post-patch", "manual"],
        default="pre-patch",
        help="Type of backup to create (default: pre-patch)"
    )
    
    parser.add_argument(
        "--log-level",
        choices=["DEBUG", "INFO", "WARNING", "ERROR"],
        default="INFO",
        help="Logging level (default: INFO)"
    )
    
    return parser.parse_args()


def setup_logging(log_level: str) -> None:
    """Setup logging configuration."""
    logging.basicConfig(
        level=getattr(logging, log_level),
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
        handlers=[
            logging.StreamHandler(),
            logging.FileHandler(f'backup_{datetime.now().strftime("%Y%m%d_%H%M%S")}.log')
        ]
    )


async def main():
    """Main entry point."""
    args = parse_arguments()
    
    # Setup logging
    setup_logging(args.log_level)
    
    # Convert backup type string to enum
    backup_type_map = {
        "pre-patch": BackupType.PRE_PATCH,
        "post-patch": BackupType.POST_PATCH,
        "manual": BackupType.MANUAL
    }
    backup_type = backup_type_map[args.backup_type]
    
    # Run backup
    backup_tool = ServerBackup()
    success = await backup_tool.run(args.instance_id, args.landing_zone, backup_type)
    
    # Exit with appropriate code
    sys.exit(0 if success else 1)


if __name__ == "__main__":
    asyncio.run(main())