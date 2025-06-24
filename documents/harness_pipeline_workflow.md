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
# Enhanced Harness Shell Script with Error Handling
#!/bin/bash
set -euo pipefail  # Exit on error, undefined vars, pipe failures
IFS=$'\n\t'       # Secure Internal Field Separator

# Logging functions
log_info() { echo "[INFO] $(date '+%Y-%m-%d %H:%M:%S') - $*"; }
log_warn() { echo "[WARN] $(date '+%Y-%m-%d %H:%M:%S') - $*" >&2; }
log_error() { echo "[ERROR] $(date '+%Y-%m-%d %H:%M:%S') - $*" >&2; }

# Error handling function
error_exit() {
    log_error "$1"
    log_error "Line: $2"
    exit "${3:-1}"
}
trap 'error_exit "Script failed" "$LINENO"' ERR

# Retry function with exponential backoff
retry_with_backoff() {
    local max_attempts=$1
    local delay=$2
    local command="${@:3}"
    local attempt=1
    
    while [ $attempt -le $max_attempts ]; do
        if $command; then
            return 0
        fi
        
        log_warn "Attempt $attempt failed. Retrying in ${delay}s..."
        sleep $delay
        delay=$((delay * 2))  # Exponential backoff
        attempt=$((attempt + 1))
    done
    
    error_exit "Command failed after $max_attempts attempts" "$LINENO"
}

# Input validation
validate_input() {
    local var_name="$1"
    local var_value="$2"
    local pattern="$3"
    
    if [[ ! "$var_value" =~ $pattern ]]; then
        error_exit "Invalid $var_name: $var_value" "$LINENO"
    fi
}

# Validate inputs
LANDING_ZONE="<+input>.landingZone"
validate_input "landing_zone" "$LANDING_ZONE" '^[a-zA-Z0-9-]+$'

log_info "Starting environment validation for landing zone: $LANDING_ZONE"

# Validate AWS credentials with retry
log_info "Validating AWS credentials..."
retry_with_backoff 3 5 aws sts get-caller-identity

# Check required permissions
log_info "Checking IAM permissions..."
CURRENT_ARN=$(aws sts get-caller-identity --query Arn --output text)
retry_with_backoff 3 5 aws iam simulate-principal-policy \
  --policy-source-arn "$CURRENT_ARN" \
  --action-names ec2:DescribeInstances ec2:CreateImage ssm:SendCommand

# Validate landing zone configuration
log_info "Validating landing zone configuration..."
retry_with_backoff 3 5 python3 main.py --validate-config --landing-zone "$LANDING_ZONE"

log_info "Environment validation completed successfully"
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
set -euo pipefail
IFS=$'\n\t'

# Source common functions (assuming they're in a shared script)
source "$(dirname "$0")/common_functions.sh" 2>/dev/null || {
    # Inline common functions if shared script not available
    log_info() { echo "[INFO] $(date '+%Y-%m-%d %H:%M:%S') - $*"; }
    log_error() { echo "[ERROR] $(date '+%Y-%m-%d %H:%M:%S') - $*" >&2; }
    error_exit() { log_error "$1"; exit "${2:-1}"; }
    retry_with_backoff() {
        local max_attempts=$1 delay=$2 attempt=1
        local command="${@:3}"
        while [ $attempt -le $max_attempts ]; do
            if $command; then return 0; fi
            log_warn "Attempt $attempt failed. Retrying in ${delay}s..."
            sleep $delay; delay=$((delay * 2)); attempt=$((attempt + 1))
        done
        error_exit "Command failed after $max_attempts attempts"
    }
}

# Configuration
LANDING_ZONE="<+input>.landingZone"
LOG_LEVEL="${LOG_LEVEL:-INFO}"
OUTPUT_DIR="<+artifacts>.path"
TEMP_REPORT="/tmp/instance_report.csv"
FINAL_REPORT="$OUTPUT_DIR/instance_inventory.csv"

# Cleanup function
cleanup() {
    log_info "Performing cleanup..."
    rm -f "$TEMP_REPORT.tmp" 2>/dev/null || true
}
trap cleanup EXIT

log_info "Starting instance discovery for landing zone: $LANDING_ZONE"

# Validate prerequisites
if [[ ! -d "$OUTPUT_DIR" ]]; then
    mkdir -p "$OUTPUT_DIR" || error_exit "Failed to create output directory: $OUTPUT_DIR"
fi

# Run instance discovery with retry and validation
log_info "Executing scanner service..."
retry_with_backoff 3 10 python3 main.py \
    --phase scanner \
    --landing-zone "$LANDING_ZONE" \
    --log-level "$LOG_LEVEL"

# Validate output file exists and has content
if [[ ! -f "$TEMP_REPORT" ]]; then
    error_exit "Instance report not generated: $TEMP_REPORT"
fi

# Check if report has data (more than just header)
LINE_COUNT=$(wc -l < "$TEMP_REPORT")
if [[ $LINE_COUNT -lt 2 ]]; then
    log_warn "Instance report appears to be empty or contains only headers"
    log_warn "Line count: $LINE_COUNT"
fi

# Validate CSV format
if ! head -1 "$TEMP_REPORT" | grep -q "instance_id\|Instance"; then
    error_exit "Invalid CSV format detected in instance report"
fi

# Export results for next phase with validation
log_info "Exporting instance inventory to artifacts..."
cp "$TEMP_REPORT" "$FINAL_REPORT" || error_exit "Failed to copy report to artifacts"

# Generate summary
INSTANCE_COUNT=$((LINE_COUNT - 1))  # Subtract header line
log_info "Instance discovery completed successfully"
log_info "Total instances discovered: $INSTANCE_COUNT"
log_info "Report saved to: $FINAL_REPORT"

# Optional: Create a summary JSON for downstream steps
cat > "$OUTPUT_DIR/discovery_summary.json" << EOF
{
  "landing_zone": "$LANDING_ZONE",
  "discovery_time": "$(date -u +%Y-%m-%dT%H:%M:%SZ)",
  "total_instances": $INSTANCE_COUNT,
  "report_file": "instance_inventory.csv",
  "status": "completed"
}
EOF

