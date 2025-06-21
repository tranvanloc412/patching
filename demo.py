#!/usr/bin/env python3
"""
Demo script for the CMS Patching Tool

This script demonstrates the capabilities of the refactored patching system
with the new core architecture and clean separation of concerns.
"""

import asyncio
import logging
import sys
from pathlib import Path
from datetime import datetime

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent))

from core.services import (
    ConfigService,
    WorkflowOrchestrator,
    ScannerService,
    ValidationService
)
from core.models.config import Environment
from infrastructure.aws import AWSSessionManager
from infrastructure.storage import FileStorage, JSONHandler


def print_separator(title: str, width: int = 80) -> None:
    """Print a formatted separator with title."""
    print("\n" + "=" * width)
    print(f" {title} ".center(width, "="))
    print("=" * width)


def print_subsection(title: str, width: int = 60) -> None:
    """Print a formatted subsection header."""
    print(f"\n{'-' * width}")
    print(f" {title}")
    print(f"{'-' * width}")


async def demo_config_service() -> None:
    """Demonstrate configuration service capabilities."""
    print_separator("Configuration Service Demo")
    
    try:
        config_service = ConfigService()
        
        # Load configuration
        print("Loading configuration from config.yml...")
        await config_service.load_config('config.yml')
        
        # Get environment configurations
        print("\nAvailable environments:")
        for env in [Environment.NONPROD, Environment.PROD]:
            env_config = config_service.get_environment_config(env)
            if env_config:
                print(f"  - {env.value}: {env_config.aws.region} (role: {env_config.aws.role_name})")
        
        # Get workflow configuration
        workflow_config = config_service.get_workflow_config()
        print(f"\nWorkflow configuration loaded:")
        print(f"  - Phases: {len(workflow_config.phases)}")
        print(f"  - Timeout: {workflow_config.timeout_minutes} minutes")
        print(f"  - Parallel execution: {workflow_config.parallel_execution}")
        
        print("✅ Configuration service demo completed successfully")
        
    except Exception as e:
        print(f"❌ Configuration service demo failed: {str(e)}")


async def demo_scanner_service() -> None:
    """Demonstrate scanner service capabilities."""
    print_separator("Scanner Service Demo")
    
    try:
        # Initialize services
        config_service = ConfigService()
        await config_service.load_config('config.yml')
        
        # Mock AWS session manager for demo
        session_manager = AWSSessionManager(
            default_region='ap-southeast-2',
            role_name='CMS-CrossAccount-Role'
        )
        
        scanner_service = ScannerService(
            config_service=config_service,
            session_manager=session_manager
        )
        
        print("Scanner service initialized successfully")
        print("\nNote: In a real environment, this would:")
        print("  1. Connect to AWS accounts using cross-account roles")
        print("  2. Discover EC2 instances in specified landing zones")
        print("  3. Enrich instance data with SSM information")
        print("  4. Apply filters based on configuration")
        print("  5. Validate instances for patching readiness")
        
        # Simulate scanning (without actual AWS calls)
        print("\n🔍 Simulating instance discovery...")
        print("   Found 15 instances across 3 landing zones")
        print("   - 8 Linux instances (Amazon Linux 2, Ubuntu)")
        print("   - 7 Windows instances (Windows Server 2019/2022)")
        print("   - 12 instances with SSM agent online")
        print("   - 3 instances require SSM agent installation")
        
        print("✅ Scanner service demo completed successfully")
        
    except Exception as e:
        print(f"❌ Scanner service demo failed: {str(e)}")


async def demo_validation_service() -> None:
    """Demonstrate validation service capabilities."""
    print_separator("Validation Service Demo")
    
    try:
        # Initialize services
        config_service = ConfigService()
        await config_service.load_config('config.yml')
        
        session_manager = AWSSessionManager(
            default_region='ap-southeast-2',
            role_name='CMS-CrossAccount-Role'
        )
        
        validation_service = ValidationService(
            config_service=config_service,
            session_manager=session_manager
        )
        
        print("Validation service initialized successfully")
        print("\nValidation capabilities:")
        print("  ✓ Workflow configuration validation")
        print("  ✓ Landing zone configuration validation")
        print("  ✓ AWS connectivity validation")
        print("  ✓ Instance health validation")
        print("  ✓ Pre-patch readiness validation")
        
        # Simulate validation results
        print("\n🔍 Simulating validation checks...")
        print("\n📋 Configuration Validation:")
        print("   ✅ Landing zones configuration valid")
        print("   ✅ AWS settings valid")
        print("   ✅ Workflow phases configured correctly")
        print("   ✅ Safety settings validated")
        
        print("\n🏥 Instance Health Validation:")
        print("   ✅ EC2 instances running and accessible")
        print("   ✅ SSM connectivity established")
        print("   ✅ System resources sufficient")
        print("   ⚠️  2 instances have pending reboots")
        print("   ✅ Network connectivity verified")
        
        print("✅ Validation service demo completed successfully")
        
    except Exception as e:
        print(f"❌ Validation service demo failed: {str(e)}")


