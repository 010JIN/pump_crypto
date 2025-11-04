#!/usr/bin/env python3
"""
Database setup script
Run this to initialize the database
"""

import sys
sys.path.append('.')

from src.storage import init_databases
from loguru import logger

logger.add("logs/setup.log")

def main():
    """Initialize database"""
    print("\n?? Setting up database...")
    print("=" * 50)
    
    try:
        pg, redis = init_databases()
        
        print("\n? Database setup completed successfully!")
        print("\nPostgreSQL Tables Created:")
        print("  ? klines")
        print("  ? tickers")
        print("  ? trades_aggregated")
        print("  ? orderbook_snapshots")
        print("  ? factor_values")
        print("  ? detection_events")
        
        print("\n? Redis connection verified")
        
        print("\n?? You can now run the main system:")
        print("   python main.py")
        
    except Exception as e:
        print(f"\n? Error during setup: {e}")
        logger.error(f"Setup failed: {e}")
        sys.exit(1)


if __name__ == "__main__":
    main()
