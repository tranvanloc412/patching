# CMS AWS Patching – Migration to Harness-Based Automation

## Executive Summary

This document outlines the current AWS patching landscape for CMS and defines comprehensive requirements for migrating to **Harness-based MIS Patching Automation**. The migration aims to address existing pain points while maintaining operational excellence and compliance standards.

---

## 1. Current Patching Landscape

### 1.1 Scope & Coverage

| **Component**         | **Details**                                                         |
| --------------------- | ------------------------------------------------------------------- |
| **Primary Targets**   | • EC2 Instances<br>• Auto Scaling Groups (ASG)<br>• Nabserv Jenkins |
| **Operating Systems** | • Windows Server<br>• Amazon Linux<br>• RHEL/CentOS                 |
| **Landing Zones**     | 8 active LZs with varying patch schedules                           |

### 1.2 Patching Schedules

#### Standard Windows Patching

- **Non-Production**: Wednesday, 06:00-18:00 EST
- **Production**: Sunday, 06:00-18:00 EST

#### Custom Landing Zone Schedules

| **Landing Zone**   | **Environment** | **Schedule**       | **Window**  |
| ------------------ | --------------- | ------------------ | ----------- |
| **lz029 (EPM)**    | Non-Prod        | Monthly, Tuesday   | 16:00-00:00 |
|                    | Prod            | Monthly, Saturday  | 19:00-00:00 |
| **lz281 (MQ)**     | Non-Prod        | Weekly, Tue + Wed  | 17:00-20:00 |
|                    | Prod            | Weekly, Sunday     | 22:00-03:00 |
| **lz324 (Siebel)** | Non-Prod        | Monthly, Wednesday | 17:00-06:00 |
|                    | Prod            | Monthly, Saturday  | 21:00-08:00 |

### 1.3 Zone-Based Patching

- **Enabled for**: `lz281prod`, `lz324prod`
- **Strategy**: Availability Zone sequential patching with approval gates

---

## 2. Current Architecture & Tooling

### 2.1 Core Components

| **Component**           | **Description**                                          | **Purpose**                                                        |
| ----------------------- | -------------------------------------------------------- | ------------------------------------------------------------------ |
| **Operation Dashboard** | Static site (`cmsaws-static`)                            | • Trigger patch runs<br>• Display reports<br>• Manual LZ selection |
| **IAM Hub Role**        | `AUR-Resources-AWS-cmshubnonprod-2FA-cms-jump-provision` | Central access point                                               |
| **IAM Spoke Roles**     | `HIPCMSProvisionSpokeRole` (per LZ)                      | Cross-account SSM permissions                                      |
| **SSM Documents**       | Custom documents per LZ                                  | Patch execution logic                                              |
| **AMI Backup System**   | Tagged with `managed_by=CMS`                             | Pre-patch rollback capability                                      |

### 2.2 Current Workflow

#### Pre-Patch Phase

1. **Access Control**: Assume hub role → access dashboard
2. **Backup Creation**: Manual LZ selection → create AMI backups
3. **Verification**: Confirm backup completion before proceeding

#### Patch Execution

1. **OS Selection**: Choose Linux or Windows patching
2. **Execution Method**:
   - On-demand SSM Run Command
   - Scheduled via EventBridge
3. **Monitoring**: Generate patch reports, re-queue failures
4. **AZ-Based Runs**: Use dedicated dashboard interface

#### Post-Patch Phase

1. **Notification**: Alert application teams for Technical Verification Testing (TVT)
2. **Issue Resolution**:
   - Retry following Monday (with approval)
   - Raise Change Request for deferred patching

### 2.3 Specialized Patching

#### Auto Scaling Groups

- **Target LZs**: lz175, lz249
- **Process**: Manual launch template update → latest HIP AMI → standard post-patch

#### Jenkins Infrastructure

- **Target LZs**: lz187, lz249
- **Process**: Dedicated Jenkins job → monitoring → standard post-patch