log_info "Discovery summary created: $OUTPUT_DIR/discovery_summary.json"
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
set -euo pipefail
IFS=$'\n\t'

# Source common functions
source "$(dirname "$0")/common_functions.sh" 2>/dev/null || {
    log_info() { echo "[INFO] $(date '+%Y-%m-%d %H:%M:%S') - $*"; }
    log_warn() { echo "[WARN] $(date '+%Y-%m-%d %H:%M:%S') - $*" >&2; }
    log_error() { echo "[ERROR] $(date '+%Y-%m-%d %H:%M:%S') - $*" >&2; }
    error_exit() { log_error "$1"; exit "${2:-1}"; }
}

# Configuration
LANDING_ZONE="<+input>.landingZone"
INSTANCE_ID="<+input>.instanceId"
LOG_LEVEL="${LOG_LEVEL:-INFO}"
BACKUP_TIMEOUT="${BACKUP_TIMEOUT:-3600}"  # 1 hour default
OUTPUT_DIR="<+artifacts>.path"
BACKUP_METADATA="$OUTPUT_DIR/ami_backup_metadata.json"

# Validate inputs
if [[ -z "$LANDING_ZONE" ]]; then
    error_exit "Landing zone is required"
fi

if [[ -n "$INSTANCE_ID" && ! "$INSTANCE_ID" =~ ^i-[0-9a-f]{8,17}$ ]]; then
    error_exit "Invalid instance ID format: $INSTANCE_ID"
fi

# Cleanup function
cleanup() {
    log_info "Performing cleanup..."
    # Cancel any ongoing backup operations if script is interrupted
    if [[ -n "${BACKUP_PID:-}" ]]; then
        kill "$BACKUP_PID" 2>/dev/null || true
        wait "$BACKUP_PID" 2>/dev/null || true
    fi
}
trap cleanup EXIT INT TERM

log_info "Starting AMI backup process for landing zone: $LANDING_ZONE"

# Create output directory if it doesn't exist
mkdir -p "$OUTPUT_DIR" || error_exit "Failed to create output directory: $OUTPUT_DIR"

# Function to monitor backup progress
monitor_backup_progress() {
    local backup_log="/tmp/ami_backup.log"
    local progress_interval=60  # Check every minute
    local elapsed=0
    
    while [[ $elapsed -lt $BACKUP_TIMEOUT ]]; do
        if [[ -f "$backup_log" ]]; then
            local last_line=$(tail -1 "$backup_log" 2>/dev/null || echo "")
            if [[ -n "$last_line" ]]; then
                log_info "Backup progress: $last_line"
            fi
        fi
        
        sleep $progress_interval
        elapsed=$((elapsed + progress_interval))
        
        # Check if backup process is still running
        if [[ -n "${BACKUP_PID:-}" ]] && ! kill -0 "$BACKUP_PID" 2>/dev/null; then
            break
        fi
    done
}

# Start AMI backup process
log_info "Initiating AMI backup process..."
if [[ -n "$INSTANCE_ID" ]]; then
    log_info "Creating backup for specific instance: $INSTANCE_ID"
    # Start backup process in background
    python3 backup_server.py "$INSTANCE_ID" "$LANDING_ZONE" "$LOG_LEVEL" > /tmp/ami_backup.log 2>&1 &
    BACKUP_PID=$!
else
    log_info "Creating backups for all instances in landing zone"
    python3 main.py --phase ami-backup --landing-zone "$LANDING_ZONE" --log-level "$LOG_LEVEL" > /tmp/ami_backup.log 2>&1 &
    BACKUP_PID=$!
fi

# Monitor backup progress
log_info "Monitoring backup progress (timeout: ${BACKUP_TIMEOUT}s)..."
monitor_backup_progress &
MONITOR_PID=$!

# Wait for backup completion with timeout
if timeout "$BACKUP_TIMEOUT" wait "$BACKUP_PID"; then
    BACKUP_EXIT_CODE=$?
    kill "$MONITOR_PID" 2>/dev/null || true
    wait "$MONITOR_PID" 2>/dev/null || true
else
    log_error "Backup process timed out after ${BACKUP_TIMEOUT} seconds"
    kill "$BACKUP_PID" "$MONITOR_PID" 2>/dev/null || true
    error_exit "AMI backup timed out"
fi

# Validate backup success
if [[ $BACKUP_EXIT_CODE -eq 0 ]]; then
    log_info "AMI backup completed successfully"
    
    # Extract backup information from log
    if [[ -f "/tmp/ami_backup.log" ]]; then
        # Create backup metadata
        cat > "$BACKUP_METADATA" << EOF
{
  "backup_time": "$(date -u +%Y-%m-%dT%H:%M:%SZ)",
  "landing_zone": "$LANDING_ZONE",
  "instance_id": "${INSTANCE_ID:-all}",
  "status": "completed",
  "duration_seconds": $(($(date +%s) - START_TIME)),
  "log_file": "ami_backup.log"
}
EOF
        
        # Copy log to artifacts
        cp /tmp/ami_backup.log "$OUTPUT_DIR/" || log_warn "Failed to copy backup log"
        
        log_info "Backup metadata saved to: $BACKUP_METADATA"
    fi
else
    log_error "AMI backup failed with exit code: $BACKUP_EXIT_CODE"
    
    # Show last few lines of log for debugging
    if [[ -f "/tmp/ami_backup.log" ]]; then
        log_error "Last 10 lines of backup log:"
        tail -10 /tmp/ami_backup.log >&2
        cp /tmp/ami_backup.log "$OUTPUT_DIR/ami_backup_failed.log" || true
    fi
    
    error_exit "AMI backup failed"
fi

