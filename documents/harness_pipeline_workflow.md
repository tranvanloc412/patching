# Harness.io Pipeline for AWS EC2 Patching Workflow

## Overview

This document outlines a high-level workflow design for implementing AWS EC2 patching using Harness.io pipelines. The workflow is structured into three main phases: Pre-Patch, Patching, and Post-Patch, designed for a single landing zone deployment.

## Pipeline Architecture

### Pipeline Structure

```
AWS EC2 Patching Pipeline
├── Pre-Patch Phase
│   ├── Environment Validation
│   ├── Instance Discovery
│   ├── AMI Backup Creation
│   └── Pre-Patch Health Checks
├── Patching Phase
│   ├── Maintenance Window Setup
│   ├── Patch Installation
│   ├── Instance Reboot Management
│   └── Patch Verification
└── Post-Patch Phase
    ├── Application Validation
    ├── Performance Testing
    ├── Rollback Capability
    └── Reporting & Cleanup
```

## Detailed Workflow Phases

### Phase 1: Pre-Patch

#### 1.1 Environment Validation

- **Purpose**: Validate AWS credentials, permissions, and landing zone configuration
- **Harness Step Type**: Shell Script
- **Key Actions**:
  - Verify AWS CLI configuration
  - Validate IAM permissions for EC2, SSM, and backup operations
  - Check landing zone connectivity
  - Validate configuration files

```bash
# Harness Shell Script Example
#!/bin/bash
set -e

# Validate AWS credentials
aws sts get-caller-identity

# Check required permissions
aws iam simulate-principal-policy \
  --policy-source-arn $(aws sts get-caller-identity --query Arn --output text) \
  --action-names ec2:DescribeInstances ec2:CreateImage ssm:SendCommand

# Validate landing zone configuration
python3 main.py --validate-config --landing-zone <+input>.landingZone
```

#### 1.2 Instance Discovery

- **Purpose**: Discover and inventory EC2 instances in the target landing zone
- **Harness Step Type**: Shell Script
- **Key Actions**:
  - Execute scanner service to discover instances
  - Generate instance inventory report
  - Validate instance eligibility for patching
  - Create patching groups based on criticality

```bash
#!/bin/bash
# Run instance discovery
python3 main.py --phase scanner --landing-zone <+input>.landingZone --log-level INFO

# Export results for next phase
cp /tmp/instance_report.csv <+artifacts>.path/instance_inventory.csv
```

#### 1.3 AMI Backup Creation

- **Purpose**: Create AMI backups for all instances before patching
- **Harness Step Type**: Shell Script with Timeout
- **Key Actions**:
  - Initiate AMI backup process
  - Monitor backup progress
  - Validate backup completion
  - Store backup metadata

```bash
#!/bin/bash
# Create AMI backups
python3 main.py --phase ami-backup --landing-zone <+input>.landingZone --log-level INFO

# Wait for backup completion with timeout
timeout 3600 python3 backup_server.py <+input>.instanceId <+input>.landingZone INFO

# Validate backup success
if [ $? -eq 0 ]; then
  echo "AMI backup completed successfully"
else
  echo "AMI backup failed or timed out"
  exit 1
fi
```

#### 1.4 Pre-Patch Health Checks & Server State Validation

- **Purpose**: Ensure servers are running and healthy before patching operations
- **Harness Step Type**: Shell Script with Conditional Logic
- **Key Actions**:
  - Validate instance status and ensure servers are running
  - Start stopped instances if required
  - Check system resources (CPU, memory, disk)
  - Validate SSM agent connectivity
  - Verify critical services status
  - Check application health endpoints
  - Validate network connectivity

