# Full Patching Workflow Diagram

## Overview

This document provides a comprehensive flow diagram of the complete patching workflow, from initial configuration to final reporting.

## Full Patching Flow

```mermaid
flowchart TD
    A[Start: main.py] --> B{Configuration Mode?}
    B -->|CLI Args| C[Parse CLI Arguments]
    B -->|Config File| D[Load prepatch_config.yml]

    C --> E[Initialize Services]
    D --> E

    E --> F[ConfigService: Validate Configuration]
    F --> G{Valid Config?}
    G -->|No| H[Exit with Error]
    G -->|Yes| I[Initialize AWS Session]

    I --> J[STS Client: Assume Roles]
    J --> K{Role Assumption Success?}
    K -->|No| L[Exit with Authentication Error]
    K -->|Yes| M[Start Workflow Orchestrator]

    M --> N{Workflow Phase?}
    N -->|scan| O[SCAN PHASE]
    N -->|backup| P[BACKUP PHASE]
    N -->|precheck| Q[PRECHECK PHASE]
    N -->|patch| R[PATCH PHASE]
    N -->|full| S[ALL PHASES]

    %% SCAN PHASE
    O --> O1[ScannerService: Initialize]
    O1 --> O2[For Each Landing Zone]
    O2 --> O3[EC2Client: Describe Instances]
    O3 --> O4[Filter by Tags/Criteria]
    O4 --> O5[SSMClient: Get Instance Info]
    O5 --> O6[ValidationService: Validate Instance]
    O6 --> O7{More Landing Zones?}
    O7 -->|Yes| O2
    O7 -->|No| O8[Generate Scan Report]
    O8 --> O9[StorageService: Save Results]
    O9 --> END1[End: Scan Complete]

    %% BACKUP PHASE
    P --> P1[AMIBackupService: Initialize]
    P1 --> P2[Load Scan Results]
    P2 --> P3{Instances Found?}
    P3 -->|No| P4[Exit: No Instances to Backup]
    P3 -->|Yes| P5[For Each Instance]
    P5 --> P6[EC2Client: Create AMI]
    P6 --> P7[Add Backup Tags]
    P7 --> P8[Wait for AMI Creation]
    P8 --> P9{AMI Ready?}
    P9 -->|No| P10[Check Timeout]
    P10 --> P11{Timeout Reached?}
    P11 -->|Yes| P12[Mark as Failed]
    P11 -->|No| P8
    P9 -->|Yes| P13[Mark as Success]
    P12 --> P14{More Instances?}
    P13 --> P14
    P14 -->|Yes| P5
    P14 -->|No| P15[Generate Backup Report]
    P15 --> P16[StorageService: Save Results]
    P16 --> END2[End: Backup Complete]

    %% PRECHECK PHASE
    Q --> Q1[ServerManagerService: Initialize]
    Q1 --> Q2[Load Previous Results]
    Q2 --> Q3[For Each Instance]
    Q3 --> Q4[SSMClient: Check Connectivity]
    Q4 --> Q5{SSM Connected?}
    Q5 -->|No| Q6[Mark as Unreachable]
    Q5 -->|Yes| Q7[Run Pre-patch Checks]
    Q7 --> Q8[Check Disk Space]
    Q8 --> Q9[Check System Load]
    Q9 --> Q10[Check Critical Services]
    Q10 --> Q11[ValidationService: Validate Readiness]
    Q11 --> Q12{Ready for Patching?}
    Q12 -->|No| Q13[Mark as Not Ready]
    Q12 -->|Yes| Q14[Mark as Ready]
    Q6 --> Q15{More Instances?}
    Q13 --> Q15
    Q14 --> Q15
    Q15 -->|Yes| Q3
    Q15 -->|No| Q16[Generate Precheck Report]
    Q16 --> Q17[StorageService: Save Results]
    Q17 --> END3[End: Precheck Complete]

    %% PATCH PHASE
    R --> R1[ServerManagerService: Initialize]
    R1 --> R2[Load Precheck Results]
    R2 --> R3{Ready Instances Found?}
    R3 -->|No| R4[Exit: No Instances Ready]
    R3 -->|Yes| R5[For Each Ready Instance]
    R5 --> R6[SSMClient: Start Patch Session]
    R6 --> R7[Execute Patch Commands]
    R7 --> R8[Monitor Patch Progress]
    R8 --> R9{Patch Complete?}
    R9 -->|No| R10[Check Timeout]
    R10 --> R11{Timeout Reached?}
    R11 -->|Yes| R12[Mark as Failed]
    R11 -->|No| R8
    R9 -->|Yes| R13[Verify Patch Success]
    R13 --> R14{Verification Passed?}
    R14 -->|No| R15[Mark as Partial Success]
    R14 -->|Yes| R16[Mark as Success]
    R12 --> R17{More Instances?}
    R15 --> R17
    R16 --> R17
    R17 -->|Yes| R5
    R17 -->|No| R18[Generate Patch Report]
    R18 --> R19[StorageService: Save Results]
    R19 --> END4[End: Patch Complete]

    %% FULL WORKFLOW
    S --> S1[Execute SCAN PHASE]
    S1 --> S2{Scan Successful?}
    S2 -->|No| S3[Exit with Scan Error]
    S2 -->|Yes| S4[Execute BACKUP PHASE]
    S4 --> S5{Backup Successful?}
    S5 -->|No| S6[Exit with Backup Error]
    S5 -->|Yes| S7[Execute PRECHECK PHASE]
    S7 --> S8{Precheck Successful?}
    S8 -->|No| S9[Exit with Precheck Error]
    S8 -->|Yes| S10[Execute PATCH PHASE]
    S10 --> S11[Generate Final Report]
    S11 --> S12[ReportService: Create Multi-format Reports]
    S12 --> S13[Generate CSV Report]
    S13 --> S14[Generate JSON Report]
    S14 --> S15[Generate HTML Dashboard]
    S15 --> S16[Generate XML Report]
    S16 --> END5[End: Full Workflow Complete]

    %% Error Handling
    H --> ERROR[Error Handling]
    L --> ERROR
    P4 --> ERROR
    R4 --> ERROR
    S3 --> ERROR
    S6 --> ERROR
    S9 --> ERROR

    ERROR --> ERR1[Log Error Details]
    ERR1 --> ERR2[Generate Error Report]
    ERR2 --> ERR3[Cleanup Resources]
    ERR3 --> ERR4[Exit with Error Code]

    %% Styling
    classDef phaseBox fill:#e1f5fe,stroke:#01579b,stroke-width:2px
    classDef serviceBox fill:#f3e5f5,stroke:#4a148c,stroke-width:2px
    classDef decisionBox fill:#fff3e0,stroke:#e65100,stroke-width:2px
    classDef errorBox fill:#ffebee,stroke:#b71c1c,stroke-width:2px
    classDef endBox fill:#e8f5e8,stroke:#2e7d32,stroke-width:2px

    class O,P,Q,R,S phaseBox
    class O1,P1,Q1,R1,S12 serviceBox
    class B,G,K,N,P3,Q5,Q12,R3,R9,R14,S2,S5,S8 decisionBox
    class H,L,ERROR,ERR1,ERR2,ERR3,ERR4 errorBox
    class END1,END2,END3,END4,END5 endBox
```