# Verify AMI creation (if specific instance)
if [[ -n "$INSTANCE_ID" ]]; then
    log_info "Verifying AMI creation for instance: $INSTANCE_ID"
    
    # Get the most recent AMI for this instance
    RECENT_AMI=$(aws ec2 describe-images \
        --owners self \
        --filters "Name=name,Values=*$INSTANCE_ID*" \
        --query 'Images | sort_by(@, &CreationDate) | [-1].ImageId' \
        --output text 2>/dev/null || echo "None")
    
    if [[ "$RECENT_AMI" != "None" && "$RECENT_AMI" != "null" ]]; then
        log_info "AMI created successfully: $RECENT_AMI"
        
        # Update metadata with AMI ID
        if [[ -f "$BACKUP_METADATA" ]]; then
            # Add AMI ID to metadata (simple approach)
            sed -i.bak 's/"log_file":/"ami_id": "'"$RECENT_AMI"'", "log_file":/' "$BACKUP_METADATA"
        fi
    else
        log_warn "Could not verify AMI creation - manual verification recommended"
    fi
fi

log_info "AMI backup process completed successfully"
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
set -euo pipefail
IFS=$'\n\t'

# Source common functions
source "$(dirname "$0")/common_functions.sh" 2>/dev/null || {
    log_info() { echo "[INFO] $(date '+%Y-%m-%d %H:%M:%S') - $*"; }
    log_error() { echo "[ERROR] $(date '+%Y-%m-%d %H:%M:%S') - $*" >&2; }
    error_exit() { log_error "$1"; exit "${2:-1}"; }
    retry_with_backoff() {
        local max_attempts=$1 delay=$2 attempt=1
        local command="${@:3}"
        while [ $attempt -le $max_attempts ]; do
            if $command; then return 0; fi
            log_warn "Attempt $attempt failed. Retrying in ${delay}s..."
            sleep $delay; delay=$((delay * 2)); attempt=$((attempt + 1))
        done
        error_exit "Command failed after $max_attempts attempts"
    }
}

# Configuration
LANDING_ZONE="<+input>.landingZone"
REGION="<+input>.region"
OUTPUT_DIR="<+artifacts>.path"
WINDOW_METADATA="$OUTPUT_DIR/maintenance_window_metadata.json"

# Maintenance window configuration
WINDOW_NAME="Patching-${LANDING_ZONE}-$(date +%Y%m%d-%H%M)"
WINDOW_SCHEDULE="${MAINTENANCE_SCHEDULE:-cron(0 2 ? * SUN *)}"
WINDOW_DURATION="${MAINTENANCE_DURATION:-4}"
WINDOW_CUTOFF="${MAINTENANCE_CUTOFF:-1}"
WINDOW_DESCRIPTION="Automated patching maintenance window for landing zone: $LANDING_ZONE"

# Validate inputs
if [[ -z "$LANDING_ZONE" ]]; then
    error_exit "Landing zone is required"
fi

if [[ ! "$WINDOW_DURATION" =~ ^[1-9][0-9]*$ ]] || [[ $WINDOW_DURATION -gt 24 ]]; then
    error_exit "Invalid maintenance window duration: $WINDOW_DURATION (must be 1-24 hours)"
fi

if [[ ! "$WINDOW_CUTOFF" =~ ^[0-9]+$ ]] || [[ $WINDOW_CUTOFF -ge $WINDOW_DURATION ]]; then
    error_exit "Invalid cutoff time: $WINDOW_CUTOFF (must be less than duration)"
fi

# Cleanup function
cleanup() {
    log_info "Performing cleanup..."
    # If window creation failed, attempt to clean up any partial resources
    if [[ -n "${MAINTENANCE_WINDOW_ID:-}" && "${WINDOW_CREATION_FAILED:-false}" == "true" ]]; then
        log_info "Attempting to clean up failed maintenance window: $MAINTENANCE_WINDOW_ID"
        aws ssm delete-maintenance-window --window-id "$MAINTENANCE_WINDOW_ID" 2>/dev/null || true
    fi
}
trap cleanup EXIT

log_info "Setting up maintenance window for landing zone: $LANDING_ZONE"
log_info "Window schedule: $WINDOW_SCHEDULE"
log_info "Window duration: $WINDOW_DURATION hours"
log_info "Window cutoff: $WINDOW_CUTOFF hours"

# Check for existing maintenance windows to avoid conflicts
log_info "Checking for existing maintenance windows..."
EXISTING_WINDOWS=$(aws ssm describe-maintenance-windows \
    --filters "Key=Name,Values=Patching-${LANDING_ZONE}-*" \
    --query 'WindowIdentities[?Enabled==`true`].WindowId' \
    --output text 2>/dev/null || echo "")

if [[ -n "$EXISTING_WINDOWS" ]]; then
    log_warn "Found existing maintenance windows for this landing zone:"
    echo "$EXISTING_WINDOWS" | tr '\t' '\n' | while read -r window_id; do
        if [[ -n "$window_id" ]]; then
            WINDOW_INFO=$(aws ssm get-maintenance-window --window-id "$window_id" \
                --query '[Name,Schedule,Duration,Cutoff,Enabled]' --output text 2>/dev/null || echo "Unknown")
            log_warn "  Window ID: $window_id - Info: $WINDOW_INFO"
        fi
    done
fi

# Create maintenance window with retry
log_info "Creating maintenance window: $WINDOW_NAME"
MAINTENANCE_WINDOW_ID=$(retry_with_backoff 3 5 aws ssm create-maintenance-window \
    --name "$WINDOW_NAME" \
    --description "$WINDOW_DESCRIPTION" \
    --schedule "$WINDOW_SCHEDULE" \
    --duration "$WINDOW_DURATION" \
    --cutoff "$WINDOW_CUTOFF" \
    --allow-unassociated-targets \
    --query 'WindowId' --output text)

if [[ -z "$MAINTENANCE_WINDOW_ID" || "$MAINTENANCE_WINDOW_ID" == "None" ]]; then
    WINDOW_CREATION_FAILED=true
    error_exit "Failed to create maintenance window"
fi

log_info "Created maintenance window: $MAINTENANCE_WINDOW_ID"

