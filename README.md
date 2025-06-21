# AWS EC2 Patching Automation Tool

A comprehensive Python-based automation tool for managing AWS EC2 instance patching workflows across multiple landing zones and environments. This tool has been completely refactored with a clean architecture, async support, and improved maintainability.

## 🚀 Features

- **Clean Architecture**: Modular design with clear separation of concerns
- **Async/Await Support**: High-performance asynchronous operations
- **Multi-Environment Support**: Handles `nonprod` and `prod` environments
- **Automated AMI Backup**: Creates AMI backups before patching with configurable retention
- **Landing Zone Integration**: Supports multiple AWS landing zones with YAML-based configuration
- **Comprehensive Reporting**: Generates detailed reports in CSV, JSON, HTML, and XML formats
- **Flexible Workflow**: Supports both full orchestrated runs and individual phase execution
- **Safety First**: Built-in pre-checks and validation before any patching operations
- **Type Safety**: Full type hints and validation throughout
- **Configuration Driven**: YAML-based configuration with environment overrides

## 🏗️ Architecture Overview

The tool follows a clean architecture pattern with the following structure:

```plain
patching/
├── core/                       # Core business logic
│   ├── interfaces/            # Abstract interfaces
│   ├── models/                # Data models and business entities
│   └── services/              # Service implementations
├── infrastructure/             # External dependencies
│   ├── aws/                   # AWS client implementations
│   └── storage/               # File and data storage handlers
├── config/                     # Configuration files
│   ├── prepatch_config.yml    # Pre-patch workflow configuration
│   └── __init__.py
├── inventory/                  # Landing zone definitions
│   ├── nonprod_landing_zones.yml
│   ├── prod_landing_zones.yml
│   └── __init__.py
├── tests/                      # Test suites
│   ├── unit/                  # Unit tests
│   ├── integration/           # Integration tests
│   └── fixtures/              # Test fixtures
├── documents/                  # Documentation
├── reports/                    # Generated reports directory
├── main.py                     # CLI entry point
├── demo.py                     # Architecture demonstration
├── config.yml                  # Main configuration file
└── requirements.txt           # Python dependencies
```

## 🔄 Workflow Phases

The pre-patch workflow consists of four main phases:

1. **Scanner Phase**: Discover and inventory EC2 instances across landing zones
2. **AMI Backup Phase**: Create backup AMIs for all discovered instances
3. **Server Start Phase**: Start any stopped instances that need patching
4. **Validation Phase**: Verify instance health and pre-patch readiness

## 🛠️ Installation

### Prerequisites

- Python 3.8+
- AWS CLI configured with appropriate permissions
- Access to target AWS accounts and landing zones

### Setup

1. **Clone the repository**:

   ```bash
   git clone <repository-url>
   cd patching
   ```

2. **Create virtual environment**:

   ```bash
   python -m venv .venv
   source .venv/bin/activate  # On Windows: .venv\Scripts\activate
   ```

3. **Install dependencies**:

   ```bash
   pip install -r requirements.txt
   ```

## 🎯 Usage

### Quick Start

**Run the demo** to see the refactored architecture in action:

```bash
python demo.py
```

### CLI Commands

**View all available options**:

```bash
python main.py --help
```

**Full prepatch workflow**:

```bash
# Run complete 4-phase workflow
python main.py --landing-zones lz250nonprod --environment nonprod

# Run with custom configuration
python main.py --config config/prepatch_config.yml --landing-zones lz250nonprod

# Run with verbose logging
python main.py --landing-zones lz250nonprod --verbose
```

**Scanner only**:

```bash
# Scan instances across landing zones
python main.py --scanner-only --landing-zones lz250nonprod,cmsnonprod

# Scan with custom output directory
python main.py --scanner-only --landing-zones lz250nonprod --output-dir custom_reports/
```

### Environment Detection

The tool automatically detects environments based on landing zone names:

- **NonProd**: Landing zones containing `nonprod` (e.g., `lz250nonprod`, `cmsnonprod`)
- **Prod**: Landing zones containing `prod` (e.g., `lz250prod`, `fotoolsprod`, `cmsprod`)

### Configuration

The tool uses YAML-based configuration with environment-specific overrides:

```yaml
# config.yml
workflow:
  platform: "all" # windows, linux, or all
  skip_backup: false
  skip_validation: false
  ami_timeout: 30

aws:
  role_name: "PatchingRole"
  region: "us-east-1"

output:
  reports_dir: "reports"
  verbose: false
```

