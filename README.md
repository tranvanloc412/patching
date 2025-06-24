# AWS EC2 Patching Automation Tool

A streamlined Python-based automation tool for managing AWS EC2 instance patching workflows across multiple landing zones. This tool features a simplified architecture focused on core functionality with async support and improved maintainability.

## 🚀 Features

- **Simplified Architecture**: Clean, modular design with reduced complexity
- **Async/Await Support**: High-performance asynchronous operations
- **Multi-Landing Zone Support**: Handles multiple AWS landing zones with YAML configuration
- **Automated AMI Backup**: Creates AMI backups before patching operations
- **CSV Reporting**: Generates detailed CSV reports for workflow tracking
- **3-Phase Workflow**: Streamlined Scanner → AMI Backup → Server Manager workflow
- **Safety First**: Built-in validation and error handling
- **Type Safety**: Full type hints and validation throughout
- **Configuration Driven**: Simple YAML-based configuration management

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
│   └── storage/               # Basic file storage handlers
├── inventory/                  # Landing zone definitions
│   ├── nonprod_landing_zones.yml
│   └── prod_landing_zones.yml
├── tests/                      # Test suites
│   ├── unit/                  # Unit tests
│   ├── integration/           # Integration tests
│   └── fixtures/              # Test fixtures
├── documents/                  # Documentation
├── reports/                    # Generated CSV reports directory
├── main.py                     # CLI entry point
├── demo.py                     # Architecture demonstration
├── config.yml                  # Main configuration file
└── requirements.txt           # Python dependencies
```

## 🔄 Workflow Phases

The simplified pre-patch workflow consists of three main phases:

1. **Scanner Phase**: Discover and inventory EC2 instances across landing zones
2. **AMI Backup Phase**: Create backup AMIs for all discovered instances
3. **Server Manager Phase**: Manage instance states and prepare for patching

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
# Run complete 3-phase workflow
python main.py --landing-zones lz250nonprod

# Run with multiple landing zones
python main.py --landing-zones lz250nonprod,cmsnonprod

# Run with custom configuration
python main.py --config config.yml --landing-zones lz250nonprod
```

**Scanner only**:

```bash
# Scan instances across landing zones
python main.py --scanner-only --landing-zones lz250nonprod,cmsnonprod

# Scan with custom output directory
python main.py --scanner-only --landing-zones lz250nonprod --output-dir custom_reports/
```

### Configuration

The tool uses a simple YAML-based configuration file (`config.yml`):

```yaml
# Simplified Patching Tool Configuration
name: "Pre-Patch Workflow"

# Landing zones to process
landing_zones:
  - "lz250nonprod"
  - "cmsnonprod"

# AWS settings
aws:
  region: "ap-southeast-2"
  role_name: "CMS-CrossAccount-Role"
  timeout: 60
  max_retries: 3

# Phase settings
scanner:
  enabled: true
  timeout_minutes: 30
  max_concurrent: 10

ami_backup:
  enabled: true
  timeout_minutes: 60
  max_concurrent: 5

server_manager:
  enabled: true
  timeout_minutes: 10
  max_concurrent: 10

# Output settings
output_dir: "reports"
log_level: "INFO"
```

## 📊 Reports

The tool generates CSV reports for workflow tracking:

### CSV Reports

- **Instance Inventory**: Complete list of discovered EC2 instances
- **Landing Zone Details**: Account and region information
- **AMI Backup Status**: Backup creation status and AMI IDs
- **Instance States**: Current and target instance states
- **Workflow Progress**: Phase completion status and timestamps
- **Error Tracking**: Any issues encountered during execution

## 🏗️ Core Components

### Services

- **ConfigService**: Simple configuration management and validation
- **ScannerService**: EC2 instance discovery across landing zones
- **AMIBackupService**: Automated AMI backup creation
- **ServerManagerService**: Instance state management
- **WorkflowOrchestrator**: Streamlined 3-phase workflow coordination

### Infrastructure

- **AWS Clients**: EC2, SSM, STS service integrations
- **File Storage**: Basic CSV and file operations
- **Session Management**: Cross-account role assumption

### Models

- **Instance**: EC2 instance representation with metadata
- **WorkflowConfig**: Simple workflow execution parameters
- **PhaseResult**: Phase execution tracking and status

## 🔧 Configuration

### Landing Zones

Configure your landing zones in YAML files:

- `inventory/nonprod_landing_zones.yml` - NonProd environments
- `inventory/prod_landing_zones.yml` - Prod environments

### Main Configuration

Customize workflow behavior in `config.yml`:

```yaml
# Simplified configuration with 3-phase workflow
name: "Pre-Patch Workflow"

landing_zones:
  - "lz250nonprod"
  - "cmsnonprod"

aws:
  region: "ap-southeast-2"
  role_name: "CMS-CrossAccount-Role"

# Phase settings for Scanner, AMI Backup, and Server Manager
scanner:
  enabled: true
  timeout_minutes: 30
  max_concurrent: 10

ami_backup:
  enabled: true
  timeout_minutes: 60
  max_concurrent: 5

server_manager:
  enabled: true
  timeout_minutes: 10
  max_concurrent: 10
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

**Note**: The current test suite is minimal and needs expansion. See the [Configuration Guide](documents/configuration_guide.md) for testing recommendations.

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

Enable debug logging by setting the log level in `config.yml`:

```yaml
log_level: "DEBUG"
```

Or use a custom configuration file:

```bash
python main.py --config debug-config.yml --landing-zones lz250nonprod
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

**Note**: This tool has been simplified with a streamlined 3-phase architecture, reduced complexity, and improved maintainability. The focus is on core functionality with CSV reporting and essential pre-patch operations.

## 🔒 Security

- **Credentials**: Never commit AWS credentials to the repository
- **Permissions**: Follow principle of least privilege for AWS IAM roles
- **Validation**: All operations include comprehensive pre-checks
- **Backup**: AMI backups are created before any patching operations
- **Audit**: All actions are logged for compliance and troubleshooting