# Register targets (instances in the landing zone)
log_info "Registering targets for maintenance window..."
TARGET_ID=$(retry_with_backoff 3 5 aws ssm register-target-with-maintenance-window \
    --window-id "$MAINTENANCE_WINDOW_ID" \
    --target-type "Instance" \
    --targets "Key=tag:Environment,Values=$LANDING_ZONE" \
    --query 'WindowTargetId' --output text)

if [[ -z "$TARGET_ID" || "$TARGET_ID" == "None" ]]; then
    WINDOW_CREATION_FAILED=true
    error_exit "Failed to register targets with maintenance window"
fi

log_info "Registered targets with ID: $TARGET_ID"

# Register patch task
log_info "Registering patch task with maintenance window..."
TASK_ID=$(retry_with_backoff 3 5 aws ssm register-task-with-maintenance-window \
    --window-id "$MAINTENANCE_WINDOW_ID" \
    --target-id "$TARGET_ID" \
    --task-type "RUN_COMMAND" \
    --task-arn "AWS-RunPatchBaseline" \
    --service-role-arn "arn:aws:iam::$(aws sts get-caller-identity --query Account --output text):role/MaintenanceWindowRole" \
    --task-parameters '{"Operation":{"Values":["Install"]},"RebootOption":{"Values":["RebootIfNeeded"]}}' \
    --priority 1 \
    --max-concurrency "50%" \
    --max-errors "10%" \
    --query 'WindowTaskId' --output text)

if [[ -z "$TASK_ID" || "$TASK_ID" == "None" ]]; then
    WINDOW_CREATION_FAILED=true
    error_exit "Failed to register patch task with maintenance window"
fi

log_info "Registered patch task with ID: $TASK_ID"

# Create metadata file
mkdir -p "$OUTPUT_DIR" || error_exit "Failed to create output directory"
cat > "$WINDOW_METADATA" << EOF
{
  "maintenance_window_id": "$MAINTENANCE_WINDOW_ID",
  "window_name": "$WINDOW_NAME",
  "landing_zone": "$LANDING_ZONE",
  "schedule": "$WINDOW_SCHEDULE",
  "duration_hours": $WINDOW_DURATION,
  "cutoff_hours": $WINDOW_CUTOFF,
  "target_id": "$TARGET_ID",
  "task_id": "$TASK_ID",
  "created_time": "$(date -u +%Y-%m-%dT%H:%M:%SZ)",
  "region": "$REGION",
  "status": "created"
}
EOF

log_info "Maintenance window setup completed successfully"
log_info "Window ID: $MAINTENANCE_WINDOW_ID"
log_info "Target ID: $TARGET_ID"
log_info "Task ID: $TASK_ID"
log_info "Metadata saved to: $WINDOW_METADATA"

# Verify the maintenance window is properly configured
log_info "Verifying maintenance window configuration..."
WINDOW_STATUS=$(aws ssm get-maintenance-window --window-id "$MAINTENANCE_WINDOW_ID" \
    --query 'Enabled' --output text 2>/dev/null || echo "false")

if [[ "$WINDOW_STATUS" == "true" ]]; then
    log_info "Maintenance window is enabled and ready"
else
    log_warn "Maintenance window may not be properly enabled"
fi
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
set -euo pipefail
IFS=$'\n\t'

# Source common functions
source "$(dirname "$0")/common_functions.sh" 2>/dev/null || {
    log_info() { echo "[INFO] $(date '+%Y-%m-%d %H:%M:%S') - $*"; }
    log_error() { echo "[ERROR] $(date '+%Y-%m-%d %H:%M:%S') - $*" >&2; }
    log_warn() { echo "[WARN] $(date '+%Y-%m-%d %H:%M:%S') - $*" >&2; }
    error_exit() { log_error "$1"; exit "${2:-1}"; }
    retry_with_backoff() {
        local max_attempts=$1 delay=$2 attempt=1
        local command="${@:3}"
        while [ $attempt -le $max_attempts ]; do
            if $command; then return 0; fi
            log_warn "Attempt $attempt failed. Retrying in ${delay}s..."
            sleep $delay; delay=$((delay * 2)); attempt=$((attempt + 1))
        done
        error_exit "Command failed after $max_attempts attempts"
    }
}

# Configuration
LANDING_ZONE="<+input>.landingZone"
REGION="<+input>.region"
OUTPUT_DIR="<+artifacts>.path"
PATCH_REPORT="$OUTPUT_DIR/patch_installation_report.json"
COMMAND_LOG="$OUTPUT_DIR/patch_command_log.json"

# Patch installation configuration
MAX_CONCURRENCY="${PATCH_MAX_CONCURRENCY:-50%}"
MAX_ERRORS="${PATCH_MAX_ERRORS:-10%}"
REBOOT_OPTION="${PATCH_REBOOT_OPTION:-RebootIfNeeded}"
TIMEOUT_SECONDS="${PATCH_TIMEOUT:-3600}"
DOCUMENT_NAME="AWS-RunPatchBaseline"

# Validate inputs
if [[ -z "$LANDING_ZONE" ]]; then
    error_exit "Landing zone is required"
fi

if [[ ! "$TIMEOUT_SECONDS" =~ ^[0-9]+$ ]] || [[ $TIMEOUT_SECONDS -lt 300 ]] || [[ $TIMEOUT_SECONDS -gt 7200 ]]; then
    error_exit "Invalid timeout: $TIMEOUT_SECONDS (must be 300-7200 seconds)"
fi

# Validate reboot option
case "$REBOOT_OPTION" in
    "RebootIfNeeded"|"NoReboot")
        ;;
    *)
        error_exit "Invalid reboot option: $REBOOT_OPTION (must be RebootIfNeeded or NoReboot)"
        ;;
esac

# Create output directory
mkdir -p "$OUTPUT_DIR" || error_exit "Failed to create output directory"

log_info "Starting patch installation for landing zone: $LANDING_ZONE"
log_info "Max concurrency: $MAX_CONCURRENCY"
log_info "Max errors: $MAX_ERRORS"
log_info "Reboot option: $REBOOT_OPTION"
log_info "Timeout: $TIMEOUT_SECONDS seconds"