```bash
#!/bin/bash
set -e

# Step 1: Check and ensure instances are running
echo "=== Server State Validation ==="
python3 -c "
import asyncio
import sys
from core.services.validation_service import ValidationService
from core.services.server_manager_service import ServerManagerService
from core.services.config_service import ConfigService
from infrastructure.aws.ec2_client import EC2Client
from infrastructure.aws.ssm_client import SSMClient

async def ensure_servers_running():
    # Initialize services
    config_service = ConfigService()
    ec2_client = EC2Client('<+input>.region')
    ssm_client = SSMClient('<+input>.region')
    server_manager = ServerManagerService(config_service, ec2_client, ssm_client)
    validation_service = ValidationService(config_service, server_manager)

    # Get instances from discovery phase
    instances = await get_discovered_instances('<+input>.landingZone')

    for instance in instances:
        print(f'Checking instance {instance.instance_id}...')

        # Check current status
        current_status = await server_manager.get_instance_state(
            instance.instance_id, instance.region
        )

        if current_status.value == 'stopped':
            print(f'Starting stopped instance {instance.instance_id}...')
            result = await server_manager.start_instance(
                instance.instance_id,
                instance.account_id,
                instance.region,
                '<+input>.roleName',
                timeout_minutes=10
            )

            if not result['success']:
                print(f'Failed to start instance {instance.instance_id}: {result.get(\"error_message\")}')
                sys.exit(1)

            print(f'Instance {instance.instance_id} started successfully')

        elif current_status.value == 'running':
            print(f'Instance {instance.instance_id} is already running')

        else:
            print(f'Instance {instance.instance_id} is in {current_status.value} state - cannot proceed')
            sys.exit(1)

    print('All instances are now running')
    return True

asyncio.run(ensure_servers_running())
"

if [ $? -ne 0 ]; then
    echo "Failed to ensure all servers are running"
    exit 1
fi

# Step 2: Comprehensive health validation
echo "=== Health Checks ==="
python3 main.py --phase precheck --landing-zone <+input>.landingZone --log-level INFO

# Step 3: SSM Agent connectivity validation
echo "=== SSM Agent Validation ==="
aws ssm describe-instance-information \
  --filters "Key=tag:Environment,Values=<+input>.landingZone" \
  --query 'InstanceInformationList[?PingStatus!=`Online`].[InstanceId,PingStatus]' \
  --output table

# Check if any instances are not online
OFFLINE_COUNT=$(aws ssm describe-instance-information \
  --filters "Key=tag:Environment,Values=<+input>.landingZone" \
  --query 'length(InstanceInformationList[?PingStatus!=`Online`])' \
  --output text)

if [ "$OFFLINE_COUNT" -gt 0 ]; then
    echo "Warning: $OFFLINE_COUNT instances have SSM agent issues"
    echo "Attempting to restart SSM agent on affected instances..."

    aws ssm send-command \
      --document-name "AWS-RunShellScript" \
      --parameters 'commands=["sudo systemctl restart amazon-ssm-agent","sleep 30","sudo systemctl status amazon-ssm-agent"]' \
      --targets "Key=tag:Environment,Values=<+input>.landingZone" \
      --comment "Restart SSM agent for prepatch validation"
fi

# Step 4: System resource validation
echo "=== System Resource Checks ==="
COMMAND_ID=$(aws ssm send-command \
  --document-name "AWS-RunShellScript" \
  --parameters 'commands=[
    "echo \"=== Disk Space ==="\",
    "df -h | grep -E \"(Filesystem|/dev/)\"",
    "echo \"=== Memory Usage ==="\",
    "free -m",
    "echo \"=== CPU Load ==="\",
    "uptime",
    "echo \"=== Critical Services ==="\",
    "if command -v systemctl >/dev/null 2>&1; then systemctl is-active sshd || echo \"SSH service issue\"; fi",
    "echo \"=== Network Connectivity ==="\",
    "ping -c 3 8.8.8.8 || echo \"Network connectivity issue\""
  ]' \
  --targets "Key=tag:Environment,Values=<+input>.landingZone" \
  --comment "Pre-patch system resource validation" \
  --query 'Command.CommandId' --output text)

# Wait for command completion and check results
sleep 60
aws ssm list-command-invocations \
  --command-id $COMMAND_ID \
  --details \
  --query 'CommandInvocations[?Status!=`Success`].[InstanceId,Status,StatusDetails]' \
  --output table

# Step 5: Application-specific health checks
echo "=== Application Health Validation ==="
if [ ! -z "<+input>.applicationEndpoint" ]; then
    # Test application endpoints
    for endpoint in $(echo "<+input>.applicationEndpoint" | tr ',' ' '); do
        echo "Testing endpoint: $endpoint"
        if curl -f -s --max-time 30 "$endpoint/health" > /dev/null; then
            echo "✓ $endpoint is healthy"
        else
            echo "✗ $endpoint health check failed"
            # Don't fail the pipeline for application issues, just warn
        fi
    done
fi

# Step 6: Generate health report
echo "=== Generating Health Report ==="
python3 -c "
import json
import boto3
from datetime import datetime

# Collect health summary
health_report = {
    'validation_time': datetime.utcnow().isoformat(),
    'landing_zone': '<+input>.landingZone',
    'total_instances_checked': 0,
    'running_instances': 0,
    'ssm_online_instances': 0,
    'health_issues': []
}

# Save report for next phase
with open('/tmp/prepatch_health_report.json', 'w') as f:
    json.dump(health_report, f, indent=2)

print('Health validation completed successfully')
"

echo "Pre-patch health checks completed. Report saved to artifacts."
cp /tmp/prepatch_health_report.json <+artifacts>.path/prepatch_health_report.json
```

