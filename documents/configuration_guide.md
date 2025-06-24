# CMS Patching Tool - Configuration Guide

This guide provides comprehensive information on configuring the CMS Patching Tool for your environment.

## Overview

The CMS Patching Tool uses YAML-based configuration files to control workflow behavior, AWS settings, and operational parameters. The simplified architecture focuses on a single main configuration file with clear, straightforward options.

## Main Configuration File

### Location

- **Primary**: `config.yml` (project root)
- **Alternative**: Custom path via `--config` CLI argument

### Structure

```yaml
# Simplified Patching Tool Configuration
name: "Pre-Patch Workflow"

# Landing zones to process
landing_zones:
  - "lz250nonprod"
  - "cmsnonprod"
  - "fotoolspreprod"

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
  retry_attempts: 2

ami_backup:
  enabled: true
  timeout_minutes: 60
  max_concurrent: 5
  retry_attempts: 2

server_manager:
  enabled: true
  timeout_minutes: 10
  max_concurrent: 10
  retry_attempts: 2

# Output settings
output_dir: "reports"
log_level: "INFO"

# Execution options
skip_backup: false
skip_validation: false
continue_on_error: true
```

## Configuration Sections

### 1. Workflow Settings

```yaml
name: "Pre-Patch Workflow"
```

- **name**: Descriptive name for the workflow (used in reports and logs)
- **Type**: String
- **Required**: Yes

### 2. Landing Zones

```yaml
landing_zones:
  - "lz250nonprod"
  - "cmsnonprod"
  - "fotoolspreprod"
```

- **landing_zones**: List of AWS landing zones to process
- **Type**: Array of strings
- **Required**: Yes
- **Examples**:
  - NonProd: `lz250nonprod`, `cmsnonprod`, `fotoolspreprod`
  - Prod: `lz250prod`, `cmsprod`, `fotoolsprod`

### 3. AWS Settings

```yaml
aws:
  region: "ap-southeast-2"
  role_name: "CMS-CrossAccount-Role"
  timeout: 60
  max_retries: 3
```

#### Parameters:

- **region**: AWS region for operations

  - **Type**: String
  - **Default**: "ap-southeast-2"
  - **Examples**: "us-east-1", "eu-west-1", "ap-southeast-2"

- **role_name**: IAM role name for cross-account access

  - **Type**: String
  - **Default**: "CMS-CrossAccount-Role"
  - **Required**: Yes

- **timeout**: AWS API call timeout in seconds

  - **Type**: Integer
  - **Default**: 60
  - **Range**: 30-300

- **max_retries**: Maximum retry attempts for AWS API calls
  - **Type**: Integer
  - **Default**: 3
  - **Range**: 1-5

### 4. Phase Settings

Each phase (Scanner, AMI Backup, Server Manager) has consistent configuration options:

```yaml
scanner:
  enabled: true
  timeout_minutes: 30
  max_concurrent: 10
  retry_attempts: 2
```

#### Common Phase Parameters:

- **enabled**: Whether the phase is active

  - **Type**: Boolean
  - **Default**: true

- **timeout_minutes**: Phase execution timeout

  - **Type**: Integer
  - **Scanner**: 30 minutes (default)
  - **AMI Backup**: 60 minutes (default)
  - **Server Manager**: 10 minutes (default)

- **max_concurrent**: Maximum concurrent operations

  - **Type**: Integer
  - **Scanner**: 10 (default)
  - **AMI Backup**: 5 (default)
  - **Server Manager**: 10 (default)

- **retry_attempts**: Number of retry attempts on failure
  - **Type**: Integer
  - **Default**: 2
  - **Range**: 0-5

### 5. Output Settings

```yaml
output_dir: "reports"
log_level: "INFO"
```

- **output_dir**: Directory for generated reports

  - **Type**: String
  - **Default**: "reports"
  - **Note**: Directory will be created if it doesn't exist

- **log_level**: Logging verbosity level
  - **Type**: String
  - **Options**: "DEBUG", "INFO", "WARNING", "ERROR"
  - **Default**: "INFO"

### 6. Execution Options

```yaml
skip_backup: false
skip_validation: false
continue_on_error: true
```

- **skip_backup**: Skip AMI backup phase

  - **Type**: Boolean
  - **Default**: false
  - **Use Case**: Testing or when backups are handled externally

- **skip_validation**: Skip validation checks

  - **Type**: Boolean
  - **Default**: false
  - **Use Case**: Quick runs or when validation is not required

- **continue_on_error**: Continue workflow on non-critical errors
  - **Type**: Boolean
  - **Default**: true
  - **Note**: Critical errors will still stop the workflow

## Landing Zone Configuration

### File Locations

- **NonProd**: `inventory/nonprod_landing_zones.yml`
- **Prod**: `inventory/prod_landing_zones.yml`

### Structure

```yaml
# Example: nonprod_landing_zones.yml
landing_zones:
  lz250nonprod:
    account_id: "123456789012"
    region: "ap-southeast-2"
    role_name: "CMS-CrossAccount-Role"
    description: "LZ250 NonProd Environment"

  cmsnonprod:
    account_id: "123456789013"
    region: "ap-southeast-2"
    role_name: "CMS-CrossAccount-Role"
    description: "CMS NonProd Environment"
```

## Environment-Specific Configurations

### NonProd Configuration Example