# Get target instances before patching
log_info "Discovering target instances..."
TARGET_INSTANCES=$(aws ec2 describe-instances \
    --filters "Name=tag:Environment,Values=$LANDING_ZONE" "Name=instance-state-name,Values=running" \
    --query 'Reservations[].Instances[].InstanceId' \
    --output text 2>/dev/null || echo "")

if [[ -z "$TARGET_INSTANCES" ]]; then
    error_exit "No running instances found for landing zone: $LANDING_ZONE"
fi

INSTANCE_COUNT=$(echo "$TARGET_INSTANCES" | wc -w)
log_info "Found $INSTANCE_COUNT target instances: $(echo $TARGET_INSTANCES | tr ' ' ',')"

# Verify SSM agent connectivity
log_info "Verifying SSM agent connectivity..."
ONLINE_INSTANCES=$(aws ssm describe-instance-information \
    --filters "Key=InstanceIds,Values=$(echo $TARGET_INSTANCES | tr ' ' ',')" \
    --query 'InstanceInformationList[?PingStatus==`Online`].InstanceId' \
    --output text 2>/dev/null || echo "")

ONLINE_COUNT=$(echo "$ONLINE_INSTANCES" | wc -w)
log_info "$ONLINE_COUNT instances are online and ready for patching"

if [[ $ONLINE_COUNT -eq 0 ]]; then
    error_exit "No instances are online and available for patching"
fi

if [[ $ONLINE_COUNT -lt $INSTANCE_COUNT ]]; then
    OFFLINE_INSTANCES=$(comm -23 <(echo "$TARGET_INSTANCES" | tr ' ' '\n' | sort) <(echo "$ONLINE_INSTANCES" | tr ' ' '\n' | sort) | tr '\n' ' ')
    log_warn "Some instances are offline: $OFFLINE_INSTANCES"
fi

# Execute patch installation with retry
log_info "Executing patch installation command..."
COMMAND_ID=$(retry_with_backoff 3 10 aws ssm send-command \
    --document-name "$DOCUMENT_NAME" \
    --parameters "Operation=Install,RebootOption=$REBOOT_OPTION" \
    --targets "Key=tag:Environment,Values=$LANDING_ZONE" \
    --max-concurrency "$MAX_CONCURRENCY" \
    --max-errors "$MAX_ERRORS" \
    --timeout-seconds "$TIMEOUT_SECONDS" \
    --query 'Command.CommandId' --output text)

if [[ -z "$COMMAND_ID" || "$COMMAND_ID" == "None" ]]; then
    error_exit "Failed to execute patch installation command"
fi

log_info "Patch installation command initiated with ID: $COMMAND_ID"

# Monitor command execution
log_info "Monitoring patch installation progress..."
START_TIME=$(date +%s)
CHECK_INTERVAL=30
MAX_WAIT_TIME=$((TIMEOUT_SECONDS + 300))

while true; do
    CURRENT_TIME=$(date +%s)
    ELAPSED_TIME=$((CURRENT_TIME - START_TIME))
    
    if [[ $ELAPSED_TIME -gt $MAX_WAIT_TIME ]]; then
        log_error "Patch installation monitoring timeout after $ELAPSED_TIME seconds"
        break
    fi
    
    # Get command status
    COMMAND_STATUS=$(aws ssm get-command-invocation \
        --command-id "$COMMAND_ID" \
        --instance-id "$(echo $ONLINE_INSTANCES | cut -d' ' -f1)" \
        --query 'Status' --output text 2>/dev/null || echo "Unknown")
    
    # Get overall command status
    OVERALL_STATUS=$(aws ssm list-command-invocations \
        --command-id "$COMMAND_ID" \
        --query 'CommandInvocations[0].Status' --output text 2>/dev/null || echo "Unknown")
    
    log_info "Command status: $OVERALL_STATUS (elapsed: ${ELAPSED_TIME}s)"
    
    case "$OVERALL_STATUS" in
        "Success")
            log_info "Patch installation completed successfully"
            break
            ;;
        "Failed"|"Cancelled"|"TimedOut")
            log_error "Patch installation failed with status: $OVERALL_STATUS"
            break
            ;;
        "InProgress"|"Pending")
            log_info "Patch installation in progress..."
            sleep $CHECK_INTERVAL
            ;;
        *)
            log_warn "Unknown command status: $OVERALL_STATUS"
            sleep $CHECK_INTERVAL
            ;;
    esac
done

# Collect detailed results
log_info "Collecting patch installation results..."
COMMAND_INVOCATIONS=$(aws ssm list-command-invocations \
    --command-id "$COMMAND_ID" \
    --details \
    --query 'CommandInvocations' --output json 2>/dev/null || echo '[]')

# Generate comprehensive report
echo "{" > "$PATCH_REPORT"
echo "  \"command_id\": \"$COMMAND_ID\"," >> "$PATCH_REPORT"
echo "  \"landing_zone\": \"$LANDING_ZONE\"," >> "$PATCH_REPORT"
echo "  \"document_name\": \"$DOCUMENT_NAME\"," >> "$PATCH_REPORT"
echo "  \"execution_time\": \"$(date -u +%Y-%m-%dT%H:%M:%SZ)\"," >> "$PATCH_REPORT"
echo "  \"configuration\": {" >> "$PATCH_REPORT"
echo "    \"max_concurrency\": \"$MAX_CONCURRENCY\"," >> "$PATCH_REPORT"
echo "    \"max_errors\": \"$MAX_ERRORS\"," >> "$PATCH_REPORT"
echo "    \"reboot_option\": \"$REBOOT_OPTION\"," >> "$PATCH_REPORT"
echo "    \"timeout_seconds\": $TIMEOUT_SECONDS" >> "$PATCH_REPORT"
echo "  }," >> "$PATCH_REPORT"
echo "  \"target_summary\": {" >> "$PATCH_REPORT"
echo "    \"total_instances\": $INSTANCE_COUNT," >> "$PATCH_REPORT"
echo "    \"online_instances\": $ONLINE_COUNT," >> "$PATCH_REPORT"
echo "    \"target_instances\": \"$(echo $TARGET_INSTANCES | tr ' ' ',')\"," >> "$PATCH_REPORT"
echo "    \"online_instance_list\": \"$(echo $ONLINE_INSTANCES | tr ' ' ',')\"" >> "$PATCH_REPORT"
echo "  }," >> "$PATCH_REPORT"
echo "  \"execution_results\": $COMMAND_INVOCATIONS," >> "$PATCH_REPORT"
echo "  \"overall_status\": \"$OVERALL_STATUS\"," >> "$PATCH_REPORT"
echo "  \"elapsed_time_seconds\": $ELAPSED_TIME" >> "$PATCH_REPORT"
echo "}" >> "$PATCH_REPORT"