async def demo_storage_handlers() -> None:
    """Demonstrate storage handler capabilities."""
    print_separator("Storage Handlers Demo")
    
    try:
        # Initialize storage components
        file_storage = FileStorage()
        json_handler = JSONHandler(file_storage)
        
        print("Storage handlers initialized successfully")
        print("\nStorage capabilities:")
        print("  📁 File system operations (create, read, write, delete)")
        print("  📊 CSV handling for instance data")
        print("  📄 JSON handling for reports and configuration")
        print("  🌐 HTML report generation")
        print("  📋 XML data processing")
        
        # Demonstrate JSON handling
        demo_data = {
            'workflow_id': 'demo-workflow-001',
            'timestamp': datetime.now().isoformat(),
            'status': 'completed',
            'phases': [
                {'name': 'scanner', 'status': 'completed', 'duration': '2m 15s'},
                {'name': 'backup', 'status': 'completed', 'duration': '15m 30s'},
                {'name': 'validation', 'status': 'completed', 'duration': '1m 45s'}
            ],
            'metrics': {
                'instances_processed': 15,
                'backups_created': 15,
                'validation_passed': 13,
                'validation_warnings': 2
            }
        }
        
        # Create demo directory
        demo_dir = 'demo_output'
        file_storage.ensure_directory_exists(demo_dir)
        
        # Write demo JSON
        demo_json_path = f'{demo_dir}/demo_workflow_report.json'
        json_handler.write_json(demo_json_path, demo_data)
        
        print(f"\n📝 Created demo report: {demo_json_path}")
        
        # Read and validate
        read_data = json_handler.read_json(demo_json_path)
        print(f"   ✅ Successfully read {len(read_data)} top-level keys")
        
        # Get file info
        file_info = json_handler.get_json_info(demo_json_path)
        print(f"   📊 File size: {file_info['file_size']} bytes")
        print(f"   📊 Valid JSON: {file_info['valid_json']}")
        
        print("✅ Storage handlers demo completed successfully")
        
    except Exception as e:
        print(f"❌ Storage handlers demo failed: {str(e)}")


async def demo_workflow_orchestrator() -> None:
    """Demonstrate workflow orchestrator capabilities."""
    print_separator("Workflow Orchestrator Demo")
    
    try:
        print("Workflow Orchestrator capabilities:")
        print("  🔄 Complete pre-patch workflow execution")
        print("  📊 Phase-by-phase progress tracking")
        print("  ⚡ Parallel execution support")
        print("  🛡️  Error handling and recovery")
        print("  📈 Metrics collection and reporting")
        print("  🔍 Real-time status monitoring")
        
        print("\n🚀 Simulating workflow execution...")
        
        phases = [
            ('Scanner Phase', 'Discovering instances across landing zones'),
            ('AMI Backup Phase', 'Creating backup AMIs for all instances'),
            ('Server Start Phase', 'Starting stopped instances'),
            ('Validation Phase', 'Verifying pre-patch readiness')
        ]
        
        for i, (phase_name, description) in enumerate(phases, 1):
            print(f"\n📋 Phase {i}/4: {phase_name}")
            print(f"   {description}")
            
            # Simulate phase execution
            await asyncio.sleep(0.5)  # Simulate processing time
            
            if phase_name == 'AMI Backup Phase':
                print("   ⏳ Creating AMI backups (this may take 10-15 minutes)...")
                print("   ✅ 15/15 AMI backups completed successfully")
            elif phase_name == 'Scanner Phase':
                print("   🔍 Scanning 3 landing zones...")
                print("   ✅ Discovered 15 instances, 13 ready for patching")
            elif phase_name == 'Server Start Phase':
                print("   🔄 Starting 3 stopped instances...")
                print("   ✅ All instances started successfully")
            elif phase_name == 'Validation Phase':
                print("   🏥 Validating instance health and readiness...")
                print("   ✅ 13/15 instances passed validation")
                print("   ⚠️  2 instances have warnings (pending reboots)")
        
        print("\n🎉 Workflow completed successfully!")
        print("\n📊 Final Summary:")
        print("   • Total instances: 15")
        print("   • AMI backups created: 15")
        print("   • Instances ready for patching: 13")
        print("   • Instances with warnings: 2")
        print("   • Total execution time: ~18 minutes")
        
        print("✅ Workflow orchestrator demo completed successfully")
        
    except Exception as e:
        print(f"❌ Workflow orchestrator demo failed: {str(e)}")


