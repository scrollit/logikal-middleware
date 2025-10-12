from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from sqlalchemy import text
from core.database import get_db
import logging

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/v1/admin", tags=["admin"])

@router.post("/fix-phase-constraint")
async def fix_phase_constraint(db: Session = Depends(get_db)):
    """Fix the phase constraint to allow multiple null logikal_ids across projects"""
    
    try:
        logger.info("Starting phase constraint fix...")
        
        # Check current constraints
        result = db.execute(text("""
            SELECT constraint_name, constraint_type 
            FROM information_schema.table_constraints 
            WHERE table_name = 'phases' AND constraint_name = 'ix_phases_logikal_id'
        """))
        
        old_constraint_exists = result.fetchone() is not None
        logger.info(f"Old constraint 'ix_phases_logikal_id' exists: {old_constraint_exists}")
        
        result = db.execute(text("""
            SELECT constraint_name, constraint_type 
            FROM information_schema.table_constraints 
            WHERE table_name = 'phases' AND constraint_name = 'uq_phase_logikal_project'
        """))
        
        new_constraint_exists = result.fetchone() is not None
        logger.info(f"New constraint 'uq_phase_logikal_project' exists: {new_constraint_exists}")
        
        # Drop old constraint if it exists
        if old_constraint_exists:
            logger.info("Dropping old constraint 'ix_phases_logikal_id'...")
            db.execute(text("ALTER TABLE phases DROP CONSTRAINT IF EXISTS ix_phases_logikal_id"))
            logger.info("Old constraint dropped")
        
        # Add new constraint if it doesn't exist
        if not new_constraint_exists:
            logger.info("Adding new composite constraint 'uq_phase_logikal_project'...")
            db.execute(text("ALTER TABLE phases ADD CONSTRAINT uq_phase_logikal_project UNIQUE (logikal_id, project_id)"))
            logger.info("New constraint added")
        
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
            "old_constraint_removed": old_constraint_exists,
            "new_constraint_added": not new_constraint_exists,
            "null_guid_phases_count": null_guid_count
        }
        
    except Exception as e:
        db.rollback()
        logger.error(f"Error during constraint fix: {e}")
        raise HTTPException(status_code=500, detail=f"Constraint fix failed: {str(e)}")