---

## 3. Current State Assessment

### 3.1 Strengths ✅

- **Reliable Triggers**: Dashboard-based on-demand execution
- **Linux Success Rate**: High patch success for Linux systems
- **Stable SSM Integration**: Consistent SSM Run Command performance
- **Backup Strategy**: Comprehensive AMI backup before patching

### 3.2 Critical Pain Points 🔴

| **Issue**                   | **Impact**              | **Affected Systems** |
| --------------------------- | ----------------------- | -------------------- |
| **Windows Patch Failures**  | High failure rate       | lz324nonprod/prod    |
| **SSM Agent Offline**       | No pre-check capability | Windows instances    |
| **SSM Document Versioning** | Operational overhead    | All LZs              |
| **Slow CR Approvals**       | Delayed remediation     | lz324prod, lz281prod |
| **Personal Token Usage**    | Security risk           | Patching automation  |
| **Manual Processes**        | Human error potential   | All workflows        |

---

## 4. Harness Migration Requirements

### 4.1 Platform Architecture

#### Core Infrastructure

- **Execution Environment**: Harness Delegates (Kubernetes pods)
- **Cost Management**: Cloud Cost Management (CCM) for spoke role assumption
- **Inventory Source**: GitHub repository via service account PAT
- **Orchestration**: SSM Fleet Manager for zero-touch patching
- **Backup Strategy**: Automated AMI creation before patch operations

### 4.2 Pipeline Architecture

#### Standard Patching Pipelines

| **Pipeline**               | **Purpose**               | **Inputs**        | **Outputs**       |
| -------------------------- | ------------------------- | ----------------- | ----------------- |
| **Update-Maintenance-Tag** | Set maintenance windows   | LZ list, schedule | Tagged instances  |
| **Patch**                  | Execute patching          | Tagged instances  | Patch results     |
| **Generate-Report**        | Create compliance reports | Patch results     | Formatted reports |

#### Functional Requirements

1. **End-to-End Automation**: Zero manual intervention for standard flows
2. **Flexible Triggers**: Support both ad-hoc and scheduled execution
3. **Error Handling**: Automatic retry logic with configurable thresholds
4. **Rollback Capability**: Automated rollback to pre-patch AMI state

#### Non-Functional Requirements

- **Performance**: Total maintenance window ≤ 6 hours
- **Scalability**: Support for instance auto-upgrade (below t3.medium)
- **Reliability**: 98% success rate target
- **Monitoring**: Real-time status updates and alerting

### 4.3 Custom AZ-by-AZ Patching

#### Enhanced Pipeline Features

- **Per-AZ Tagging**: Support availability zone-specific maintenance tags
- **Approval Gates**:
  - Pre-patch approval (asset team + stakeholders)
  - TVT approval before next AZ progression
- **Special Handling**: Windows Time Machine servers in lz324 exclusion

#### Workflow Requirements

1. **Sequential Processing**: One AZ at a time with approval checkpoints
2. **Stakeholder Integration**: Automated approval request routing
3. **Progress Tracking**: Real-time AZ completion status
4. **Rollback Scope**: Per-AZ rollback capability

### 4.4 Auto Scaling Group Automation

#### Stateless ASG Handling

- **Process**: Instance replacement with latest HIP AMI
- **Launch Template**: Automatic update with new AMI ID
- **Validation**: Post-replacement health checks

#### Stateful ASG Handling

- **Process**: In-place patching → AMI creation → launch template update
- **Data Preservation**: Ensure stateful data integrity
- **Rollback**: Maintain previous AMI for quick recovery

#### Terraform Integration

- **Drift Prevention**: Automatic commit of launch template IDs to TFE
- **Version Control**: Maintain infrastructure as code consistency
- **Approval Workflow**: Integration with TFE approval processes

### 4.5 Jenkins Infrastructure Automation

