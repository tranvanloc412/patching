#!/usr/bin/env python3

import asyncio
import sys
import os
import argparse
from datetime import datetime

# Add the project root to Python path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from core.models.ami_backup import BackupType
from backup_server import ServerBackup, setup_logging

def parse_arguments():
    """Parse command line arguments."""
    parser = argparse.ArgumentParser(description="Test AMI Backup Server with Timeout")
    parser.add_argument(
        "--instance-id",
        required=True,
        help="EC2 instance ID to backup"
    )
    parser.add_argument(
        "--landing-zone",
        required=True,
        help="Landing zone identifier"
    )
    parser.add_argument(
        "--backup-type",
        choices=["pre-patch", "post-patch", "manual"],
        default="pre-patch",
        help="Type of backup to perform"
    )
    parser.add_argument(
        "--log-level",
        choices=["DEBUG", "INFO", "WARNING", "ERROR"],
        default="INFO",
        help="Logging level"
    )
    return parser.parse_args()

async def main():
    """Main entry point with timeout."""
    print(f"[{datetime.now()}] Starting backup test with timeout...")
    
    args = parse_arguments()
    print(f"[{datetime.now()}] Arguments parsed: instance_id={args.instance_id}, landing_zone={args.landing_zone}")
    
    # Setup logging
    print(f"[{datetime.now()}] Setting up logging...")
    setup_logging(args.log_level)
    print(f"[{datetime.now()}] Logging setup complete")
    
    # Convert backup type string to enum
    backup_type_map = {
        "pre-patch": BackupType.PRE_PATCH,
        "post-patch": BackupType.POST_PATCH,
        "manual": BackupType.MANUAL
    }
    backup_type = backup_type_map[args.backup_type]
    print(f"[{datetime.now()}] Backup type: {backup_type}")
    
    # Initialize backup tool
    print(f"[{datetime.now()}] Initializing ServerBackup...")
    backup_tool = ServerBackup()
    print(f"[{datetime.now()}] ServerBackup initialized")
    
    # Run with timeout
    print(f"[{datetime.now()}] Running backup with 60 second timeout...")
    try:
        success = await asyncio.wait_for(
            backup_tool.run(args.instance_id, args.landing_zone, backup_type),
            timeout=60.0
        )
        print(f"[{datetime.now()}] Backup completed: {success}")
        return success
    except asyncio.TimeoutError:
        print(f"[{datetime.now()}] Backup timed out after 60 seconds")
        return False
    except Exception as e:
        print(f"[{datetime.now()}] Error during backup: {str(e)}")
        import traceback
        traceback.print_exc()
        return False

if __name__ == "__main__":
    try:
        success = asyncio.run(main())
        sys.exit(0 if success else 1)
    except KeyboardInterrupt:
        print(f"[{datetime.now()}] Interrupted by user")
        sys.exit(1)
    except Exception as e:
        print(f"[{datetime.now()}] Unexpected error: {str(e)}")
        import traceback
        traceback.print_exc()
        sys.exit(1)