```yaml
name: "NonProd Pre-Patch Workflow"

landing_zones:
  - "lz250nonprod"
  - "cmsnonprod"
  - "fotoolspreprod"

aws:
  region: "ap-southeast-2"
  role_name: "CMS-CrossAccount-Role"
  timeout: 60
  max_retries: 3

# More aggressive settings for NonProd
scanner:
  enabled: true
  timeout_minutes: 20
  max_concurrent: 15
  retry_attempts: 1

ami_backup:
  enabled: true
  timeout_minutes: 45
  max_concurrent: 8
  retry_attempts: 1

server_manager:
  enabled: true
  timeout_minutes: 8
  max_concurrent: 15
  retry_attempts: 1

output_dir: "reports/nonprod"
log_level: "DEBUG"
continue_on_error: true
```

### Prod Configuration Example

```yaml
name: "Production Pre-Patch Workflow"

landing_zones:
  - "lz250prod"
  - "cmsprod"
  - "fotoolsprod"

aws:
  region: "ap-southeast-2"
  role_name: "CMS-CrossAccount-Role"
  timeout: 90
  max_retries: 5

# Conservative settings for Production
scanner:
  enabled: true
  timeout_minutes: 45
  max_concurrent: 5
  retry_attempts: 3

ami_backup:
  enabled: true
  timeout_minutes: 90
  max_concurrent: 3
  retry_attempts: 3

server_manager:
  enabled: true
  timeout_minutes: 15
  max_concurrent: 5
  retry_attempts: 3

output_dir: "reports/prod"
log_level: "INFO"
continue_on_error: false
```

## Configuration Validation

The tool automatically validates configuration on startup:

### Required Fields

- `name`
- `landing_zones` (at least one)
- `aws.region`
- `aws.role_name`

### Validation Rules

- Timeout values must be positive integers
- Concurrency values must be between 1 and 50
- Retry attempts must be between 0 and 5
- Log level must be valid (DEBUG, INFO, WARNING, ERROR)
- Landing zones must exist in inventory files

### Error Handling

If configuration validation fails:

1. Tool displays specific error messages
2. Execution stops before any AWS operations
3. Suggested fixes are provided

## Best Practices

### 1. Environment Separation

- Use separate configuration files for different environments
- Store configurations in version control
- Use descriptive names for workflows

### 2. Performance Tuning

- **NonProd**: Higher concurrency, shorter timeouts
- **Prod**: Lower concurrency, longer timeouts
- Monitor AWS API rate limits

### 3. Error Handling

- Set `continue_on_error: true` for NonProd
- Set `continue_on_error: false` for Prod
- Use appropriate retry attempts based on environment

### 4. Logging

- Use `DEBUG` for troubleshooting
- Use `INFO` for normal operations
- Use `WARNING` or `ERROR` for production monitoring

### 5. Output Management

- Use environment-specific output directories
- Implement log rotation for long-running operations
- Archive reports for compliance

## Troubleshooting

### Common Configuration Issues

1. **Invalid Landing Zone**

   ```plaintext
   Error: Landing zone 'invalid-lz' not found in inventory
   Solution: Check inventory files and ensure landing zone exists
   ```

2. **AWS Permission Issues**

   ```plaintext
   Error: Unable to assume role 'CMS-CrossAccount-Role'
   Solution: Verify IAM role exists and has correct trust policy
   ```

3. **Timeout Issues**

   ```plaintext
   Error: Phase timeout exceeded
   Solution: Increase timeout_minutes for the affected phase
   ```

4. **Concurrency Limits**

   ```plaintext
   Error: AWS API rate limit exceeded
   Solution: Reduce max_concurrent values
   ```

### Configuration Testing

Test your configuration with:

```bash
# Validate configuration only
python main.py --validate-config

# Test with scanner only
python main.py --scanner-only --landing-zones test-lz

# Dry run mode (if implemented)
python main.py --dry-run --landing-zones test-lz
```

## Advanced Configuration

### Custom Configuration Files

```bash
# Use custom configuration file
python main.py --config /path/to/custom-config.yml

# Environment-specific configs
python main.py --config configs/nonprod.yml
python main.py --config configs/prod.yml
```

### Configuration Overrides

CLI arguments can override configuration file settings:

```bash
# Override output directory
python main.py --output-dir /custom/path

# Override log level
python main.py --log-level DEBUG
```

## Security Considerations

### 1. Credential Management

- Never store AWS credentials in configuration files
- Use IAM roles and cross-account access
- Implement least-privilege access policies

### 2. Configuration Security

- Store configuration files securely
- Use version control with proper access controls
- Audit configuration changes

### 3. Network Security

- Ensure proper VPC and security group configurations
- Use private subnets where possible
- Implement network access controls

## Migration Guide

If migrating from the complex 4-phase workflow:

### 1. Configuration Changes

- Remove environment-specific sections
- Simplify phase configurations
- Update landing zone references

### 2. Workflow Changes

- 4-phase → 3-phase workflow
- Remove validation phase configurations
- Update CLI commands

### 3. Report Changes

- Multi-format → CSV only
- Update report processing scripts
- Adjust monitoring and alerting

## Support

For configuration assistance:

1. Check this guide for common scenarios
2. Review error messages for specific guidance
3. Test configurations in NonProd first
4. Use debug logging for troubleshooting
