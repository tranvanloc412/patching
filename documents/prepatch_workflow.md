# Pre-Patch Workflow Implementation

## Overview

This document describes the refactored 4-phase pre-patch workflow implementation that provides a comprehensive, automated approach to preparing CMS environments for patching operations. The workflow has been completely redesigned with clean architecture principles, async support, and improved maintainability.

## Architecture

The implementation follows a clean architecture pattern with clear separation of concerns:

### Core Services

1. **`core/services/config_service.py`** - Configuration management and validation
2. **`core/services/scanner_service.py`** - EC2 instance discovery and inventory
3. **`core/services/ami_backup_service.py`** - Automated AMI backup creation
4. **`core/services/server_manager_service.py`** - Instance state management
5. **`core/services/validation_service.py`** - Pre-patch health checks
6. **`core/services/workflow_orchestrator.py`** - End-to-end workflow coordination
7. **`core/services/report_service.py`** - Multi-format report generation

### Infrastructure Layer

1. **`infrastructure/aws/`** - AWS service clients (EC2, SSM, STS)
2. **`infrastructure/storage/`** - File and data storage handlers
3. **`infrastructure/aws/session_manager.py`** - Cross-account role assumption

### Data Models

The workflow uses structured data models defined in `core/models/`:

- **Instance**: EC2 instance representation with status and metadata
- **LandingZone**: AWS account and region configuration
- **WorkflowConfig**: Workflow execution parameters
- **ReportData**: Structured report information
- **AMIBackup**: AMI backup metadata and status

## 4-Phase Workflow

### Phase 1: Scanner

- Discovers instances in specified landing zones or across all CMS environments
- Generates initial CSV report with instance details
- Captures initial state, platform, and SSM agent status

### Phase 2: AMI Backup

- Creates AMI backups for all discovered instances (running and stopped)
- Updates CSV with backup status, AMI IDs, and completion times
- Supports both synchronous and asynchronous backup operations

### Phase 3: Start Stopped Servers

- Identifies instances that were initially stopped
- Starts stopped instances to ensure they're running for patching
- Updates CSV with current instance states

### Phase 4: Validation

- Verifies all instances are in expected states
- Checks SSM agent connectivity
- Validates backup completion
- Generates final validation report

## CLI Commands

### Complete Workflow

```bash
# Run complete 4-phase workflow
python3 main.py --landing-zones lz250nonprod --environment nonprod
python3 main.py --landing-zones lz250nonprod,cmsnonprod --environment nonprod
```

### Scanner Only

```bash
# Phase 1: Scanner only
python3 main.py --scanner-only --landing-zones lz250nonprod
python3 main.py --scanner-only --landing-zones lz250nonprod,cmsnonprod
```

### Workflow Options

```bash
# Custom configuration file
python3 main.py --config config/prepatch_config.yml --landing-zones lz250nonprod

# Custom output directory
python3 main.py --landing-zones lz250nonprod --output-dir custom_reports/

# Verbose logging
python3 main.py --landing-zones lz250nonprod --verbose

# Environment-specific execution
python3 main.py --landing-zones lz250prod --environment prod
```

### Configuration-Driven Workflow

The new architecture uses YAML configuration files to control workflow behavior:

```yaml
# config/prepatch_config.yml
workflow:
  phases:
    scanner:
      enabled: true
      timeout: 300
    ami_backup:
      enabled: true
      retention_days: 7
      timeout: 1800
    server_start:
      enabled: true
      wait_timeout: 600
    validation:
      enabled: true
      health_checks: true
      ssm_ping: true
```

## Key Features

### Error Handling

- Comprehensive error handling with detailed logging
- Graceful failure handling - workflow continues even if individual operations fail
- Clear error reporting in final summary

### Flexibility

- Skip any phase using command-line flags
- Run individual phases independently
- Support for both landing zone-specific and environment-wide operations

### Monitoring

- Detailed progress reporting for each phase
- Comprehensive final summary with statistics
- CSV-based tracking for audit and review

### Integration

- Seamless integration with existing scanner and AMI backup functionality
- Maintains backward compatibility with existing commands
- Uses established AWS session management and role assumption

## Output Files

The workflow generates comprehensive reports in multiple formats in the `reports/` directory:

### CSV Reports

