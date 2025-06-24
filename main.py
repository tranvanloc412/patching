#!/usr/bin/env python3
"""
CMS Patching Tool - Main Entry Point

This is the main entry point for the AWS EC2 patching system.
It provides a command-line interface for running pre-patch workflows.
"""

import argparse
import asyncio
import logging
import sys
from pathlib import Path
from typing import List, Optional

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent))

from core.services.config_service import ConfigService
from core.orchestration.workflow_orchestrator import WorkflowOrchestrator
from core.services.scanner_service import ScannerService
from core.models.config import Environment, LogLevel
from infrastructure.aws.session_manager import AWSSessionManager
from infrastructure.storage.file_storage import FileStorage


def setup_logging(verbose: bool = False) -> None:
    """Setup logging configuration."""
    level = logging.DEBUG if verbose else logging.INFO
    logging.basicConfig(
        level=level,
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
        handlers=[
            logging.StreamHandler(sys.stdout),
            logging.FileHandler('patching.log')
        ]
    )


async def run_workflow(
    landing_zones: List[str],
    config_path: str = 'config.yml',
    environment: str = 'nonprod',
    verbose: bool = False,
    skip_phases: Optional[List[str]] = None
) -> bool:
    """Run the complete pre-patch workflow."""
    try:
        # Setup logging
        setup_logging(verbose)
        logger = logging.getLogger(__name__)
        
        logger.info(f"Starting pre-patch workflow for landing zones: {landing_zones}")
        
        # Initialize services
        config_service = ConfigService()
        await config_service.load_config(config_path)
        
        # Get workflow config
        workflow_config = config_service.get_workflow_config()
        if not workflow_config:
            logger.error("Workflow configuration not found")
            return False
        
        # Initialize AWS session manager
        session_manager = AWSSessionManager(
            default_region=workflow_config.aws.region,
            role_name=workflow_config.aws.role_name
        )
        
        # Initialize workflow orchestrator
        orchestrator = WorkflowOrchestrator(
            config_service=config_service,
            session_manager=session_manager
        )
        
        # Run workflow
        workflow_result = await orchestrator.run_prepatch_workflow(
            landing_zones=landing_zones,
            skip_phases=skip_phases or []
        )
        
        if workflow_result.status.name == 'COMPLETED':
            logger.info("Pre-patch workflow completed successfully")
            logger.info(f"Workflow ID: {workflow_result.workflow_id}")
            logger.info(f"Duration: {workflow_result.duration}")
            return True
        else:
            logger.error(f"Workflow failed with status: {workflow_result.status.name}")
            if workflow_result.errors:
                for error in workflow_result.errors:
                    logger.error(f"Error: {error}")
            return False
            
    except Exception as e:
        logger.error(f"Failed to run workflow: {str(e)}")
        return False


async def run_scanner_only(
    landing_zones: List[str],
    config_path: str = 'config.yml',
    environment: str = 'nonprod',
    verbose: bool = False
) -> bool:
    """Run only the scanner phase."""
    try:
        setup_logging(verbose)
        logger = logging.getLogger(__name__)
        
        logger.info(f"Running scanner for landing zones: {landing_zones}")
        
        # Initialize services
        config_service = ConfigService()
        await config_service.load_config(config_path)
        
        workflow_config = config_service.get_workflow_config()
        if not workflow_config:
            logger.error("Workflow configuration not found")
            return False
        
        session_manager = AWSSessionManager(
            default_region=workflow_config.aws.region,
            role_name=workflow_config.aws.role_name
        )
        
        scanner_service = ScannerService(
            config_service=config_service,
            session_manager=session_manager
        )
        
        # Run scanner
        instances = await scanner_service.scan_landing_zones(landing_zones)
        
        # Save results
        from datetime import datetime
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        csv_path = f"reports/scan_results_{timestamp}.csv"
        
        file_storage = FileStorage()
        await file_storage.write_file(csv_path, "instance_id,name,state,platform\n")
        for instance in instances:
            line = f"{instance.instance_id},{instance.name},{instance.status.value},{instance.platform.value}\n"
            await file_storage.append_file(csv_path, line)
        
        logger.info(f"Scanner completed. Found {len(instances)} instances")
        logger.info(f"Results saved to: {csv_path}")
        
        return True
        
    except Exception as e:
        logger.error(f"Failed to run scanner: {str(e)}")
        return False


def parse_arguments() -> argparse.Namespace:
    """Parse command line arguments."""
    parser = argparse.ArgumentParser(
        description='CMS Patching Tool - Pre-patch workflow automation',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Run complete workflow for specific landing zones
  python main.py --workflow lz-example1 lz-example2
  
  # Run scanner only
  python main.py --scanner-only lz-example1
  
  # Run with custom config and environment
  python main.py --workflow lz-example1 --config custom_config.yml --environment prod
  
  # Skip specific phases
  python main.py --workflow lz-example1 --skip-phases backup validation
        """
    )
    
    # Main action groups
    action_group = parser.add_mutually_exclusive_group(required=True)
    action_group.add_argument(
        '--workflow',
        nargs='+',
        metavar='LANDING_ZONE',
        help='Run complete pre-patch workflow for specified landing zones'
    )
    action_group.add_argument(
        '--scanner-only',
        nargs='+',
        metavar='LANDING_ZONE',
        help='Run only the scanner phase for specified landing zones'
    )
    
    # Configuration options
    parser.add_argument(
        '--config',
        default='config.yml',
        help='Path to configuration file (default: config.yml)'
    )
    parser.add_argument(
        '--environment',
        choices=['nonprod', 'prod'],
        default='nonprod',
        help='Target environment (default: nonprod)'
    )
    
    # Workflow options
    parser.add_argument(
        '--skip-phases',
        nargs='+',
        choices=['scanner', 'backup', 'start_servers', 'validation'],
        help='Skip specific workflow phases'
    )
    
    # Output options
    parser.add_argument(
        '--verbose', '-v',
        action='store_true',
        help='Enable verbose logging'
    )
    
    return parser.parse_args()


async def main() -> int:
    """Main entry point."""
    args = parse_arguments()
    
    try:
        if args.workflow:
            success = await run_workflow(
                landing_zones=args.workflow,
                config_path=args.config,
                environment=args.environment,
                verbose=args.verbose,
                skip_phases=args.skip_phases
            )
        elif args.scanner_only:
            success = await run_scanner_only(
                landing_zones=args.scanner_only,
                config_path=args.config,
                environment=args.environment,
                verbose=args.verbose
            )
        else:
            print("No action specified. Use --help for usage information.")
            return 1
        
        return 0 if success else 1
        
    except KeyboardInterrupt:
        print("\nOperation cancelled by user")
        return 1
    except Exception as e:
        print(f"Unexpected error: {str(e)}")
        return 1


if __name__ == '__main__':
    sys.exit(asyncio.run(main()))