#!/usr/bin/env python3
"""
Script to fix the phase constraint issue in the middleware database.
This will drop the old unique constraint and ensure the composite constraint is in place.
"""

import os
import sys
import asyncio
from sqlalchemy import create_engine, text
from sqlalchemy.exc import SQLAlchemyError

# Database connection
DATABASE_URL = os.getenv("DATABASE_URL", "postgresql://postgres:password@localhost:5432/logikal_middleware")

async def fix_phase_constraint():
    """Fix the phase constraint to allow multiple null logikal_ids across projects"""
    
    print("🔧 Fixing phase constraint issue...")
    
    try:
        # Create database engine
        engine = create_engine(DATABASE_URL)
        
        with engine.connect() as conn:
            # Start transaction
            trans = conn.begin()
            
            try:
                print("1. Checking current constraints...")
                
                # Check if the old constraint exists
                result = conn.execute(text("""
                    SELECT constraint_name, constraint_type 
                    FROM information_schema.table_constraints 
                    WHERE table_name = 'phases' AND constraint_name = 'ix_phases_logikal_id'
                """))
                
                old_constraint_exists = result.fetchone() is not None
                print(f"   Old constraint 'ix_phases_logikal_id' exists: {old_constraint_exists}")
                
                # Check if the new constraint exists
                result = conn.execute(text("""
                    SELECT constraint_name, constraint_type 
                    FROM information_schema.table_constraints 
                    WHERE table_name = 'phases' AND constraint_name = 'uq_phase_logikal_project'
                """))
                
                new_constraint_exists = result.fetchone() is not None
                print(f"   New constraint 'uq_phase_logikal_project' exists: {new_constraint_exists}")
                
                # Drop old constraint if it exists
                if old_constraint_exists:
                    print("2. Dropping old constraint 'ix_phases_logikal_id'...")
                    conn.execute(text("ALTER TABLE phases DROP CONSTRAINT IF EXISTS ix_phases_logikal_id"))
                    print("   ✅ Old constraint dropped")
                else:
                    print("2. Old constraint doesn't exist, skipping drop")
                
                # Add new constraint if it doesn't exist
                if not new_constraint_exists:
                    print("3. Adding new composite constraint 'uq_phase_logikal_project'...")
                    conn.execute(text("ALTER TABLE phases ADD CONSTRAINT uq_phase_logikal_project UNIQUE (logikal_id, project_id)"))
                    print("   ✅ New constraint added")
                else:
                    print("3. New constraint already exists, skipping add")
                
                # Verify the fix
                print("4. Verifying constraint fix...")
                
                # Try to insert a test phase with null GUID to see if it works
                test_result = conn.execute(text("""
                    SELECT COUNT(*) as count 
                    FROM phases 
                    WHERE logikal_id = '00000000-0000-0000-0000-000000000000'
                """))
                
                null_guid_count = test_result.fetchone()[0]
                print(f"   Current phases with null GUID: {null_guid_count}")
                
                # Commit the transaction
                trans.commit()
                print("✅ Database constraint fix completed successfully!")
                
                return True
                
            except Exception as e:
                trans.rollback()
                print(f"❌ Error during constraint fix: {e}")
                return False
                
    except SQLAlchemyError as e:
        print(f"❌ Database connection error: {e}")
        return False

if __name__ == "__main__":
    success = asyncio.run(fix_phase_constraint())
    sys.exit(0 if success else 1)