### Phase 2: Patching

#### 2.1 Maintenance Window Setup

- **Purpose**: Configure and activate maintenance windows
- **Harness Step Type**: Shell Script
- **Key Actions**:
  - Create SSM maintenance windows
  - Register targets for patching
  - Configure patching schedules
  - Set up monitoring and alerting

```bash
#!/bin/bash
# Create maintenance window
MAINTENANCE_WINDOW_ID=$(aws ssm create-maintenance-window \
  --name "Patching-<+input>.landingZone-$(date +%Y%m%d)" \
  --schedule "cron(0 2 ? * SUN *)" \
  --duration 4 \
  --cutoff 1 \
  --query 'WindowId' --output text)

echo "Created maintenance window: $MAINTENANCE_WINDOW_ID"
```

#### 2.2 Patch Installation

- **Purpose**: Execute patch installation using AWS Systems Manager
- **Harness Step Type**: Shell Script with Approval
- **Key Actions**:
  - Execute patch baseline installation
  - Monitor patch installation progress
  - Handle patch installation failures
  - Log patch installation results

```bash
#!/bin/bash
# Execute patching via SSM
COMMAND_ID=$(aws ssm send-command \
  --document-name "AWS-RunPatchBaseline" \
  --parameters 'Operation=Install,RebootOption=RebootIfNeeded' \
  --targets "Key=tag:Environment,Values=<+input>.landingZone" \
  --query 'Command.CommandId' --output text)

# Monitor command execution
while true; do
  STATUS=$(aws ssm get-command-invocation \
    --command-id $COMMAND_ID \
    --instance-id <+input>.instanceId \
    --query 'Status' --output text)

  if [[ "$STATUS" == "Success" || "$STATUS" == "Failed" ]]; then
    break
  fi
  sleep 30
done

echo "Patch installation status: $STATUS"
```

#### 2.3 Instance Reboot Management

- **Purpose**: Manage instance reboots during patching
- **Harness Step Type**: Shell Script
- **Key Actions**:
  - Coordinate graceful instance reboots
  - Monitor instance availability post-reboot
  - Validate service startup
  - Handle reboot failures

```bash
#!/bin/bash
# Graceful reboot management
aws ssm send-command \
  --document-name "AWS-RunShellScript" \
  --parameters 'commands=["sudo shutdown -r +1"]' \
  --targets "Key=InstanceIds,Values=<+input>.instanceId"

# Wait for instance to come back online
aws ec2 wait instance-status-ok --instance-ids <+input>.instanceId
```

#### 2.4 Patch Verification

- **Purpose**: Verify successful patch installation
- **Harness Step Type**: Shell Script
- **Key Actions**:
  - Validate installed patches
  - Check system integrity
  - Verify security compliance
  - Generate patch compliance report

```bash
#!/bin/bash
# Verify patch installation
aws ssm send-command \
  --document-name "AWS-RunPatchBaseline" \
  --parameters 'Operation=Scan' \
  --targets "Key=InstanceIds,Values=<+input>.instanceId"

# Generate compliance report
python3 main.py --phase patch-verify --landing-zone <+input>.landingZone --log-level INFO
```

### Phase 3: Post-Patch

#### 3.1 Application Validation