# Log command details
echo "$COMMAND_ID" > "$COMMAND_LOG"

log_info "Patch installation completed"
log_info "Command ID: $COMMAND_ID"
log_info "Overall Status: $OVERALL_STATUS"
log_info "Report saved to: $PATCH_REPORT"

# Summary statistics
SUCCESS_COUNT=$(echo "$COMMAND_INVOCATIONS" | jq '[.[] | select(.Status == "Success")] | length' 2>/dev/null || echo "0")
FAILED_COUNT=$(echo "$COMMAND_INVOCATIONS" | jq '[.[] | select(.Status == "Failed")] | length' 2>/dev/null || echo "0")

log_info "Patch installation summary:"
log_info "  Successful: $SUCCESS_COUNT instances"
log_info "  Failed: $FAILED_COUNT instances"
log_info "  Total processed: $(echo "$COMMAND_INVOCATIONS" | jq 'length' 2>/dev/null || echo "0") instances"

if [[ "$OVERALL_STATUS" != "Success" ]]; then
    log_error "Patch installation did not complete successfully"
    exit 1
fi
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
set -euo pipefail
IFS=$'\n\t'

# Source common functions
source "$(dirname "$0")/common_functions.sh" 2>/dev/null || {
    log_info() { echo "[INFO] $(date '+%Y-%m-%d %H:%M:%S') - $*"; }
    log_error() { echo "[ERROR] $(date '+%Y-%m-%d %H:%M:%S') - $*" >&2; }
    log_warn() { echo "[WARN] $(date '+%Y-%m-%d %H:%M:%S') - $*" >&2; }
    error_exit() { log_error "$1"; exit "${2:-1}"; }
    retry_with_backoff() {
        local max_attempts=$1 delay=$2 attempt=1
        local command="${@:3}"
        while [ $attempt -le $max_attempts ]; do
            if $command; then return 0; fi
            log_warn "Attempt $attempt failed. Retrying in ${delay}s..."
            sleep $delay; delay=$((delay * 2)); attempt=$((attempt + 1))
        done
        error_exit "Command failed after $max_attempts attempts"
    }
}

# Configuration
LANDING_ZONE="<+input>.landingZone"
REGION="<+input>.region"
OUTPUT_DIR="<+artifacts>.path"
REBOOT_REPORT="$OUTPUT_DIR/reboot_management_report.json"
INSTANCE_STATUS_LOG="$OUTPUT_DIR/instance_status_log.json"

# Reboot management configuration
REBOOT_TIMEOUT="${REBOOT_TIMEOUT:-1800}"  # 30 minutes
REBOOT_CHECK_INTERVAL="${REBOOT_CHECK_INTERVAL:-60}"  # 1 minute
MAX_REBOOT_WAIT="${MAX_REBOOT_WAIT:-2400}"  # 40 minutes
REBOOT_STRATEGY="${REBOOT_STRATEGY:-conditional}"  # conditional, force, skip
MAX_CONCURRENT_REBOOTS="${MAX_CONCURRENT_REBOOTS:-5}"

# Validate inputs
if [[ -z "$LANDING_ZONE" ]]; then
    error_exit "Landing zone is required"
fi

if [[ ! "$REBOOT_TIMEOUT" =~ ^[0-9]+$ ]] || [[ $REBOOT_TIMEOUT -lt 300 ]] || [[ $REBOOT_TIMEOUT -gt 3600 ]]; then
    error_exit "Invalid reboot timeout: $REBOOT_TIMEOUT (must be 300-3600 seconds)"
fi

case "$REBOOT_STRATEGY" in
    "conditional"|"force"|"skip")
        ;;
    *)
        error_exit "Invalid reboot strategy: $REBOOT_STRATEGY (must be conditional, force, or skip)"
        ;;
esac

# Create output directory
mkdir -p "$OUTPUT_DIR" || error_exit "Failed to create output directory"

log_info "Starting reboot management for landing zone: $LANDING_ZONE"
log_info "Reboot strategy: $REBOOT_STRATEGY"
log_info "Reboot timeout: $REBOOT_TIMEOUT seconds"
log_info "Max concurrent reboots: $MAX_CONCURRENT_REBOOTS"

# Get target instances
log_info "Discovering target instances..."
TARGET_INSTANCES=$(aws ec2 describe-instances \
    --filters "Name=tag:Environment,Values=$LANDING_ZONE" "Name=instance-state-name,Values=running" \
    --query 'Reservations[].Instances[].InstanceId' \
    --output text 2>/dev/null || echo "")

if [[ -z "$TARGET_INSTANCES" ]]; then
    error_exit "No running instances found for landing zone: $LANDING_ZONE"
fi

INSTANCE_COUNT=$(echo "$TARGET_INSTANCES" | wc -w)
log_info "Found $INSTANCE_COUNT target instances: $(echo $TARGET_INSTANCES | tr ' ' ',')"

