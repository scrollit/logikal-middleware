from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from sqlalchemy import text
from core.database import get_db
import logging

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/v1/admin", tags=["admin"])

@router.get("/check-phase-constraints")
async def check_phase_constraints(db: Session = Depends(get_db)):
    """Check all constraints and indexes on the phases table"""
    
    try:
        # Get all constraints
        result = db.execute(text("""
            SELECT constraint_name, constraint_type 
            FROM information_schema.table_constraints 
            WHERE table_name = 'phases'
            ORDER BY constraint_name
        """))
        
        constraints = [{"name": row[0], "type": row[1]} for row in result.fetchall()]
        
        # Get all indexes
        result = db.execute(text("""
            SELECT indexname, indexdef 
            FROM pg_indexes 
            WHERE tablename = 'phases'
            ORDER BY indexname
        """))
        
        indexes = [{"name": row[0], "definition": row[1]} for row in result.fetchall()]
        
        return {
            "success": True,
            "constraints": constraints,
            "indexes": indexes
        }
        
    except Exception as e:
        logger.error(f"Error checking constraints: {e}")
        raise HTTPException(status_code=500, detail=f"Check failed: {str(e)}")

@router.post("/fix-phase-constraint")
async def fix_phase_constraint(db: Session = Depends(get_db)):
    """Fix the phase constraint to allow multiple null logikal_ids across projects"""
    
    try:
        logger.info("Starting phase constraint fix...")
        
        # First, drop ALL unique constraints and indexes on logikal_id
        logger.info("Dropping all unique constraints/indexes on logikal_id...")
        
        # Drop index if it exists
        try:
            db.execute(text("DROP INDEX IF EXISTS ix_phases_logikal_id"))
            logger.info("Dropped index ix_phases_logikal_id")
        except Exception as e:
            logger.warning(f"Could not drop index: {e}")
        
        # Drop constraint if it exists (it might be a constraint, not just an index)
        try:
            db.execute(text("ALTER TABLE phases DROP CONSTRAINT IF EXISTS ix_phases_logikal_id"))
            logger.info("Dropped constraint ix_phases_logikal_id")
        except Exception as e:
            logger.warning(f"Could not drop constraint: {e}")
        
        # Check if composite constraint exists
        result = db.execute(text("""
            SELECT constraint_name 
            FROM information_schema.table_constraints 
            WHERE table_name = 'phases' AND constraint_name = 'uq_phase_logikal_project'
        """))
        
        new_constraint_exists = result.fetchone() is not None
        
        # Add new constraint if it doesn't exist
        if not new_constraint_exists:
            logger.info("Adding new composite constraint 'uq_phase_logikal_project'...")
            db.execute(text("ALTER TABLE phases ADD CONSTRAINT uq_phase_logikal_project UNIQUE (logikal_id, project_id)"))
            logger.info("New constraint added")
        else:
            logger.info("Composite constraint already exists")
        
        # Verify the fix
        result = db.execute(text("""
            SELECT COUNT(*) as count 
            FROM phases 
            WHERE logikal_id = '00000000-0000-0000-0000-000000000000'
        """))
        
        null_guid_count = result.fetchone()[0]
        logger.info(f"Current phases with null GUID: {null_guid_count}")
        
        db.commit()
        
        return {
            "success": True,
            "message": "Phase constraint fix completed successfully",
            "actions_taken": [
                "Dropped index ix_phases_logikal_id",
                "Dropped constraint ix_phases_logikal_id",
                "Added composite constraint uq_phase_logikal_project" if not new_constraint_exists else "Composite constraint already exists"
            ],
            "null_guid_phases_count": null_guid_count
        }
        
    except Exception as e:
        db.rollback()
        logger.error(f"Error during constraint fix: {e}")
        raise HTTPException(status_code=500, detail=f"Constraint fix failed: {str(e)}")