- **Purpose**: Validate application functionality post-patching
- **Harness Step Type**: Shell Script
- **Key Actions**:
  - Execute application health checks
  - Validate critical business functions
  - Check application performance metrics
  - Verify data integrity

```bash
#!/bin/bash
# Application validation
python3 main.py --phase post-patch-validation --landing-zone <+input>.landingZone --log-level INFO

# Custom application health checks
curl -f http://<+input>.applicationEndpoint/health || exit 1

# Performance validation
aws cloudwatch get-metric-statistics \
  --namespace AWS/EC2 \
  --metric-name CPUUtilization \
  --dimensions Name=InstanceId,Value=<+input>.instanceId \
  --start-time $(date -u -d '1 hour ago' +%Y-%m-%dT%H:%M:%S) \
  --end-time $(date -u +%Y-%m-%dT%H:%M:%S) \
  --period 300 \
  --statistics Average
```

#### 3.2 Performance Testing

- **Purpose**: Execute performance tests to ensure system stability
- **Harness Step Type**: Shell Script
- **Key Actions**:
  - Run automated performance tests
  - Compare performance metrics with baseline
  - Validate response times and throughput
  - Generate performance reports

```bash
#!/bin/bash
# Performance testing
# Execute load testing scripts
./scripts/performance_test.sh <+input>.applicationEndpoint

# Compare with baseline metrics
python3 scripts/performance_comparison.py \
  --current-metrics /tmp/current_metrics.json \
  --baseline-metrics /baseline/performance_baseline.json
```

#### 3.3 Rollback Capability

- **Purpose**: Provide rollback mechanism in case of issues
- **Harness Step Type**: Manual Approval + Shell Script
- **Key Actions**:
  - Prepare rollback procedures
  - Create rollback decision points
  - Execute rollback if needed
  - Validate rollback success

```bash
#!/bin/bash
# Rollback capability
if [[ "<+input>.rollbackRequired" == "true" ]]; then
  echo "Initiating rollback procedure"

  # Restore from AMI backup
  python3 scripts/rollback_from_ami.py \
    --instance-id <+input>.instanceId \
    --backup-ami-id <+artifacts>.amiBackupId

  # Validate rollback
  aws ec2 wait instance-status-ok --instance-ids <+input>.instanceId
fi
```

#### 3.4 Reporting & Cleanup

- **Purpose**: Generate comprehensive reports and cleanup resources
- **Harness Step Type**: Shell Script
- **Key Actions**:
  - Generate patching summary report
  - Update compliance databases
  - Cleanup temporary resources
  - Send notifications

```bash
#!/bin/bash
# Generate final report
python3 main.py --phase reporting --landing-zone <+input>.landingZone --log-level INFO

# Cleanup temporary resources
aws ssm delete-maintenance-window --window-id <+artifacts>.maintenanceWindowId

# Send notifications
aws sns publish \
  --topic-arn <+input>.notificationTopic \
  --message "Patching completed for landing zone: <+input>.landingZone"
```

## Pipeline Configuration

### Input Variables

```yaml
landingZone:
  type: String
  description: "Target landing zone for patching"
  required: true

instanceId:
  type: String
  description: "Specific instance ID (optional)"
  required: false

applicationEndpoint:
  type: String
  description: "Application health check endpoint"
  required: true

notificationTopic:
  type: String
  description: "SNS topic for notifications"
  required: true

rollbackRequired:
  type: String
  description: "Whether rollback is required"
  default: "false"
```

### Approval Gates

1. **Pre-Patch Approval**: Manual approval before starting patching phase
2. **Post-Patch Validation**: Manual approval after patch verification
3. **Rollback Decision**: Manual approval for rollback execution

### Failure Handling

- **Retry Strategy**: Automatic retry for transient failures (max 3 attempts)
- **Rollback Triggers**: Automatic rollback on critical failures
- **Notification Strategy**: Immediate alerts for failures, summary reports for success

### Monitoring & Observability

- **CloudWatch Integration**: Real-time monitoring of patching progress
- **Custom Metrics**: Track patching success rates, duration, and failure reasons
- **Logging**: Centralized logging for all patching activities
- **Dashboards**: Real-time dashboards for patching status

## Security Considerations

### IAM Permissions

