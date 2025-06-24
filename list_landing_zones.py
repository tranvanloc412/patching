#!/usr/bin/env python3
"""
Utility script to list all available landing zones from configuration.

Usage:
    python list_landing_zones.py
    python list_landing_zones.py --detailed
"""

import argparse
import asyncio
import logging
import sys
from typing import List

from core.services.config_service import ConfigService
from core.utils.logger import setup_logger


class LandingZoneLister:
    """Utility to list available landing zones."""

    def __init__(self):
        self.logger = setup_logger(__name__)
        self.config_service = None

    async def initialize(self) -> None:
        """Initialize configuration service."""
        try:
            self.config_service = ConfigService()
            await self.config_service.load_config()
            self.logger.info("Configuration loaded successfully")
        except Exception as e:
            self.logger.error(f"Failed to load configuration: {e}")
            raise

    async def list_landing_zones(self, detailed: bool = False) -> List[dict]:
        """List all available landing zones."""
        try:
            landing_zones = await self.config_service.get_landing_zones()
            
            if not landing_zones:
                self.logger.warning("No landing zones found in configuration")
                return []

            print("\n=== Available Landing Zones ===")
            
            zone_info = []
            for lz in landing_zones:
                zone_data = {
                    'name': lz.name,
                    'account_id': getattr(lz, 'account_id', 'Not specified'),
                    'patch_enabled': getattr(lz, 'patch_enabled', 'Unknown')
                }
                zone_info.append(zone_data)
                
                if detailed:
                    print(f"\n📍 {lz.name}")
                    print(f"   Account ID: {zone_data['account_id']}")
                    print(f"   Patch Enabled: {zone_data['patch_enabled']}")
                    
                    # Show additional attributes if available
                    for attr in dir(lz):
                        if not attr.startswith('_') and attr not in ['name', 'account_id', 'patch_enabled']:
                            value = getattr(lz, attr)
                            if not callable(value):
                                print(f"   {attr.replace('_', ' ').title()}: {value}")
                else:
                    print(f"• {lz.name} (Account: {zone_data['account_id']})")
            
            if not detailed:
                print(f"\nTotal: {len(landing_zones)} landing zones")
                print("\nUse --detailed flag for more information")
            
            return zone_info
            
        except Exception as e:
            self.logger.error(f"Error listing landing zones: {e}")
            raise

    async def show_usage_examples(self, landing_zones: List[dict]) -> None:
        """Show usage examples with actual landing zone names."""
        if not landing_zones:
            return
            
        print("\n=== Usage Examples ===")
        
        # Show examples with first few landing zones
        examples = landing_zones[:3]  # Show up to 3 examples
        
        for i, lz in enumerate(examples):
            lz_name = lz['name']
            print(f"\n{i+1}. Backup server in {lz_name}:")
            print(f"   python backup_server.py --instance-id i-1234567890abcdef0 --landing-zone {lz_name}")
            
            if i == 0:  # Show additional examples for first landing zone
                print(f"\n   With specific backup type:")
                print(f"   python backup_server.py --instance-id i-1234567890abcdef0 --landing-zone {lz_name} --backup-type manual")
                
                print(f"\n   With debug logging:")
                print(f"   python backup_server.py --instance-id i-1234567890abcdef0 --landing-zone {lz_name} --log-level DEBUG")

    async def run(self, detailed: bool = False, show_examples: bool = True) -> bool:
        """Run the landing zone listing."""
        try:
            await self.initialize()
            landing_zones = await self.list_landing_zones(detailed)
            
            if show_examples and landing_zones:
                await self.show_usage_examples(landing_zones)
            
            return True
            
        except Exception as e:
            self.logger.error(f"Failed to list landing zones: {e}")
            return False


def parse_arguments():
    """Parse command line arguments."""
    parser = argparse.ArgumentParser(
        description="List all available landing zones from configuration"
    )
    
    parser.add_argument(
        "--detailed",
        action="store_true",
        help="Show detailed information for each landing zone"
    )
    
    parser.add_argument(
        "--no-examples",
        action="store_true",
        help="Don't show usage examples"
    )
    
    parser.add_argument(
        "--log-level",
        choices=["DEBUG", "INFO", "WARNING", "ERROR"],
        default="WARNING",
        help="Logging level (default: WARNING)"
    )
    
    return parser.parse_args()


def setup_logging(log_level: str) -> None:
    """Setup logging configuration."""
    logging.basicConfig(
        level=getattr(logging, log_level),
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
    )


async def main():
    """Main entry point."""
    args = parse_arguments()
    
    # Setup logging
    setup_logging(args.log_level)
    
    # List landing zones
    lister = LandingZoneLister()
    success = await lister.run(
        detailed=args.detailed,
        show_examples=not args.no_examples
    )
    
    # Exit with appropriate code
    sys.exit(0 if success else 1)


if __name__ == "__main__":
    asyncio.run(main())