## Phase Details

### 1. Initialization Phase

- **Configuration Loading**: Parse CLI arguments or load YAML configuration
- **Service Initialization**: Initialize all core services and AWS clients
- **Authentication**: Assume AWS roles for each landing zone
- **Validation**: Validate configuration and connectivity

### 2. Scan Phase

- **Instance Discovery**: Query EC2 instances across all landing zones
- **Filtering**: Apply tag-based and criteria-based filtering
- **Information Gathering**: Collect instance metadata via SSM
- **Validation**: Validate instance eligibility for patching
- **Reporting**: Generate scan results in multiple formats

### 3. Backup Phase

- **AMI Creation**: Create AMI backups for all eligible instances
- **Tagging**: Apply consistent tagging for backup tracking
- **Monitoring**: Monitor AMI creation progress with timeout handling
- **Verification**: Verify AMI creation success
- **Reporting**: Generate backup status reports

### 4. Precheck Phase

- **Connectivity Testing**: Verify SSM connectivity to instances
- **System Checks**: Validate disk space, system load, and critical services
- **Readiness Assessment**: Determine patch readiness for each instance
- **Risk Assessment**: Identify potential patching risks
- **Reporting**: Generate precheck results and recommendations

### 5. Patch Phase

- **Patch Execution**: Execute patching commands via SSM
- **Progress Monitoring**: Monitor patch progress with timeout handling
- **Verification**: Verify patch installation success
- **Status Tracking**: Track success, failure, and partial success states
- **Reporting**: Generate comprehensive patch results

### 6. Reporting Phase

- **Multi-format Output**: Generate CSV, JSON, HTML, and XML reports
- **Dashboard Creation**: Create interactive HTML dashboard
- **Data Aggregation**: Aggregate results across all phases
- **Compliance Reporting**: Generate compliance and audit reports

## Error Handling

### Error Categories

1. **Configuration Errors**: Invalid YAML, missing parameters
2. **Authentication Errors**: AWS role assumption failures
3. **Connectivity Errors**: Network or SSM connectivity issues
4. **Resource Errors**: Insufficient permissions or quotas
5. **Timeout Errors**: Operations exceeding configured timeouts
6. **Validation Errors**: Instance or system validation failures

### Error Response

- **Logging**: Comprehensive error logging with context
- **Reporting**: Error details included in reports
- **Cleanup**: Automatic resource cleanup on failures
- **Exit Codes**: Specific exit codes for different error types

## Configuration Options

### Workflow Control

```yaml
workflow:
  phases:
    scan: true
    backup: true
    precheck: true
    patch: false # Can be controlled separately

  timeouts:
    ami_creation: 1800 # 30 minutes
    patch_execution: 3600 # 60 minutes
    ssm_connection: 300 # 5 minutes
```

### Landing Zone Configuration

```yaml
landing_zones:
  - name: "prod-us-east-1"
    account_id: "123456789012"
    region: "us-east-1"
    role_arn: "arn:aws:iam::123456789012:role/PatchingRole"
    filters:
      tags:
        Environment: "production"
        PatchGroup: "group-1"
```

## Usage Examples

### Full Workflow

```bash
python main.py --landing-zones inventory/prod_landing_zones.yml --workflow full
```

### Individual Phases

```bash
# Scan only
python main.py --landing-zones inventory/prod_landing_zones.yml --workflow scan

# Backup only (requires previous scan)
python main.py --landing-zones inventory/prod_landing_zones.yml --workflow backup

# Precheck only (requires previous scan)
python main.py --landing-zones inventory/prod_landing_zones.yml --workflow precheck

# Patch only (requires previous precheck)
python main.py --landing-zones inventory/prod_landing_zones.yml --workflow patch
```

### Configuration-Driven Workflow

```bash
python main.py --config config/prepatch_config.yml
```

This flow diagram provides a complete overview of the patching workflow, showing all decision points, error handling, and the interaction between different services and phases.