- **Instance inventory** with patching status and metadata
- **Environment classification** and landing zone mapping
- **AMI backup information** with timestamps and retention data
- **Validation results** and health check status

### JSON Reports

- **Structured metadata** for API integration
- **Detailed AMI backup results** with creation timestamps
- **Workflow execution logs** and performance metrics
- **Error reports** with detailed diagnostic information

### HTML Reports

- **Interactive dashboards** with workflow summaries
- **Table-based presentations** of instance data
- **Visual status indicators** for quick assessment
- **Drill-down capabilities** for detailed analysis

### XML Reports

- **Enterprise system integration** with schema validation
- **Structured data export** for external tools
- **Compliance reporting** with audit trails

## Usage Examples

### Typical Pre-Patch Sequence

1. **Initial Discovery and Preparation**

   ```bash
   python3 main.py --landing-zones lz250nonprod --environment nonprod --verbose
   ```

2. **Review Generated Reports**

   - Check multi-format reports in `reports/` directory
   - Verify instance discovery and backup status in HTML dashboard
   - Review JSON reports for detailed metadata

3. **Scanner-Only Execution for Quick Assessment**

   ```bash
   # Quick instance discovery without backup operations
   python3 main.py --scanner-only --landing-zones lz250nonprod
   ```

4. **Proceed with Patching**
   - Use the validated reports as input for patching operations
   - Reference instance IDs and AMI backup information

### Advanced Usage

```bash
# Multi-landing zone execution
python3 main.py --landing-zones lz250nonprod,cmsnonprod,fotoolsnonprod --environment nonprod

# Custom configuration with specific settings
python3 main.py --config config/custom_prepatch.yml --landing-zones lz250prod --environment prod

# Scanner with custom output directory
python3 main.py --scanner-only --landing-zones lz250nonprod --output-dir /custom/reports/
```

### Configuration-Based Workflow Control

```yaml
# Disable specific phases via configuration
workflow:
  phases:
    scanner:
      enabled: true
    ami_backup:
      enabled: false # Skip backup phase
    server_start:
      enabled: true
    validation:
      enabled: false # Skip validation phase
```

## Benefits

1. **Automation** - Reduces manual steps in pre-patch preparation
2. **Consistency** - Ensures standardized approach across environments
3. **Auditability** - CSV-based tracking provides clear audit trail
4. **Flexibility** - Modular design allows selective phase execution
5. **Integration** - Seamlessly works with existing tooling
6. **Reliability** - Comprehensive error handling and validation

## Testing

The refactored implementation includes a comprehensive testing framework:

```bash
# Run unit tests
python3 -m pytest tests/unit/ -v

# Run integration tests
python3 -m pytest tests/integration/ -v

# Run all tests with coverage
python3 -m pytest tests/ --cov=core --cov=infrastructure --cov-report=html

# View architecture demonstration
python3 demo.py
```

### Test Structure

- **Unit Tests**: Individual service and component testing
- **Integration Tests**: End-to-end workflow validation
- **Fixtures**: Reusable test data and mock configurations
- **Coverage Reports**: HTML coverage reports for code quality

## Benefits of the Refactored Architecture

1. **Clean Architecture** - Clear separation of concerns with defined layers
2. **Type Safety** - Full type hints and validation throughout
3. **Async Support** - High-performance asynchronous operations
4. **Testability** - Comprehensive test coverage with mocking capabilities
5. **Maintainability** - Modular design with dependency injection
6. **Extensibility** - Easy addition of new features and integrations
7. **Multi-format Reporting** - CSV, JSON, HTML, and XML output formats
8. **Configuration-Driven** - YAML-based workflow control

## Next Steps

This refactored pre-patch workflow provides the foundation for:

1. **Enhanced API Development** - RESTful APIs for external integration
2. **Real-time Monitoring** - WebSocket-based progress tracking
3. **Advanced Scheduling** - Cron-based automated execution
4. **Rollback Automation** - Automated instance restoration capabilities
5. **Integration Ecosystem** - ServiceNow, Jira, and ITSM integrations
6. **Performance Analytics** - Detailed metrics and performance optimization
7. **Multi-cloud Support** - Extension to Azure and GCP environments
8. **Compliance Automation** - Automated compliance reporting and validation

The clean architecture and modular design ensure easy extension and customization for evolving organizational needs while maintaining code quality and reliability.