def show_cli_examples() -> None:
    """Show CLI usage examples."""
    print_separator("CLI Usage Examples")
    
    examples = [
        (
            "Complete Workflow",
            "python main.py --workflow lz-example1 lz-example2",
            "Run the complete 4-phase pre-patch workflow"
        ),
        (
            "Scanner Only",
            "python main.py --scanner-only lz-example1",
            "Run only the instance discovery phase"
        ),
        (
            "Custom Environment",
            "python main.py --workflow lz-prod1 --environment prod",
            "Run workflow in production environment"
        ),
        (
            "Skip Phases",
            "python main.py --workflow lz-test --skip-phases backup validation",
            "Skip AMI backup and validation phases"
        ),
        (
            "Verbose Output",
            "python main.py --workflow lz-example1 --verbose",
            "Enable detailed logging output"
        ),
        (
            "Custom Config",
            "python main.py --workflow lz-example1 --config custom_config.yml",
            "Use a custom configuration file"
        )
    ]
    
    for title, command, description in examples:
        print_subsection(title)
        print(f"Command: {command}")
        print(f"Description: {description}")


def show_architecture_overview() -> None:
    """Show the new architecture overview."""
    print_separator("New Architecture Overview")
    
    print("🏗️  Core Architecture Components:")
    print("\n📦 Core Package:")
    print("   • interfaces/     - Abstract interfaces for all services")
    print("   • models/         - Data models and business logic")
    print("   • services/       - Service implementations")
    
    print("\n🔧 Infrastructure Package:")
    print("   • aws/            - AWS client implementations")
    print("   • storage/        - File and data storage handlers")
    
    print("\n✨ Key Improvements:")
    print("   ✅ Clean separation of concerns")
    print("   ✅ Dependency injection pattern")
    print("   ✅ Async/await support throughout")
    print("   ✅ Comprehensive error handling")
    print("   ✅ Type hints and validation")
    print("   ✅ Modular and testable design")
    print("   ✅ Configuration-driven workflows")
    print("   ✅ Multiple output formats (CSV, JSON, HTML, XML)")
    
    print("\n🔄 Workflow Phases:")
    phases = [
        "1. Scanner Phase - Instance discovery and enrichment",
        "2. AMI Backup Phase - Create backup AMIs",
        "3. Server Start Phase - Start stopped instances",
        "4. Validation Phase - Verify pre-patch readiness"
    ]
    for phase in phases:
        print(f"   {phase}")


async def main() -> None:
    """Main demo function."""
    print_separator("CMS Patching Tool - Architecture Demo", 100)
    print("Welcome to the demonstration of the refactored CMS Patching Tool!")
    print("This demo showcases the new clean architecture and improved capabilities.")
    
    # Show architecture overview
    show_architecture_overview()
    
    # Run service demos
    await demo_config_service()
    await demo_scanner_service()
    await demo_validation_service()
    await demo_storage_handlers()
    await demo_workflow_orchestrator()
    
    # Show CLI examples
    show_cli_examples()
    
    print_separator("Demo Complete", 100)
    print("🎉 The refactored CMS Patching Tool is ready for use!")
    print("\n📚 Next Steps:")
    print("   1. Update your config.yml with your specific settings")
    print("   2. Test the scanner phase with: python main.py --scanner-only <landing-zone>")
    print("   3. Run the complete workflow with: python main.py --workflow <landing-zone>")
    print("   4. Check the generated reports in the reports/ directory")
    print("\n📖 For more information, see the documentation in documents/")


if __name__ == '__main__':
    # Setup basic logging for demo
    logging.basicConfig(
        level=logging.INFO,
        format='%(levelname)s - %(message)s'
    )
    
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("\n\nDemo interrupted by user. Goodbye!")
    except Exception as e:
        print(f"\n\nDemo failed with error: {str(e)}")
        sys.exit(1)