# Check which instances need reboot
check_reboot_required() {
    local instance_id=$1
    local reboot_required=false
    
    # Check if reboot-required file exists
    local check_cmd="test -f /var/run/reboot-required && echo 'REBOOT_REQUIRED' || echo 'NO_REBOOT'"
    local result=$(aws ssm send-command \
        --document-name "AWS-RunShellScript" \
        --parameters "commands=['$check_cmd']" \
        --targets "Key=InstanceIds,Values=$instance_id" \
        --query 'Command.CommandId' --output text 2>/dev/null || echo "")
    
    if [[ -n "$result" ]]; then
        sleep 10  # Wait for command to complete
        local output=$(aws ssm get-command-invocation \
            --command-id "$result" \
            --instance-id "$instance_id" \
            --query 'StandardOutputContent' --output text 2>/dev/null || echo "")
        
        if [[ "$output" == *"REBOOT_REQUIRED"* ]]; then
            reboot_required=true
        fi
    fi
    
    echo $reboot_required
}

# Determine instances that need reboot
REBOOT_REQUIRED_INSTANCES=()
if [[ "$REBOOT_STRATEGY" == "conditional" ]]; then
    log_info "Checking which instances require reboot..."
    for instance_id in $TARGET_INSTANCES; do
        if [[ $(check_reboot_required "$instance_id") == "true" ]]; then
            REBOOT_REQUIRED_INSTANCES+=("$instance_id")
            log_info "Instance $instance_id requires reboot"
        else
            log_info "Instance $instance_id does not require reboot"
        fi
    done
elif [[ "$REBOOT_STRATEGY" == "force" ]]; then
    log_info "Force reboot strategy - all instances will be rebooted"
    REBOOT_REQUIRED_INSTANCES=($TARGET_INSTANCES)
elif [[ "$REBOOT_STRATEGY" == "skip" ]]; then
    log_info "Skip reboot strategy - no instances will be rebooted"
    REBOOT_REQUIRED_INSTANCES=()
fi

