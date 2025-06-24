# CMS Patching Tool - Architecture Flow (Table Format)

## Layer Overview

| Layer | Purpose | Components | Dependencies |
|-------|---------|------------|-------------|
| **Entry Point** | Application bootstrap | `main.py` | → Orchestration |
| **Interfaces** | Contracts/Abstractions | `IWorkflowOrchestrator`, `IScannerService`, `IAMIBackupService`, `IServerManagerService`, `IConfigService`, `IStorageService` | ← Services |
| **Orchestration** | Workflow coordination | `WorkflowOrchestrator` | → Services |
| **Services** | Domain logic | `ScannerService`, `AMIBackupService`, `ServerManagerService`, `ConfigService`, `StorageService` | → Models, Infrastructure |
| **Models** | Data structures | `Instance`, `AMIBackup`, `ServerOperation`, `WorkflowConfig`, `Report`, `LandingZone` | ← Services |
| **Infrastructure** | Technical components | `AWSSessionManager`, `EC2Client`, `SSMClient`, `STSClient`, `FileStorage`, `CSVHandler` | → External Systems |
| **External Systems** | Third-party services | `AWS EC2`, `AWS SSM`, `AWS STS`, `File System`, `Configuration Files` | ← Infrastructure |

## 3-Phase Workflow Coordination

| Phase | Service | Purpose | Models Used | Infrastructure Used |
|-------|---------|---------|-------------|--------------------|
| **Phase 1: Discovery** | `ScannerService` | • Scan EC2 instances<br/>• Validate targets<br/>• Generate instance list | `Instance`, `WorkflowResult` | `AWSSessionManager`, `EC2Client` |
| **Phase 2: Backup** | `AMIBackupService` | • Create AMI backups<br/>• Verify backup success<br/>• Update status | `AMIBackup` | `EC2Client` |
| **Phase 3: Patching** | `ServerManagerService` | • Apply patches<br/>• Restart services<br/>• Validate results | `ServerOperation` | `SSMClient` |
| **Support** | `ConfigService` | • Manage configuration<br/>• Validate settings | `WorkflowConfig` | `FileStorage` |
| **Support** | `StorageService` | • Data persistence<br/>• Generate reports | `Report`, `LandingZone` | `CSVHandler`, `FileStorage` |

## Service Dependencies Matrix

| Service | Interfaces | Models | Infrastructure | External Systems |
|---------|------------|--------|----------------|------------------|
| **ScannerService** | `IScannerService` | `Instance`, `WorkflowResult` | `AWSSessionManager`, `EC2Client` | `AWS EC2` |
| **AMIBackupService** | `IAMIBackupService` | `AMIBackup` | `EC2Client` | `AWS EC2` |
| **ServerManagerService** | `IServerManagerService` | `ServerOperation` | `SSMClient` | `AWS SSM` |
| **ConfigService** | `IConfigService` | `WorkflowConfig` | `FileStorage` | `Configuration Files`, `File System` |
| **StorageService** | `IStorageService` | `Report`, `LandingZone` | `CSVHandler`, `FileStorage` | `File System` |

## Infrastructure Components

| Component | Purpose | External System | Used By |
|-----------|---------|-----------------|----------|
| **AWSSessionManager** | AWS authentication & session management | `AWS STS` | `ScannerService` |
| **EC2Client** | EC2 operations (instances, AMIs) | `AWS EC2` | `ScannerService`, `AMIBackupService` |
| **SSMClient** | Systems Manager operations | `AWS SSM` | `ServerManagerService` |
| **STSClient** | Security Token Service | `AWS STS` | `AWSSessionManager` |
| **FileStorage** | File system operations | `File System` | `ConfigService`, `StorageService` |
| **CSVHandler** | CSV file operations | `File System` | `StorageService` |

## Data Flow Summary

### Request Flow (Top-Down)
```
main.py
  ↓
WorkflowOrchestrator
  ↓ (coordinates phases)
┌─────────────────┬─────────────────┬─────────────────┐
│ Phase 1         │ Phase 2         │ Phase 3         │
│ ScannerService  │ AMIBackupService│ ServerMgrService│
└─────────────────┴─────────────────┴─────────────────┘
  ↓                 ↓                 ↓
┌─────────────────┬─────────────────┬─────────────────┐
│ Instance        │ AMIBackup       │ ServerOperation │
│ WorkflowResult  │                 │                 │
└─────────────────┴─────────────────┴─────────────────┘
  ↓                 ↓                 ↓
┌─────────────────┬─────────────────┬─────────────────┐
│ EC2Client       │ EC2Client       │ SSMClient       │
│ SessionManager  │                 │                 │
└─────────────────┴─────────────────┴─────────────────┘
  ↓                 ↓                 ↓
┌─────────────────┬─────────────────┬─────────────────┐
│ AWS EC2         │ AWS EC2         │ AWS SSM         │
└─────────────────┴─────────────────┴─────────────────┘
```

### Support Services Flow
```
ConfigService ←→ WorkflowConfig ←→ FileStorage ←→ Configuration Files
StorageService ←→ Report/LandingZone ←→ CSVHandler/FileStorage ←→ File System
```

## Architecture Principles

| Principle | Implementation | Benefit |
|-----------|----------------|----------|
| **Dependency Inversion** | Inner layers don't depend on outer layers | Testability, flexibility |
| **Single Responsibility** | Each layer has one clear purpose | Maintainability, clarity |
| **Interface Segregation** | Specific interfaces for each service | Loose coupling, testability |
| **Separation of Concerns** | Business logic separated from infrastructure | Clean architecture, modularity |
| **Orchestration Pattern** | Centralized workflow coordination | Clear process flow, error handling |

## Key Benefits

| Aspect | Benefit | Implementation |
|--------|---------|----------------|
| **Testability** | Each component can be tested in isolation | Interface-based dependency injection |
| **Maintainability** | Changes in one layer don't affect others | Clear layer boundaries |
| **Scalability** | Easy to scale individual components | Modular service architecture |
| **Flexibility** | Easy to swap implementations | Abstract interfaces |
| **Reliability** | Centralized error handling and recovery | Orchestration layer coordination |
| **Observability** | Clear data flow and component interactions | Structured logging and monitoring points |

## Usage Scenarios

| Scenario | Entry Point | Flow | Output |
|----------|-------------|------|--------|
| **Full Patching Workflow** | `main.py` | All 3 phases sequentially | Complete patching report |
| **Discovery Only** | `demo.py` | Phase 1 only | Instance inventory |
| **Backup Verification** | Custom script | Phase 2 only | AMI backup status |
| **Configuration Validation** | Config tool | ConfigService only | Configuration report |

This table format provides a comprehensive yet readable overview of the architecture that can be easily maintained in documentation and version control systems.