## 📊 Reports

The tool generates comprehensive reports in multiple formats:

### CSV Reports

- Instance inventory with patching status
- Environment classification
- AMI backup information
- Pre-check results

### JSON Reports

- Detailed metadata and structured data
- API-friendly format for integration
- Backup creation timestamps
- Retention policy information

### HTML Reports

- Interactive web-based reports
- Workflow summaries and dashboards
- Table-based data presentation

### XML Reports

- Structured data for enterprise systems
- Schema-validated output
- Integration with external tools

## 🏗️ Core Components

### Services

- **ConfigService**: Configuration management and validation
- **ScannerService**: EC2 instance discovery and inventory
- **AMIBackupService**: Automated AMI backup creation
- **ServerManagerService**: Instance state management
- **ValidationService**: Pre-patch health checks
- **ReportService**: Multi-format report generation
- **WorkflowOrchestrator**: End-to-end workflow coordination

### Infrastructure

- **AWS Clients**: EC2, SSM, STS service integrations
- **Storage Handlers**: File, CSV, JSON, XML, HTML operations
- **Session Management**: Cross-account role assumption

### Models

- **Instance**: EC2 instance representation
- **LandingZone**: AWS account and region configuration
- **WorkflowConfig**: Workflow execution parameters
- **ReportData**: Structured report information

## 🔧 Configuration

### Landing Zones

Configure your landing zones in YAML files:

- `inventory/nonprod_landing_zones.yml` - NonProd environments
- `inventory/prod_landing_zones.yml` - Prod environments

### Workflow Configuration

Customize workflow behavior in `config/prepatch_config.yml`:

```yaml
workflow:
  phases:
    scanner:
      enabled: true
      timeout: 300
    ami_backup:
      enabled: true
      retention_days: 7
    server_start:
      enabled: true
      wait_timeout: 600
    validation:
      enabled: true
      health_checks: true
```

## 🧪 Testing

**Run unit tests**:

```bash
python -m pytest tests/unit/
```

**Run integration tests**:

```bash
python -m pytest tests/integration/
```

**Run all tests with coverage**:

```bash
python -m pytest tests/ --cov=core --cov=infrastructure --cov-report=html
```

## 🚨 Troubleshooting

### Common Issues

**AWS Permissions**:

- Ensure your AWS credentials have the necessary permissions for EC2, SSM, and STS operations
- Verify cross-account role trust relationships are properly configured

**Landing Zone Configuration**:

- Check YAML syntax in landing zone files
- Verify account IDs and regions are correct
- Ensure role names match across environments

**Timeout Issues**:

- Increase timeout values in configuration for large environments
- Check network connectivity to AWS services
- Verify SSM agent is running on target instances

### Debug Mode

Enable verbose logging for detailed troubleshooting:

```bash
python main.py --landing-zones lz250nonprod --verbose
```

## 🤝 Contributing

1. **Fork the repository**
2. **Create a feature branch**: `git checkout -b feature/amazing-feature`
3. **Follow the architecture patterns**: Use the established service and interface patterns
4. **Add tests**: Ensure new code has appropriate unit and integration tests
5. **Update documentation**: Keep README and docstrings current
6. **Commit changes**: `git commit -m 'Add amazing feature'`
7. **Push to branch**: `git push origin feature/amazing-feature`
8. **Open a Pull Request**

### Code Standards

- Follow PEP 8 style guidelines
- Use type hints throughout
- Write comprehensive docstrings
- Maintain test coverage above 80%
- Use async/await for I/O operations

## 📝 License

This project is licensed under the MIT License - see the LICENSE file for details.

## 🆘 Support

For questions, issues, or contributions:

- **Issues**: Use GitHub Issues for bug reports and feature requests
- **Documentation**: Check the `documents/` directory for detailed guides
- **Architecture**: Review `demo.py` for implementation examples

---

**Note**: This tool has been completely refactored with a clean architecture, improved performance, and enhanced maintainability. The legacy code has been removed and replaced with a modern, type-safe implementation following best practices.

## 🔒 Security

- **Credentials**: Never commit AWS credentials to the repository
- **Permissions**: Follow principle of least privilege for AWS IAM roles
- **Validation**: All operations include comprehensive pre-checks
- **Backup**: AMI backups are created before any patching operations
- **Audit**: All actions are logged for compliance and troubleshooting