```json
{
  "Version": "2012-10-17",
  "Statement": [
    {
      "Effect": "Allow",
      "Action": [
        "ec2:DescribeInstances",
        "ec2:CreateImage",
        "ec2:DescribeImages",
        "ssm:SendCommand",
        "ssm:GetCommandInvocation",
        "ssm:CreateMaintenanceWindow",
        "ssm:DeleteMaintenanceWindow",
        "sns:Publish",
        "cloudwatch:GetMetricStatistics"
      ],
      "Resource": "*"
    }
  ]
}
```

### Secret Management

- Use Harness Secret Manager for AWS credentials
- Rotate secrets regularly
- Implement least privilege access

## Server State Management Best Practices

### Pre-Patch Server Validation Strategy

#### 1. Instance State Verification

- **Automated State Checks**: Verify all instances are in expected states before patching
- **Conditional Starting**: Automatically start stopped instances with proper validation
- **State Transition Monitoring**: Monitor instance state changes with timeouts
- **Failure Handling**: Implement proper error handling for instances that fail to start

#### 2. Health Check Hierarchy

```
Level 1: Infrastructure Health
├── Instance Status (running/stopped/terminated)
├── SSM Agent Connectivity
└── Basic Network Connectivity

Level 2: System Health
├── System Resources (CPU, Memory, Disk)
├── Critical Services Status
└── Security Agent Status

Level 3: Application Health
├── Application Service Status
├── Health Endpoint Validation
└── Database Connectivity
```

#### 3. Server Starting Logic

```bash
# Enhanced server starting with validation
for instance in discovered_instances:
    current_state = get_instance_state(instance)

    if current_state == "stopped":
        # Check if instance should be started
        if should_start_instance(instance):
            start_result = start_instance_with_timeout(instance, 10_minutes)
            if start_result.success:
                wait_for_ssm_connectivity(instance, 5_minutes)
                validate_critical_services(instance)
            else:
                handle_start_failure(instance, start_result.error)

    elif current_state == "running":
        validate_instance_health(instance)

    else:
        # Handle unexpected states
        log_warning(f"Instance {instance.id} in unexpected state: {current_state}")
        decide_on_proceeding_or_failing(instance, current_state)
```

#### 4. SSM Agent Validation

- **Connectivity Verification**: Ensure SSM agent is online and responsive
- **Version Validation**: Check SSM agent version compatibility
- **Automatic Remediation**: Restart SSM agent if connectivity issues detected
- **Fallback Strategies**: Alternative connection methods if SSM fails

#### 5. Resource Threshold Validation

```yaml
# Resource validation thresholds
resource_thresholds:
  disk_space:
    root_partition: 85% # Fail if > 85% used
    temp_partition: 90% # Fail if > 90% used
  memory:
    available: 512MB # Fail if < 512MB available
  cpu:
    load_average: 80% # Warn if > 80% load
  network:
    ping_timeout: 5s # Fail if ping > 5s
```

## General Best Practices

1. **Gradual Rollout**: Start with non-production environments
2. **Backup Strategy**: Always create AMI backups before patching
3. **Testing**: Comprehensive testing in lower environments
4. **Monitoring**: Continuous monitoring during and after patching
5. **Documentation**: Maintain detailed runbooks and procedures
6. **Automation**: Minimize manual interventions where possible
7. **Compliance**: Ensure compliance with organizational policies
8. **Server State Management**: Implement robust server state validation and recovery
9. **Health Check Layering**: Use hierarchical health checks for comprehensive validation
10. **Timeout Management**: Set appropriate timeouts for all operations
11. **Error Recovery**: Implement automatic remediation for common issues
12. **Reporting**: Generate detailed reports for audit and troubleshooting

## Integration Points

### External Systems

- **ITSM Integration**: ServiceNow/Jira for change management
- **Monitoring Tools**: Integration with existing monitoring solutions
- **Compliance Tools**: Integration with security and compliance platforms
- **Notification Systems**: Slack, Teams, or email notifications

### Data Flow

```
Harness Pipeline → AWS Services → Monitoring → Reporting → ITSM
```

This workflow provides a comprehensive, automated approach to AWS EC2 patching using Harness.io, ensuring reliability, security, and compliance while minimizing manual effort and reducing the risk of human error.