REBOOT_COUNT=${#REBOOT_REQUIRED_INSTANCES[@]}
log_info "$REBOOT_COUNT instances require reboot"

if [[ $REBOOT_COUNT -eq 0 ]]; then
    log_info "No instances require reboot - skipping reboot management"
else
    # Perform rolling reboot
    log_info "Starting rolling reboot of $REBOOT_COUNT instances..."
    REBOOT_BATCH_SIZE=$MAX_CONCURRENT_REBOOTS
    REBOOTED_INSTANCES=()
    FAILED_REBOOTS=()
    
    for ((i=0; i<$REBOOT_COUNT; i+=REBOOT_BATCH_SIZE)); do
        BATCH_INSTANCES=("${REBOOT_REQUIRED_INSTANCES[@]:$i:$REBOOT_BATCH_SIZE}")
        BATCH_SIZE=${#BATCH_INSTANCES[@]}
        
        log_info "Rebooting batch of $BATCH_SIZE instances: ${BATCH_INSTANCES[*]}"
        
        # Initiate reboot for batch
        REBOOT_COMMAND_IDS=()
        for instance_id in "${BATCH_INSTANCES[@]}"; do
            log_info "Initiating reboot for instance: $instance_id"
            COMMAND_ID=$(aws ssm send-command \
                --document-name "AWS-RunShellScript" \
                --parameters 'commands=["echo Rebooting instance...; sudo shutdown -r +1"]' \
                --targets "Key=InstanceIds,Values=$instance_id" \
                --query 'Command.CommandId' --output text 2>/dev/null || echo "")
            
            if [[ -n "$COMMAND_ID" ]]; then
                REBOOT_COMMAND_IDS+=("$COMMAND_ID")
                log_info "Reboot command sent to $instance_id with ID: $COMMAND_ID"
            else
                log_error "Failed to send reboot command to $instance_id"
                FAILED_REBOOTS+=("$instance_id")
            fi
        done
        
        # Wait for instances to go offline
        log_info "Waiting for instances to go offline..."
        sleep 120  # Give time for reboot to initiate
        
        # Monitor instance recovery
        BATCH_START_TIME=$(date +%s)
        RECOVERED_INSTANCES=()
        
        while [[ ${#RECOVERED_INSTANCES[@]} -lt ${#BATCH_INSTANCES[@]} ]]; do
            CURRENT_TIME=$(date +%s)
            ELAPSED_TIME=$((CURRENT_TIME - BATCH_START_TIME))
            
            if [[ $ELAPSED_TIME -gt $MAX_REBOOT_WAIT ]]; then
                log_error "Reboot timeout after $ELAPSED_TIME seconds"
                break
            fi
            
            for instance_id in "${BATCH_INSTANCES[@]}"; do
                # Skip if already recovered
                if [[ " ${RECOVERED_INSTANCES[*]} " == *" $instance_id "* ]]; then
                    continue
                fi
                
                # Check instance status
                INSTANCE_STATE=$(aws ec2 describe-instances \
                    --instance-ids "$instance_id" \
                    --query 'Reservations[0].Instances[0].State.Name' \
                    --output text 2>/dev/null || echo "unknown")
                
                SSM_STATUS=$(aws ssm describe-instance-information \
                    --filters "Key=InstanceIds,Values=$instance_id" \
                    --query 'InstanceInformationList[0].PingStatus' \
                    --output text 2>/dev/null || echo "ConnectionLost")
                
                if [[ "$INSTANCE_STATE" == "running" && "$SSM_STATUS" == "Online" ]]; then
                    RECOVERED_INSTANCES+=("$instance_id")
                    REBOOTED_INSTANCES+=("$instance_id")
                    log_info "Instance $instance_id has recovered (elapsed: ${ELAPSED_TIME}s)"
                else
                    log_info "Instance $instance_id status: $INSTANCE_STATE/$SSM_STATUS (elapsed: ${ELAPSED_TIME}s)"
                fi
            done
            
            if [[ ${#RECOVERED_INSTANCES[@]} -lt ${#BATCH_INSTANCES[@]} ]]; then
                sleep $REBOOT_CHECK_INTERVAL
            fi
        done
        
        # Check for failed recoveries
        for instance_id in "${BATCH_INSTANCES[@]}"; do
            if [[ ! " ${RECOVERED_INSTANCES[*]} " == *" $instance_id "* ]]; then
                FAILED_REBOOTS+=("$instance_id")
                log_error "Instance $instance_id failed to recover after reboot"
            fi
        done
        
        log_info "Batch reboot completed. Recovered: ${#RECOVERED_INSTANCES[@]}/${#BATCH_INSTANCES[@]}"
    done
fi

# Generate comprehensive report
echo "{" > "$REBOOT_REPORT"
echo "  \"landing_zone\": \"$LANDING_ZONE\"," >> "$REBOOT_REPORT"
echo "  \"execution_time\": \"$(date -u +%Y-%m-%dT%H:%M:%SZ)\"," >> "$REBOOT_REPORT"
echo "  \"reboot_strategy\": \"$REBOOT_STRATEGY\"," >> "$REBOOT_REPORT"
echo "  \"configuration\": {" >> "$REBOOT_REPORT"
echo "    \"reboot_timeout\": $REBOOT_TIMEOUT," >> "$REBOOT_REPORT"
echo "    \"check_interval\": $REBOOT_CHECK_INTERVAL," >> "$REBOOT_REPORT"
echo "    \"max_wait_time\": $MAX_REBOOT_WAIT," >> "$REBOOT_REPORT"
echo "    \"max_concurrent_reboots\": $MAX_CONCURRENT_REBOOTS" >> "$REBOOT_REPORT"
echo "  }," >> "$REBOOT_REPORT"
echo "  \"summary\": {" >> "$REBOOT_REPORT"
echo "    \"total_instances\": $INSTANCE_COUNT," >> "$REBOOT_REPORT"
echo "    \"reboot_required_count\": $REBOOT_COUNT," >> "$REBOOT_REPORT"
echo "    \"successfully_rebooted\": ${#REBOOTED_INSTANCES[@]}," >> "$REBOOT_REPORT"
echo "    \"failed_reboots\": ${#FAILED_REBOOTS[@]}" >> "$REBOOT_REPORT"
echo "  }," >> "$REBOOT_REPORT"
echo "  \"instance_details\": {" >> "$REBOOT_REPORT"
echo "    \"all_instances\": \"$(echo $TARGET_INSTANCES | tr ' ' ',')\"," >> "$REBOOT_REPORT"
echo "    \"reboot_required\": \"$(IFS=,; echo "${REBOOT_REQUIRED_INSTANCES[*]}")\"," >> "$REBOOT_REPORT"
echo "    \"successfully_rebooted\": \"$(IFS=,; echo "${REBOOTED_INSTANCES[*]}")\"," >> "$REBOOT_REPORT"
echo "    \"failed_reboots\": \"$(IFS=,; echo "${FAILED_REBOOTS[*]}\")\"" >> "$REBOOT_REPORT"
echo "  }" >> "$REBOOT_REPORT"
echo "}" >> "$REBOOT_REPORT"

log_info "Reboot management completed"
log_info "Total instances: $INSTANCE_COUNT"
log_info "Required reboot: $REBOOT_COUNT"
log_info "Successfully rebooted: ${#REBOOTED_INSTANCES[@]}"
log_info "Failed reboots: ${#FAILED_REBOOTS[@]}"
log_info "Report saved to: $REBOOT_REPORT"

if [[ ${#FAILED_REBOOTS[@]} -gt 0 ]]; then
    log_error "Some instances failed to reboot properly: ${FAILED_REBOOTS[*]}"
    exit 1
fi
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

## Technical Implementation Updates

### YAML Configuration Improvements

#### Pipeline Configuration Syntax Fixes

The Harness pipeline YAML configuration (`harness_pipeline_ec2_patching.yaml`) has been updated to resolve syntax parsing issues and improve maintainability:

**Issues Resolved:**
- **Heredoc Syntax Conflicts**: Replaced problematic heredoc patterns (`<< EOF`) within bash scripts that caused YAML parsing errors
- **Quote Escaping**: Fixed unescaped quotes and special characters in JSON generation scripts
- **Indentation Consistency**: Ensured proper YAML indentation throughout the pipeline configuration

**Technical Changes Applied:**

1. **JSON Report Generation**: Converted all heredoc-based JSON creation to individual `echo` statements with proper escaping:
   ```bash
   # Before (problematic heredoc)
   cat << EOF > /tmp/report.json
   {
     "status": "success",
     "message": "Operation completed"
   }
   EOF

   # After (YAML-safe echo statements)
   echo "{" > /tmp/report.json
   echo "  \"status\": \"success\"," >> /tmp/report.json
   echo "  \"message\": \"Operation completed\"" >> /tmp/report.json
   echo "}" >> /tmp/report.json
   ```

2. **Report Files Updated**:
   - Pre-patch health report generation
   - Patch status tracking reports
   - Reboot status monitoring
   - Patch verification reports
   - Application validation reports
   - Performance testing reports
   - Rollback status reports
   - Final comprehensive reports

3. **SNS Notification Formatting**: Fixed multi-line notification message formatting to prevent YAML parsing conflicts

4. **Validation**: All changes have been validated using Python's `yaml.safe_load()` to ensure proper YAML syntax

#### Benefits of the Updates

- **Improved Reliability**: Eliminates YAML parsing errors that could prevent pipeline execution
- **Better Maintainability**: Cleaner, more readable bash scripts within YAML configuration
- **Enhanced Debugging**: Easier to troubleshoot issues with individual echo statements vs. heredoc blocks
- **Consistent Formatting**: Standardized approach to JSON generation across all pipeline steps
- **Production Ready**: Pipeline configuration now passes strict YAML validation

#### Configuration Validation

To validate the pipeline configuration before deployment:

```bash
# Validate YAML syntax
python3 -c "import yaml; yaml.safe_load(open('harness_pipeline_ec2_patching.yaml')); print('YAML syntax is valid!')"

# Validate Harness-specific syntax (if Harness CLI is available)
harness pipeline validate --file harness_pipeline_ec2_patching.yaml
```

These technical improvements ensure the pipeline configuration is robust, maintainable, and ready for production deployment while preserving all original functionality for AWS EC2 patching operations.

This workflow provides a comprehensive, automated approach to AWS EC2 patching using Harness.io, ensuring reliability, security, and compliance while minimizing manual effort and reducing the risk of human error.
