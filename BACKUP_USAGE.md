# AMI Backup Scripts Usage Guide

This guide explains how to use the AMI backup scripts to create backups for servers in any configured landing zone.

## Scripts Overview

### 1. `backup_server.py` (Recommended)
A production-ready script for backing up specific servers in any configured landing zone (cmsnonprod, lz250nonprod, fotoolspreprod).

### 2. `demo_ami_backup.py`
A comprehensive demonstration script showing how to use the AMI backup service with mock data.

## Prerequisites

1. **AWS Credentials**: Ensure you have proper AWS credentials configured
2. **IAM Role**: The script uses the role defined in `config/default.yml` (`HIPCMSProvisionSpokeRole`)
3. **Python Dependencies**: Install required packages from `requirements.txt`
4. **Configuration**: Ensure `config/default.yml` and inventory files are properly configured

## Usage Examples

### Basic Backup
```bash
# Backup a specific instance in cmsnonprod with default settings (pre-patch backup)
python backup_server.py --instance-id i-1234567890abcdef0 --landing-zone cmsnonprod

# Backup a specific instance in lz250nonprod
python backup_server.py --instance-id i-0987654321fedcba0 --landing-zone lz250nonprod
```

### Backup with Specific Type
```bash
# Create a manual backup in cmsnonprod
python backup_server.py --instance-id i-1234567890abcdef0 --landing-zone cmsnonprod --backup-type manual

# Create a post-patch backup in lz250nonprod
python backup_server.py --instance-id i-0987654321fedcba0 --landing-zone lz250nonprod --backup-type post-patch

# Create a pre-patch backup in fotoolspreprod
python backup_server.py --instance-id i-abcdef1234567890 --landing-zone fotoolspreprod --backup-type pre-patch
```

### Debug Mode
```bash
# Run with debug logging
python backup_server.py --instance-id i-1234567890abcdef0 --landing-zone cmsnonprod --log-level DEBUG
```

## Configuration Details

### Supported Landing Zones
From `inventory/nonprod_landing_zones.yml` and `config/default.yml`:

#### cmsnonprod
- **Account ID**: 954976297051
- **Region**: ap-southeast-2
- **IAM Role**: HIPCMSProvisionSpokeRole

#### lz250nonprod
- **Account ID**: 210987654321
- **Region**: ap-southeast-2
- **IAM Role**: HIPCMSProvisionSpokeRole

#### fotoolspreprod
- **Region**: ap-southeast-2
- **IAM Role**: HIPCMSProvisionSpokeRole
- (Account ID configured in inventory)

### Backup Settings (from config/default.yml)

- **Timeout**: 60 minutes
- **Max Concurrent**: 5 backups
- **Retry Attempts**: 2

## Script Features

### `backup_server.py`

#### What it does:
1. **Landing Zone Selection**: Allows you to choose any configured landing zone
2. **Instance Discovery**: Finds the specified instance in the selected landing zone
3. **Validation**: Checks instance status and backup requirements
4. **Backup Creation**: Creates AMI backup using the backup service
5. **Progress Monitoring**: Waits for backup completion with timeout
6. **Detailed Logging**: Provides comprehensive logs and status updates

#### Output Information:

- Backup ID and status
- AMI ID and name (when completed)
- Backup duration
- Creation and completion timestamps
- Error details (if failed)

#### Log Files:
- Console output for real-time monitoring
- Log file: `backup_YYYYMMDD_HHMMSS.log`

## Example Output

```
2024-01-15 10:30:00 - INFO - Starting backup process for instance i-1234567890abcdef0
2024-01-15 10:30:00 - INFO - Landing Zone: cmsnonprod
2024-01-15 10:30:00 - INFO - Backup Type: pre-patch
2024-01-15 10:30:01 - INFO - Initializing services...
2024-01-15 10:30:02 - INFO - Services initialized successfully
2024-01-15 10:30:03 - INFO - Searching for instance i-1234567890abcdef0 in cmsnonprod...
2024-01-15 10:30:05 - INFO - Found instance: demo-server-01 (i-1234567890abcdef0)
2024-01-15 10:30:05 - INFO - Status: running
2024-01-15 10:30:05 - INFO - Platform: linux
2024-01-15 10:30:05 - INFO - Requires backup: True
2024-01-15 10:30:06 - INFO - Creating pre-patch backup for demo-server-01...
2024-01-15 10:30:08 - INFO - Backup initiated successfully!
2024-01-15 10:30:08 - INFO - Backup ID: backup-20240115-103008-abc123
2024-01-15 10:30:08 - INFO - Initial Status: creating
2024-01-15 10:30:08 - INFO - Monitoring backup progress...
2024-01-15 10:45:12 - INFO -
=== BACKUP COMPLETED SUCCESSFULLY ===
2024-01-15 10:45:12 - INFO - AMI ID: ami-0987654321fedcba0
2024-01-15 10:45:12 - INFO - AMI Name: demo-server-01-prepatch-20240115-103008
2024-01-15 10:45:12 - INFO - Duration: 15.1 minutes
2024-01-15 10:45:12 - INFO - Created: 2024-01-15 10:30:08
2024-01-15 10:45:12 - INFO - Completed: 2024-01-15 10:45:12
2024-01-15 10:45:12 - INFO - Backup process completed successfully
```

## Error Handling

The script handles various error scenarios:

1. **Instance Not Found**: If the instance doesn't exist in cmsnonprod
2. **AWS Permission Issues**: If IAM role lacks required permissions
3. **Backup Failures**: If AMI creation fails in AWS
4. **Timeout Issues**: If backup takes longer than configured timeout
5. **Service Initialization**: If AWS services can't be initialized

## Best Practices

1. **Test First**: Run with a test instance before production use
2. **Monitor Logs**: Always check log files for detailed information
3. **Verify Results**: Confirm AMI creation in AWS console
4. **Backup Timing**: Consider instance workload when scheduling backups
5. **Cleanup**: Regularly clean up old AMIs to manage costs

## Troubleshooting

### Common Issues:

1. **"Landing zone not found"**
   - Check available landing zones in the error message
   - Verify landing zone name matches exactly (case-sensitive)
   - Ensure landing zone is configured in `config/default.yml` and inventory files

1. **"Instance not found"**
   - Verify instance ID is correct
   - Ensure instance exists in the specified landing zone account
   - Check that the landing zone name is correct (use exact names from config)
   - Check AWS credentials and permissions

2. **"Services initialization failed"**

   - Verify AWS credentials are configured
   - Check IAM role permissions
   - Ensure config files are present and valid

3. **"Backup timeout"**
   - Large instances may take longer than 60 minutes
   - Check AWS console for AMI creation status
   - Consider increasing timeout in configuration

### Debug Steps:

1. Run with `--log-level DEBUG` for detailed output
2. Check AWS CloudTrail for API call logs
3. Verify instance tags and backup requirements
4. Test AWS connectivity manually

## Integration with Main Workflow

These scripts can be integrated into the main patching workflow:

```python
# Example integration in workflow_orchestrator.py
from backup_server import ServerBackup

# Create backup before patching
backup_tool = ServerBackup()
success = await backup_tool.run(instance_id, landing_zone_name, BackupType.PRE_PATCH)
```

## Support

For issues or questions:

1. Check log files for detailed error information
2. Review AWS console for backup status
3. Verify configuration files and inventory
4. Test with debug logging enabled
