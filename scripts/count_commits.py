#!/usr/bin/env python3
"""
Database Commit Counter
Monitors and counts database commits during parsing to verify single-transaction optimization.
"""

import sys
import asyncio
from pathlib import Path
from unittest.mock import Mock, patch
import time

# Add app to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from app.core.database import SessionLocal
from app.services.sqlite_parser_service import SQLiteElevationParserService
from app.models.elevation import Elevation


class CommitCounter:
    """Tracks database commits and rollbacks"""
    
    def __init__(self):
        self.commits = []
        self.rollbacks = []
        self.original_commit = None
        self.original_rollback = None
    
    def track_commit(self):
        """Record a commit with timestamp"""
        self.commits.append(time.time())
        if self.original_commit:
            self.original_commit()
    
    def track_rollback(self):
        """Record a rollback with timestamp"""
        self.rollbacks.append(time.time())
        if self.original_rollback:
            self.original_rollback()
    
    def report(self):
        """Generate report of commits/rollbacks"""
        print(f"\n📊 Transaction Report")
        print("=" * 50)
        print(f"Total commits: {len(self.commits)}")
        print(f"Total rollbacks: {len(self.rollbacks)}")
        
        if self.commits:
            print(f"\nCommit timeline:")
            start = self.commits[0]
            for i, commit_time in enumerate(self.commits, 1):
                offset = commit_time - start
                print(f"  Commit #{i}: +{offset:.3f}s")
        
        if self.rollbacks:
            print(f"\nRollback timeline:")
            for i, rollback_time in enumerate(self.rollbacks, 1):
                offset = rollback_time - (self.commits[0] if self.commits else rollback_time)
                print(f"  Rollback #{i}: +{offset:.3f}s")


async def main():
    print("🔢 Database Commit Counter")
    print("=" * 50)
    
    # Create database session
    db = SessionLocal()
    counter = CommitCounter()
    
    # Monkey-patch commit and rollback
    counter.original_commit = db.commit
    counter.original_rollback = db.rollback
    db.commit = counter.track_commit
    db.rollback = counter.track_rollback
    
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
        
        # Run parsing operation
        parser = SQLiteElevationParserService(db)
        print("\nExecuting parse operation...\n")
        
        start_time = time.time()
        result = await parser.parse_elevation_data(elevation.id)
        elapsed = time.time() - start_time
        
        print(f"\nParse completed in {elapsed:.2f}s")
        print(f"Result: {'SUCCESS' if result['success'] else 'FAILED'}")
        
        # Generate report
        counter.report()
        
        # Evaluate results
        print("\n📋 Evaluation")
        print("=" * 50)
        
        success = True
        
        # Expected: 1 commit for success, or 1 rollback + 1 commit for error
        if result['success']:
            expected_commits = 1  # Single transaction
            if len(counter.commits) == expected_commits:
                print(f"✅ Commit count correct: {len(counter.commits)} (expected {expected_commits})")
            else:
                print(f"❌ FAILED: Too many commits!")
                print(f"   Expected: {expected_commits}")
                print(f"   Actual: {len(counter.commits)}")
                print(f"   This indicates single-transaction optimization is not working correctly.")
                success = False
            
            if len(counter.rollbacks) > 0:
                print(f"⚠️  Warning: Unexpected rollback(s) during successful parse")
        else:
            # Error case: expect 1 rollback + 1 commit for error state
            if len(counter.rollbacks) >= 1:
                print(f"✅ Rollback executed on error")
            else:
                print(f"❌ FAILED: No rollback on error!")
                success = False
        
        if success:
            print("\n✅ PASSED: Single-transaction optimization verified")
            return 0
        else:
            print("\n❌ FAILED: Single-transaction optimization not working")
            return 1
            
    except Exception as e:
        print(f"\n❌ ERROR: {str(e)}")
        import traceback
        traceback.print_exc()
        return 1
    finally:
        # Restore original methods
        if counter.original_commit:
            db.commit = counter.original_commit
        if counter.original_rollback:
            db.rollback = counter.original_rollback
        db.close()


if __name__ == "__main__":
    exit_code = asyncio.run(main())
    sys.exit(exit_code)

