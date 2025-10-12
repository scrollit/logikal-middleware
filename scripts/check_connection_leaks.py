#!/usr/bin/env python3
"""
Connection Leak Detection Script
Verifies that parsing operations don't leak SQLite connections.
"""

import gc
import sqlite3
import sys
import asyncio
from pathlib import Path

# Add app to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from app.core.database import SessionLocal
from app.services.sqlite_parser_service import SQLiteElevationParserService
from app.models.elevation import Elevation


def count_sqlite_connections():
    """Count open SQLite connections in memory"""
    gc.collect()  # Force collection first
    return len([obj for obj in gc.get_objects() if isinstance(obj, sqlite3.Connection)])


async def main():
    print("🔍 Connection Leak Detection")
    print("=" * 50)
    
    # Establish baseline
    initial_count = count_sqlite_connections()
    print(f"Initial SQLite connections: {initial_count}")
    
    # Create database session
    db = SessionLocal()
    
    try:
        # Find elevation with parts data
        elevation = db.query(Elevation).filter(
            Elevation.has_parts_data == True,
            Elevation.parts_db_path.isnot(None)
        ).first()
        
        if not elevation:
            print("❌ No test elevation found with parts data")
            return 1
        
        print(f"\nTesting with: {elevation.name} (ID: {elevation.id})")
        print(f"SQLite file: {elevation.parts_db_path}")
        
        # Run parsing operation
        parser = SQLiteElevationParserService(db)
        print("\nExecuting parse operation...")
        result = await parser.parse_elevation_data(elevation.id)
        
        print(f"Parse result: {'SUCCESS' if result['success'] else 'FAILED'}")
        
        # Check for leaks
        gc.collect()  # Force garbage collection
        final_count = count_sqlite_connections()
        leaked = final_count - initial_count
        
        print(f"\nFinal SQLite connections: {final_count}")
        print(f"Leaked connections: {leaked}")
        
        if leaked > 0:
            print("\n❌ FAILED: Connection leak detected!")
            print(f"   {leaked} connection(s) were not properly closed")
            return 1
        else:
            print("\n✅ PASSED: No connection leaks detected")
            return 0
            
    except Exception as e:
        print(f"\n❌ ERROR: {str(e)}")
        import traceback
        traceback.print_exc()
        return 1
    finally:
        db.close()


if __name__ == "__main__":
    exit_code = asyncio.run(main())
    sys.exit(exit_code)