#### Nabserv Integration

- **Service Account**: Dedicated service account for pipeline triggers
- **Retry Logic**: Up to 3 automatic retries on network failures
- **Status Monitoring**: Real-time job execution tracking

#### Legacy Image Handling

- **Fallback Process**: `nef-jenkins-update` automation trigger
- **Inventory Refresh**: Automatic Jenkins inventory update
- **ECS Deployment**: Bastion host-based task redeployment

---

## 5. Security & Compliance

### 5.1 Authentication & Authorization

- **Service Accounts**: Replace personal tokens with dedicated service accounts
- **Role-Based Access**: Granular permissions per team and function
- **Audit Trail**: Comprehensive logging of all patching activities

### 5.2 Compliance Framework

- **SOX Controls**: Automated evidence collection for financial systems
- **PCI Requirements**: Secure handling of payment card industry systems
- **Change Management**: Integration with existing CR processes

---

## 6. Success Metrics & KPIs

### 6.1 Performance Targets

- **Success Rate**: ≥ 98% patch success across all systems
- **Report Delivery**: < 15 minutes post-completion
- **Window Compliance**: 100% completion within maintenance windows
- **Rollback Time**: < 30 minutes for emergency rollbacks

### 6.2 Operational Metrics

- **Manual Intervention**: < 5% of patch cycles requiring manual intervention
- **Approval Time**: Average approval gate processing < 2 hours
- **Error Resolution**: 95% of failures auto-resolved through retry logic

---

## 7. Risk Management

### 7.1 Migration Risks

| **Risk**              | **Impact**           | **Mitigation**               |
| --------------------- | -------------------- | ---------------------------- |
| **Pipeline Failures** | Service disruption   | Parallel testing environment |
| **Permission Issues** | Access denied errors | Comprehensive IAM testing    |
| **Data Loss**         | System corruption    | Mandatory AMI backups        |
| **Rollback Failures** | Extended outages     | Automated rollback testing   |

### 7.2 Operational Risks

- **Harness Delegate Failures**: Multi-AZ delegate deployment
- **GitHub Unavailability**: Local inventory caching
- **SSM Fleet Issues**: Fallback to direct SSM commands

---

## 8. Implementation Roadmap

### Phase 1: Foundation (Weeks 1-4)

- Harness delegate setup and configuration
- Service account creation and permission assignment
- Basic pipeline development and testing

### Phase 2: Core Functionality (Weeks 5-8)

- Standard patching pipeline implementation
- AMI backup automation
- Report generation system

### Phase 3: Advanced Features (Weeks 9-12)

- AZ-by-AZ patching capability
- ASG and Jenkins automation
- Approval gate integration

### Phase 4: Migration & Validation (Weeks 13-16)

- Parallel running with existing system
- User acceptance testing
- Full migration and legacy system decommission

---

## 9. Open Questions & Next Steps

### 9.1 Technical Decisions

1. **Delegate Sizing**: Confirm resource requirements and EKS namespace allocation
2. **Patch Classification**: Standardize critical/important/optional patch queues
3. **Rollback Strategy**: Choose between AMI re-launch vs. Systems Manager Automation
4. **Monitoring Integration**: Define alerting thresholds and escalation procedures

### 9.2 Process Alignment

1. **Approval Workflows**: Map current CR processes to Harness approval gates
2. **Team Training**: Develop training materials for operations teams
3. **Documentation**: Create runbooks for common scenarios
4. **Support Model**: Define L1/L2/L3 support responsibilities

### 9.3 Validation Requirements

1. **Testing Strategy**: Comprehensive test plan for all scenarios
2. **Performance Benchmarks**: Baseline current system performance
3. **Rollback Procedures**: Document and test emergency procedures
4. **Compliance Validation**: Ensure audit requirements are met

---

_Document Version: 2.0_  
_Last Updated: [Current Date]_  
_Next Review: [Date + 30 days]_
