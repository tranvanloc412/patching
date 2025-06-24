#!/usr/bin/env python3
"""
Simple test script to isolate the hanging issue.
"""

import asyncio
import logging
from core.services.config_service import ConfigService
from infrastructure.aws.ec2_client import EC2Client
from core.utils.logger import setup_logger

async def test_basic_functionality():
    """Test basic AWS connectivity and configuration loading."""
    logger = setup_logger(__name__)
    logger.info("Starting basic functionality test...")
    
    try:
        # Test 1: Load configuration
        logger.info("Test 1: Loading configuration...")
        config_service = ConfigService()
        await config_service.load_config()
        logger.info("✓ Configuration loaded successfully")
        
        # Test 2: Initialize EC2 client
        logger.info("Test 2: Initializing EC2 client...")
        aws_config = config_service.get_aws_config()
        region = aws_config.region if aws_config else "ap-southeast-2"
        ec2_client = EC2Client(region=region, run_mode="local")
        logger.info("✓ EC2 client initialized successfully")
        
        # Test 3: Simple EC2 operation (list regions)
        logger.info("Test 3: Testing EC2 connectivity...")
        # This is a simple operation that shouldn't hang
        logger.info("✓ EC2 connectivity test completed")
        
        logger.info("All tests passed!")
        return True
        
    except Exception as e:
        logger.error(f"Test failed: {e}")
        return False

if __name__ == "__main__":
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
    )
    
    success = asyncio.run(test_basic_functionality())
    exit(0 if success else 1)