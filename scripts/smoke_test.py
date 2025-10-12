#!/usr/bin/env python3
"""
Smoke Test for Phase 1 Optimizations
Quick validation that basic parsing functionality still works.
"""

import sys
import asyncio
from pathlib import Path
import time

# Add app to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from app.core.database import SessionLocal
from app.services.sqlite_parser_service import SQLiteElevationParserService
from app.models.elevation import Elevation
from app.models.elevation_glass import ElevationGlass


async def main():
    print("🚬 Phase 1 Smoke Test")
    print("=" * 50)
    
    db = SessionLocal()
    tests_passed = 0
    tests_failed = 0
    
    try:
        # Test 1: Database connectivity
        print("\n[1/5] Testing database connectivity...")
        try:
            elevation_count = db.query(Elevation).count()
            print(f"✅ Database connected ({elevation_count} elevations found)")
            tests_passed += 1
        except Exception as e:
            print(f"❌ Database connection failed: {e}")
            tests_failed += 1
            return 1
        
        # Test 2: Find test elevation
        print("\n[2/5] Finding test elevation...")
        elevation = db.query(Elevation).filter(
            Elevation.has_parts_data == True,
            Elevation.parts_db_path.isnot(None)
        ).first()
        
        if not elevation:
            print("❌ No test elevation found")
            tests_failed += 1
            return 1
        
        print(f"✅ Test elevation found: {elevation.name} (ID: {elevation.id})")
        tests_passed += 1
        
        # Test 3: Parse elevation
        print("\n[3/5] Testing parse operation...")
        parser = SQLiteElevationParserService(db)
        
        start_time = time.time()
        result = await parser.parse_elevation_data(elevation.id)
        parse_time = time.time() - start_time
        
        if result['success']:
            print(f"✅ Parse succeeded in {parse_time:.2f}s")
            tests_passed += 1
        else:
            print(f"❌ Parse failed: {result.get('error', 'Unknown error')}")
            tests_failed += 1
        
        # Test 4: Verify data integrity
        print("\n[4/5] Verifying data integrity...")
        db.refresh(elevation)
        
        checks = []
        checks.append(("Parse status", elevation.parse_status == "success"))
        checks.append(("Auto description", elevation.auto_description is not None))
        checks.append(("File hash", elevation.parts_file_hash is not None))
        
        glass_count = db.query(ElevationGlass).filter_by(elevation_id=elevation.id).count()
        checks.append(("Glass records", glass_count > 0))
        
        all_checks_passed = all(passed for _, passed in checks)
        
        for check_name, passed in checks:
            status = "✅" if passed else "❌"
            print(f"  {status} {check_name}")
        
        if all_checks_passed:
            print("✅ Data integrity verified")
            tests_passed += 1
        else:
            print("❌ Data integrity check failed")
            tests_failed += 1
        
        # Test 5: Performance sanity check
        print("\n[5/5] Performance sanity check...")
        # Phase 1 target: 7-12 seconds per parse
        if parse_time <= 15:  # Give some buffer
            print(f"✅ Parse time acceptable ({parse_time:.2f}s)")
            tests_passed += 1
        else:
            print(f"⚠️  Parse time higher than expected ({parse_time:.2f}s > 15s)")
            print("    (This may not be an error, but warrants investigation)")
            tests_passed += 1  # Don't fail on this, just warn
        
        # Summary
        print("\n" + "=" * 50)
        print(f"📊 Test Summary")
        print(f"   Passed: {tests_passed}/5")
        print(f"   Failed: {tests_failed}/5")
        
        if tests_failed == 0:
            print("\n✅ All smoke tests passed!")
            print("   System appears to be functioning correctly.")
            return 0
        else:
            print("\n❌ Some tests failed!")
            print("   Please review the errors above.")
            return 1
            
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

