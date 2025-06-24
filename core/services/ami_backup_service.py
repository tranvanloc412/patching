"""AMI backup service implementation."""

import asyncio
import logging
from datetime import datetime, timedelta
from typing import List, Dict, Any, Optional

from core.interfaces.ami_backup_interface import IAMIBackupService
from core.interfaces.config_interface import IConfigService
from core.models.instance import Instance
from core.models.ami_backup import (
    AMIBackup,
    BackupStatus,
    BackupType,
)
from infrastructure.aws.ec2_client import EC2Client


class AMIBackupService(IAMIBackupService):
    """Implementation of AMI backup service."""

    def __init__(self, config_service: IConfigService, ec2_client: EC2Client):
        self.config_service = config_service
        self.ec2_client = ec2_client
        self.logger = logging.getLogger(__name__)
        self._active_backups: Dict[str, AMIBackup] = {}

    def _handle_error(self, operation: str, error: Exception) -> None:
        """Centralized error handling and logging."""
        self.logger.error(f"Error {operation}: {str(error)}")
        raise error

    async def create_backup(
        self, instance: Instance, backup_type: BackupType = BackupType.PRE_PATCH
    ) -> AMIBackup:
        """Create an AMI backup for a single instance."""
        try:
            backup_config = self._get_backup_configuration()

            backup = AMIBackup(
                instance_id=instance.instance_id,
                backup_type=backup_type,
                region=instance.region,
                account_id=instance.account_id,
            )

            self.ec2_client.configure_for_region(instance.region)
            await self._execute_backup(backup, instance)

            self._active_backups[backup.backup_id] = backup
            return backup

        except Exception as e:
            self._handle_error(
                f"creating backup for instance {instance.instance_id}", e
            )

    async def create_multiple_backups(
        self,
        instances: List[Instance],
        backup_type: BackupType = BackupType.PRE_PATCH,
        max_concurrent: int = 10,
    ) -> List[AMIBackup]:
        """Create AMI backups for multiple instances concurrently."""
        instances_to_backup = [inst for inst in instances if inst.requires_backup]

        if not instances_to_backup:
            return []

        semaphore = asyncio.Semaphore(max_concurrent)

        async def create_backup_with_semaphore(instance: Instance) -> AMIBackup:
            async with semaphore:
                return await self.create_backup(instance, backup_type)

        tasks = [
            create_backup_with_semaphore(instance) for instance in instances_to_backup
        ]
        results = await asyncio.gather(*tasks, return_exceptions=True)

        backups = []
        for i, result in enumerate(results):
            if isinstance(result, Exception):
                instance = instances_to_backup[i]
                failed_backup = AMIBackup(
                    instance_id=instance.instance_id,
                    backup_type=backup_type,
                    region=instance.region,
                    account_id=instance.account_id,
                )
                failed_backup.mark_failed(str(result))
                backups.append(failed_backup)
            else:
                backups.append(result)

        return backups

    async def wait_for_completion(
        self, backup: AMIBackup, timeout_minutes: int = 60
    ) -> bool:
        """Wait for a backup to complete."""
        timeout_time = datetime.utcnow() + timedelta(minutes=timeout_minutes)
        check_interval = 30
        iteration = 0

        while datetime.utcnow() < timeout_time:
            try:
                iteration += 1
                self.logger.info(f"Monitoring iteration {iteration} for backup {backup.backup_id}")
                
                status = await self.get_backup_status(backup)
                self.logger.info(f"Current backup status: {status}")

                if status == BackupStatus.AVAILABLE:
                    self.logger.info("Backup completed successfully")
                    return True
                elif status == BackupStatus.FAILED:
                    self.logger.info(f"Backup failed with status: {status}")
                    return False

                self.logger.info("Updating backup progress...")
                await self._update_backup_progress(backup)
                self.logger.info(f"Sleeping for {check_interval} seconds...")
                await asyncio.sleep(check_interval)

            except Exception as e:
                self.logger.error(f"Error during backup monitoring iteration {iteration}: {str(e)}")
                self.logger.error(f"Exception type: {type(e).__name__}")
                import traceback
                self.logger.error(f"Traceback: {traceback.format_exc()}")
                await asyncio.sleep(check_interval)

        backup.mark_failed("Backup operation timed out")
        return False

    async def get_backup_status(self, backup: AMIBackup) -> BackupStatus:
        """Get the current status of a backup."""
        if not backup.ami_id:
            return backup.status

        try:
            await self.ec2_client.configure_for_region(backup.region)
            ami_images = await self.ec2_client.describe_images(image_ids=[backup.ami_id])
            ami_info = ami_images[0] if ami_images else None

            if ami_info:
                aws_state = ami_info.get("State", "unknown")

                if aws_state == "available":
                    if backup.status != BackupStatus.AVAILABLE:
                        backup.mark_completed(backup.ami_id)
                    return BackupStatus.AVAILABLE
                elif aws_state == "pending":
                    backup.status = BackupStatus.CREATING
                    return BackupStatus.CREATING
                elif aws_state in ["failed", "error"]:
                    if backup.status != BackupStatus.FAILED:
                        backup.mark_failed(
                            f"AMI creation failed with state: {aws_state}"
                        )
                    return BackupStatus.FAILED
                else:
                    backup.status = BackupStatus.CREATING
                    return BackupStatus.CREATING
            else:
                if backup.status == BackupStatus.CREATING:
                    backup.mark_failed("AMI not found in AWS")
                return BackupStatus.FAILED

        except Exception as e:
            return backup.status

    async def cleanup_old_backups(
        self,
        instance_id: str,
        region: str,
        max_age_days: int = 30,
        max_backups: int = 5,
    ) -> List[str]:
        """Clean up old backups for an instance."""
        try:
            await self.ec2_client.configure_for_region(region)
            backups = await self._find_instance_backups(instance_id)

            if not backups:
                return []

            backups.sort(key=lambda x: x.get("CreationDate", ""), reverse=True)

            deleted_amis = []
            cutoff_date = datetime.utcnow() - timedelta(days=max_age_days)

            for i, backup in enumerate(backups):
                ami_id = backup["ImageId"]
                creation_date = backup.get("CreationDate")

                should_delete = i >= max_backups or (
                    creation_date
                    and isinstance(creation_date, datetime)
                    and creation_date < cutoff_date
                )

                if should_delete:
                    try:
                        await self.ec2_client.deregister_ami(ami_id)
                        deleted_amis.append(ami_id)
                    except Exception:
                        pass

            return deleted_amis

        except Exception as e:
            self._handle_error(f"cleaning up backups for instance {instance_id}", e)

    async def list_instance_backups(
        self, instance_id: str, region: str
    ) -> List[Dict[str, Any]]:
        """List all backups for a specific instance."""
        try:
            await self.ec2_client.configure_for_region(region)
            backups = await self._find_instance_backups(instance_id)

            backup_list = [
                {
                    "ami_id": backup["ImageId"],
                    "name": backup.get("Name", ""),
                    "description": backup.get("Description", ""),
                    "creation_date": backup.get("CreationDate"),
                    "state": backup.get("State", "unknown"),
                    "tags": {
                        tag["Key"]: tag["Value"] for tag in backup.get("Tags", [])
                    },
                }
                for backup in backups
            ]

            backup_list.sort(key=lambda x: x.get("creation_date", ""), reverse=True)
            return backup_list

        except Exception as e:
            self._handle_error(f"listing backups for instance {instance_id}", e)

    def _get_backup_configuration(self) -> Dict[str, Any]:
        """Get backup configuration from config service."""
        backup_config = self.config_service.get_phase_config("ami_backup")

        return {
            "no_reboot": backup_config.get("no_reboot", True),
            "include_all_volumes": backup_config.get("include_all_volumes", True),
            "copy_tags": backup_config.get("copy_tags", True),
            "description_template": backup_config.get(
                "description_template",
                "Pre-patch backup for {instance_id} - {timestamp}",
            ),
            "retention_days": backup_config.get("retention_days", 30),
            "max_backups_per_instance": backup_config.get("max_backups_per_instance", 5),
            "additional_tags": backup_config.get("backup_tags", {}),
            "timeout_minutes": backup_config.get("timeout_minutes", 60),
            "retry_attempts": backup_config.get("retry_attempts", 2),
            "retry_delay_minutes": backup_config.get("retry_delay", 5),
        }

    async def _execute_backup(self, backup: AMIBackup, instance: Instance) -> None:
        """Execute the actual backup creation."""
        try:
            backup.mark_started()

            backup_params = {
                "instance_id": instance.instance_id,
                "name": backup.ami_name,
                "description": backup.description,
                "no_reboot": backup.configuration.get("no_reboot", True),
            }

            response = await self.ec2_client.create_image(**backup_params)

            ami_id = response.get("ami_id")
            if not ami_id:
                raise Exception("No AMI ID returned from create_image call")

            backup.ami_id = ami_id
            backup.update_progress(50.0, "ami_created")

        except Exception as e:
            backup.mark_failed(f"Failed to create AMI: {str(e)}")
            raise

    async def _update_backup_progress(self, backup: AMIBackup) -> None:
        """Update backup progress based on current status."""
        try:
            if backup.ami_id:
                ami_images = await self.ec2_client.describe_images(image_ids=[backup.ami_id])

                if ami_images and len(ami_images) > 0:
                    ami_info = ami_images[0]
                    state = ami_info.get("State", "unknown")

                    if state == "pending" and backup.start_time:
                        elapsed = datetime.utcnow() - backup.start_time
                        estimated_total = timedelta(minutes=20)
                        progress = min(
                            90.0,
                            (elapsed.total_seconds() / estimated_total.total_seconds())
                            * 90,
                        )
                        backup.update_progress(progress, "creating")
                    elif state == "available":
                        backup.mark_completed(backup.ami_id)
                    elif state in ["failed", "error"]:
                        backup.mark_failed(f"AMI creation failed with state: {state}")

        except Exception:
            pass

    async def _find_instance_backups(self, instance_id: str) -> List[Dict[str, Any]]:
        """Find all backup AMIs for a specific instance."""
        try:
            filters = [
                {"Name": "tag:SourceInstanceId", "Values": [instance_id]},
                {"Name": "tag:Purpose", "Values": ["PrePatchBackup", "Backup"]},
                {"Name": "state", "Values": ["available", "pending"]},
            ]

            return await self.ec2_client.describe_images(
                owners=["self"], filters=filters
            )

        except Exception:
            return []

    async def get_active_backups(self) -> Dict[str, AMIBackup]:
        """Get all currently active backups."""
        return self._active_backups.copy()

    async def remove_active_backup(self, backup_id: str) -> None:
        """Remove a backup from active tracking."""
        self._active_backups.pop(backup_id, None)
    
    async def list_backups_for_instance(self, instance_id: str) -> List[AMIBackup]:
        """List all AMI backups for a specific instance.
        
        Args:
            instance_id: The instance ID
            
        Returns:
            List of AMIBackup objects
        """
        try:
            # Get AMIs created from this instance
            response = await self.ec2_client.describe_images(
                filters=[
                    {'Name': 'tag:SourceInstanceId', 'Values': [instance_id]},
                    {'Name': 'state', 'Values': ['available', 'pending']}
                ]
            )
            
            backups = []
            for image in response.get('Images', []):
                # Extract backup info from tags
                tags = {tag['Key']: tag['Value'] for tag in image.get('Tags', [])}
                
                backup = AMIBackup(
                    instance_id=instance_id,
                    backup_type=BackupType(tags.get('BackupType', 'manual')),
                    region=image.get('Region', 'unknown'),
                    account_id=image.get('OwnerId', ''),
                    ami_id=image['ImageId'],
                    ami_name=image['Name'],
                    status=BackupStatus.AVAILABLE if image['State'] == 'available' else BackupStatus.CREATING,
                )
                backups.append(backup)
            
            return backups
            
        except Exception as e:
            self._handle_error("listing backups for instance", e)
            return []
    
    async def wait_for_backup_completion(self, ami_id: str, timeout_seconds: int = 1800) -> bool:
        """Wait for an AMI backup to complete.
        
        Args:
            ami_id: The AMI ID to monitor
            timeout_seconds: Maximum time to wait
            
        Returns:
            True if backup completed successfully, False if timeout or failed
        """
        try:
            start_time = datetime.now()
            timeout_delta = timedelta(seconds=timeout_seconds)
            
            while datetime.now() - start_time < timeout_delta:
                status = await self.get_backup_status(ami_id)
                
                if status == 'available':
                    self.logger.info(f"AMI {ami_id} backup completed successfully")
                    return True
                elif status in ['failed', 'error']:
                    self.logger.error(f"AMI {ami_id} backup failed")
                    return False
                
                # Wait before checking again
                await asyncio.sleep(30)
            
            self.logger.warning(f"AMI {ami_id} backup timed out after {timeout_seconds} seconds")
            return False
            
        except Exception as e:
            self._handle_error("waiting for backup completion", e)
            return False
