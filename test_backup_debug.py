#!/usr/bin/env python3

import sys
import os
from datetime import datetime

# Add the project root to Python path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

print(f"[{datetime.now()}] Starting simple import test...")

try:
    print(f"[{datetime.now()}] Importing ConfigService...")
    from core.services.config_service import ConfigService
    print(f"[{datetime.now()}] ConfigService imported successfully")
    
    print(f"[{datetime.now()}] Importing AWSSessionManager...")
    from infrastructure.aws.session_manager import AWSSessionManager
    print(f"[{datetime.now()}] AWSSessionManager imported successfully")
    
    print(f"[{datetime.now()}] Importing EC2Client...")
    from infrastructure.aws.ec2_client import EC2Client
    print(f"[{datetime.now()}] EC2Client imported successfully")
    
    print(f"[{datetime.now()}] Importing AMIBackupService...")
    from core.services.ami_backup_service import AMIBackupService
    print(f"[{datetime.now()}] AMIBackupService imported successfully")
    
    print(f"[{datetime.now()}] Importing AMIBackup model...")
    from core.models.ami_backup import AMIBackup, BackupType
    print(f"[{datetime.now()}] AMIBackup model imported successfully")
    
    print(f"[{datetime.now()}] All imports successful!")
    
except Exception as e:
    print(f"[{datetime.now()}] Import error: {str(e)}")
    import traceback
    traceback.print_exc()
    sys.exit(1)

print(f"[{datetime.now()}] Test completed successfully!")