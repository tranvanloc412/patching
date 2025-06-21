"""AMI backup service implementation."""

import asyncio
import logging
from datetime import datetime, timedelta
from typing import List, Dict, Any, Optional

from core.interfaces.ami_backup_interface import IAMIBackupService
from core.interfaces.config_interface import IConfigService
from core.models.instance import Instance
from core.models.ami_backup import AMIBackup, BackupStatus, BackupType, BackupConfiguration
from core.models.config import AMIBackupConfig
from infrastructure.aws.ec2_client import EC2Client


class AMIBackupService(IAMIBackupService):
    """Implementation of AMI backup service."""
    
    def __init__(self, config_service: IConfigService, ec2_client: EC2Client):
        self.config_service = config_service
        self.ec2_client = ec2_client
        self.logger = logging.getLogger(__name__)
        self._active_backups: Dict[str, AMIBackup] = {}
    
    async def create_backup(self, instance: Instance, backup_type: BackupType = BackupType.PRE_PATCH) -> AMIBackup:
        """Create an AMI backup for a single instance."""
        self.logger.info(f"Creating {backup_type.value} backup for instance {instance.instance_id}")
        
        try:
            # Get backup configuration
            backup_config = self._get_backup_configuration()
            
            # Create backup object
            backup = AMIBackup(
                instance_id=instance.instance_id,
                backup_type=backup_type,
                region=instance.region,
                account_id=instance.account_id,
                landing_zone=instance.landing_zone,
                source_ami_id=instance.ami_id,
                platform=instance.platform.value,
                configuration=backup_config
            )
            
            # Configure EC2 client for the instance's region
            await self.ec2_client.configure_for_region(instance.region)
            
            # Start the backup process
            await self._execute_backup(backup, instance)
            
            # Track active backup
            self._active_backups[backup.backup_id] = backup
            
            return backup
            
        except Exception as e:
            self.logger.error(f"Error creating backup for instance {instance.instance_id}: {str(e)}")
            raise
    
    async def create_multiple_backups(self, instances: List[Instance],
                                     backup_type: BackupType = BackupType.PRE_PATCH,
                                     max_concurrent: int = 10) -> List[AMIBackup]:
        """Create AMI backups for multiple instances concurrently."""
        self.logger.info(f"Creating {backup_type.value} backups for {len(instances)} instances")
        
        # Filter instances that require backup
        instances_to_backup = [inst for inst in instances if inst.requires_backup]
        
        if not instances_to_backup:
            self.logger.info("No instances require backup")
            return []
        
        self.logger.info(f"Filtered to {len(instances_to_backup)} instances requiring backup")
        
        # Create semaphore to limit concurrent backups
        semaphore = asyncio.Semaphore(max_concurrent)
        
        async def create_backup_with_semaphore(instance: Instance) -> AMIBackup:
            async with semaphore:
                return await self.create_backup(instance, backup_type)
        
        # Execute backups concurrently
        tasks = [create_backup_with_semaphore(instance) for instance in instances_to_backup]
        results = await asyncio.gather(*tasks, return_exceptions=True)
        
        # Process results
        backups = []
        for i, result in enumerate(results):
            if isinstance(result, Exception):
                instance = instances_to_backup[i]
                self.logger.error(f"Backup failed for instance {instance.instance_id}: {str(result)}")
                
                # Create a failed backup record
                failed_backup = AMIBackup(
                    instance_id=instance.instance_id,
                    backup_type=backup_type,
                    region=instance.region,
                    account_id=instance.account_id,
                    landing_zone=instance.landing_zone
                )
                failed_backup.mark_failed(str(result))
                backups.append(failed_backup)
            else:
                backups.append(result)
        
        successful_backups = len([b for b in backups if not b.is_failed])
        self.logger.info(f"Backup creation complete: {successful_backups}/{len(backups)} successful")
        
        return backups
    
    async def wait_for_completion(self, backup: AMIBackup, timeout_minutes: int = 60) -> bool:
        """Wait for a backup to complete."""
        self.logger.info(f"Waiting for backup {backup.backup_id} to complete")
        
        timeout_time = datetime.utcnow() + timedelta(minutes=timeout_minutes)
        check_interval = 30  # seconds
        
        while datetime.utcnow() < timeout_time:
            try:
                # Check backup status
                status = await self.get_backup_status(backup)
                
                if status == BackupStatus.AVAILABLE:
                    self.logger.info(f"Backup {backup.backup_id} completed successfully")
                    return True
                elif status in [BackupStatus.FAILED, BackupStatus.ERROR, BackupStatus.CANCELLED]:
                    self.logger.error(f"Backup {backup.backup_id} failed with status: {status.value}")
                    return False
                
                # Update progress
                await self._update_backup_progress(backup)
                
                # Wait before next check
                await asyncio.sleep(check_interval)
                
            except Exception as e:
                self.logger.warning(f"Error checking backup status: {str(e)}")
                await asyncio.sleep(check_interval)
        
        # Timeout reached
        self.logger.error(f"Backup {backup.backup_id} timed out after {timeout_minutes} minutes")
        backup.mark_failed("Backup operation timed out")
        return False
    
    async def get_backup_status(self, backup: AMIBackup) -> BackupStatus:
        """Get the current status of a backup."""
        if not backup.ami_id:
            return backup.status
        
        try:
            # Configure EC2 client
            await self.ec2_client.configure_for_region(backup.region)
            
            # Get AMI status from AWS
            ami_info = await self.ec2_client.describe_image(backup.ami_id)
            
            if ami_info:
                aws_state = ami_info.get('State', 'unknown')
                
                if aws_state == 'available':
                    if backup.status != BackupStatus.AVAILABLE:
                        backup.mark_completed(backup.ami_id)
                    return BackupStatus.AVAILABLE
                elif aws_state == 'pending':
                    backup.status = BackupStatus.CREATING
                    return BackupStatus.CREATING
                elif aws_state in ['failed', 'error']:
                    if backup.status != BackupStatus.FAILED:
                        backup.mark_failed(f"AMI creation failed with state: {aws_state}")
                    return BackupStatus.FAILED
                else:
                    backup.status = BackupStatus.CREATING
                    return BackupStatus.CREATING
            else:
                # AMI not found
                if backup.status == BackupStatus.CREATING:
                    backup.mark_failed("AMI not found in AWS")
                return BackupStatus.FAILED
                
        except Exception as e:
            self.logger.warning(f"Error getting backup status for {backup.backup_id}: {str(e)}")
            return backup.status
    
    async def cleanup_old_backups(self, instance_id: str, region: str,
                                 max_age_days: int = 30,
                                 max_backups: int = 5) -> List[str]:
        """Clean up old backups for an instance."""
        self.logger.info(f"Cleaning up old backups for instance {instance_id}")
        
        try:
            # Configure EC2 client
            await self.ec2_client.configure_for_region(region)
            
            # Find backups for this instance
            backups = await self._find_instance_backups(instance_id)
            
            if not backups:
                self.logger.info(f"No backups found for instance {instance_id}")
                return []
            
            # Sort backups by creation date (newest first)
            backups.sort(key=lambda x: x.get('CreationDate', ''), reverse=True)
            
            deleted_amis = []
            cutoff_date = datetime.utcnow() - timedelta(days=max_age_days)
            
            for i, backup in enumerate(backups):
                ami_id = backup['ImageId']
                creation_date = backup.get('CreationDate')
                
                should_delete = False
                reason = ""
                
                # Check if backup exceeds max count
                if i >= max_backups:
                    should_delete = True
                    reason = f"Exceeds max backup count ({max_backups})"
                
                # Check if backup is too old
                elif creation_date and isinstance(creation_date, datetime) and creation_date < cutoff_date:
                    should_delete = True
                    reason = f"Older than {max_age_days} days"
                
                if should_delete:
                    try:
                        await self.ec2_client.deregister_ami(ami_id)
                        deleted_amis.append(ami_id)
                        self.logger.info(f"Deleted old backup AMI {ami_id}: {reason}")
                    except Exception as e:
                        self.logger.warning(f"Failed to delete AMI {ami_id}: {str(e)}")
            
            self.logger.info(f"Cleanup complete for instance {instance_id}: deleted {len(deleted_amis)} AMIs")
            return deleted_amis
            
        except Exception as e:
            self.logger.error(f"Error cleaning up backups for instance {instance_id}: {str(e)}")
            return []
    
    async def list_instance_backups(self, instance_id: str, region: str) -> List[Dict[str, Any]]:
        """List all backups for a specific instance."""
        try:
            # Configure EC2 client
            await self.ec2_client.configure_for_region(region)
            
            # Find backups for this instance
            backups = await self._find_instance_backups(instance_id)
            
            # Convert to standardized format
            backup_list = []
            for backup in backups:
                backup_info = {
                    'ami_id': backup['ImageId'],
                    'name': backup.get('Name', ''),
                    'description': backup.get('Description', ''),
                    'creation_date': backup.get('CreationDate'),
                    'state': backup.get('State', 'unknown'),
                    'tags': {tag['Key']: tag['Value'] for tag in backup.get('Tags', [])}
                }
                backup_list.append(backup_info)
            
            # Sort by creation date (newest first)
            backup_list.sort(key=lambda x: x.get('creation_date', ''), reverse=True)
            
            return backup_list
            
        except Exception as e:
            self.logger.error(f"Error listing backups for instance {instance_id}: {str(e)}")
            return []
    
    def _get_backup_configuration(self) -> BackupConfiguration:
        """Get backup configuration from config service."""
        backup_config = self.config_service.get_phase_config("ami_backup")
        
        return BackupConfiguration(
            no_reboot=backup_config.get("no_reboot", True),
            include_all_volumes=backup_config.get("include_all_volumes", True),
            copy_tags=backup_config.get("copy_tags", True),
            description_template=backup_config.get("description_template", 
                                                 "Pre-patch backup for {instance_id} - {timestamp}"),
            retention_days=backup_config.get("retention_days", 30),
            max_backups_per_instance=backup_config.get("max_backups_per_instance", 5),
            additional_tags=backup_config.get("backup_tags", {}),
            timeout_minutes=backup_config.get("timeout_minutes", 60),
            retry_attempts=backup_config.get("retry_attempts", 2),
            retry_delay_minutes=backup_config.get("retry_delay", 5)
        )
    
    async def _execute_backup(self, backup: AMIBackup, instance: Instance) -> None:
        """Execute the actual backup creation."""
        try:
            # Mark backup as started
            backup.mark_started()
            
            # Prepare backup parameters
            backup_params = {
                'InstanceId': instance.instance_id,
                'Name': backup.ami_name,
                'Description': backup.description,
                'NoReboot': backup.configuration.no_reboot
            }
            
            # Add tags
            if backup.tags:
                backup_params['TagSpecifications'] = [{
                    'ResourceType': 'image',
                    'Tags': [{'Key': k, 'Value': v} for k, v in backup.tags.items()]
                }]
            
            # Create the AMI
            self.logger.debug(f"Creating AMI for instance {instance.instance_id}")
            response = await self.ec2_client.create_image(**backup_params)
            
            ami_id = response.get('ImageId')
            if not ami_id:
                raise Exception("No AMI ID returned from create_image call")
            
            # Update backup with AMI ID
            backup.ami_id = ami_id
            backup.update_progress(50.0, "ami_created")
            
            self.logger.info(f"AMI creation initiated: {ami_id} for instance {instance.instance_id}")
            
        except Exception as e:
            backup.mark_failed(f"Failed to create AMI: {str(e)}")
            raise
    
    async def _update_backup_progress(self, backup: AMIBackup) -> None:
        """Update backup progress based on current status."""
        try:
            if backup.ami_id:
                # Get AMI details to check progress
                ami_info = await self.ec2_client.describe_image(backup.ami_id)
                
                if ami_info:
                    state = ami_info.get('State', 'unknown')
                    
                    if state == 'pending':
                        # Estimate progress based on time elapsed
                        if backup.start_time:
                            elapsed = datetime.utcnow() - backup.start_time
                            # Assume average backup takes 20 minutes
                            estimated_total = timedelta(minutes=20)
                            progress = min(90.0, (elapsed.total_seconds() / estimated_total.total_seconds()) * 90)
                            backup.update_progress(progress, "creating")
                    elif state == 'available':
                        backup.mark_completed(backup.ami_id)
                    elif state in ['failed', 'error']:
                        backup.mark_failed(f"AMI creation failed with state: {state}")
                        
        except Exception as e:
            self.logger.warning(f"Error updating backup progress: {str(e)}")
    
    async def _find_instance_backups(self, instance_id: str) -> List[Dict[str, Any]]:
        """Find all backup AMIs for a specific instance."""
        try:
            # Search for AMIs with tags indicating they're backups for this instance
            filters = [
                {
                    'Name': 'tag:SourceInstanceId',
                    'Values': [instance_id]
                },
                {
                    'Name': 'tag:Purpose',
                    'Values': ['PrePatchBackup', 'Backup']
                },
                {
                    'Name': 'state',
                    'Values': ['available', 'pending']
                }
            ]
            
            images = await self.ec2_client.describe_images(
                owners=['self'],
                filters=filters
            )
            
            return images
            
        except Exception as e:
            self.logger.warning(f"Error finding backups for instance {instance_id}: {str(e)}")
            return []
    
    async def get_active_backups(self) -> Dict[str, AMIBackup]:
        """Get all currently active backups."""
        return self._active_backups.copy()
    
    async def remove_active_backup(self, backup_id: str) -> None:
        """Remove a backup from active tracking."""
        self._active_backups.pop(backup_id, None)