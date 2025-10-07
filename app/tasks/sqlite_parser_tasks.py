import asyncio
import sqlite3
import time
import traceback
from typing import List, Dict
from datetime import datetime
from celery.exceptions import Retry
from celery import current_task
from sqlalchemy.orm import Session

from celery_app import celery_app
from core.database import get_db
from services.sqlite_parser_service import (
    SQLiteElevationParserService, 
    IdempotentParserService,
    ParsingStatus
)
from models.elevation import Elevation
import logging

logger = logging.getLogger(__name__)


@celery_app.task(bind=True, name="tasks.sqlite_parser_tasks.parse_elevation_sqlite")
def parse_elevation_sqlite_task(self, elevation_id: int, retry_count: int = 0) -> Dict:
    """Parse SQLite data for a single elevation with retry logic"""
    
    task_id = self.request.id
    logger.info(f"Starting SQLite parsing task {task_id} for elevation {elevation_id}")
    
    try:
        # Get database session
        db = next(get_db())
        
        # Update task status
        self.update_state(
            state="PROGRESS",
            meta={
                "current": 0,
                "total": 100,
                "status": f"Parsing elevation {elevation_id}",
                "elevation_id": elevation_id,
                "retry_count": retry_count
            }
        )
        
        # Initialize parser service
        parser_service = IdempotentParserService(db)
        
        # Parse elevation data
        result = asyncio.run(parser_service.parse_elevation_idempotent(elevation_id))
        
        if result["success"]:
            if result.get("skipped"):
                logger.info(f"Elevation {elevation_id} parsing skipped: {result.get('reason')}")
                return {
                    "success": True,
                    "elevation_id": elevation_id,
                    "task_id": task_id,
                    "skipped": True,
                    "reason": result.get("reason")
                }
            else:
                logger.info(f"Successfully parsed elevation {elevation_id}")
                return {
                    "success": True,
                    "elevation_id": elevation_id,
                    "task_id": task_id,
                    "parsed_at": result.get("parsed_at"),
                    "glass_count": result.get("glass_count", 0)
                }
        else:
            # Check if this is a retryable error
            if _is_retryable_error(result["error"]) and retry_count < 3:
                logger.warning(f"Retryable error for elevation {elevation_id}: {result['error']}")
                
                # Exponential backoff: 2^retry_count minutes
                countdown = 60 * (2 ** retry_count)
                
                raise self.retry(
                    args=[elevation_id, retry_count + 1],
                    countdown=countdown,
                    max_retries=3
                )
            else:
                logger.error(f"Failed to parse elevation {elevation_id}: {result['error']}")
                return {
                    "success": False,
                    "elevation_id": elevation_id,
                    "task_id": task_id,
                    "error": result["error"],
                    "retry_count": retry_count
                }
                
    except Exception as exc:
        logger.error(f"Task {task_id} failed with exception: {str(exc)}")
        
        # Check if this is a retryable exception
        if isinstance(exc, Retry):
            raise exc  # Re-raise retry exceptions
            
        if _is_retryable_exception(exc) and retry_count < 3:
            countdown = 60 * (2 ** retry_count)
            raise self.retry(
                args=[elevation_id, retry_count + 1],
                countdown=countdown,
                exc=exc,
                max_retries=3
            )
        
        return {
            "success": False,
            "elevation_id": elevation_id,
            "task_id": task_id,
            "error": str(exc),
            "retry_count": retry_count
        }
    
    finally:
        if 'db' in locals():
            db.close()


@celery_app.task(bind=True, name="tasks.sqlite_parser_tasks.batch_parse_elevations")
def batch_parse_elevations_task(self, elevation_ids: List[int]) -> Dict:
    """Batch parse SQLite data for multiple elevations with 2-worker limit"""
    
    task_id = self.request.id
    logger.info(f"Starting batch parsing task {task_id} for {len(elevation_ids)} elevations")
    
    try:
        # Process with concurrency control
        MAX_CONCURRENT_WORKERS = 2
        semaphore = asyncio.Semaphore(MAX_CONCURRENT_WORKERS)
        
        async def parse_with_semaphore(elevation_id, index):
            """Parse elevation with semaphore protection"""
            async with semaphore:
                # Update progress
                progress = int((index / len(elevation_ids)) * 100)
                self.update_state(
                    state="PROGRESS",
                    meta={
                        "current": progress,
                        "total": 100,
                        "status": f"Parsing elevation {index+1}/{len(elevation_ids)}",
                        "elevation_id": elevation_id,
                        "completed": index,
                        "total_elevations": len(elevation_ids)
                    }
                )
                
                # Parse individual elevation
                try:
                    result = parse_elevation_sqlite_task.delay(elevation_id)
                    return {
                        "elevation_id": elevation_id,
                        "success": True,
                        "task_id": result.id
                    }
                except Exception as e:
                    logger.error(f"Failed to start parsing for elevation {elevation_id}: {str(e)}")
                    return {
                        "elevation_id": elevation_id,
                        "success": False,
                        "error": str(e)
                    }
        
        # Create tasks for all elevations
        tasks = [
            parse_with_semaphore(eid, idx) 
            for idx, eid in enumerate(elevation_ids)
        ]
        
        # Process all elevations concurrently
        results = asyncio.run(asyncio.gather(*tasks, return_exceptions=True))
        
        # Aggregate results
        successful_parses = sum(1 for r in results if isinstance(r, dict) and r.get("success"))
        failed_parses = len(elevation_ids) - successful_parses
        
        return {
            "success": True,
            "task_id": task_id,
            "total_elevations": len(elevation_ids),
            "successful_parses": successful_parses,
            "failed_parses": failed_parses,
            "results": results,
            "completed_at": datetime.utcnow().isoformat()
        }
        
    except Exception as exc:
        logger.error(f"Batch parsing task {task_id} failed: {str(exc)}")
        return {
            "success": False,
            "task_id": task_id,
            "error": str(exc),
            "failed_at": datetime.utcnow().isoformat()
        }


@celery_app.task(bind=True, name="tasks.sqlite_parser_tasks.trigger_parsing_for_new_files")
def trigger_parsing_for_new_files_task(self) -> Dict:
    """Scan for new SQLite files and trigger parsing"""
    
    task_id = self.request.id
    logger.info(f"Starting file scan task {task_id}")
    
    try:
        db = next(get_db())
        
        # Find elevations with SQLite files that haven't been parsed
        elevations_to_parse = db.query(Elevation).filter(
            Elevation.has_parts_data == True,
            Elevation.parts_db_path.isnot(None),
            Elevation.parse_status.in_(['pending', 'failed'])
        ).all()
        
        triggered_count = 0
        for elevation in elevations_to_parse:
            # Check if file exists and is recent
            import os
            if os.path.exists(elevation.parts_db_path):
                # Trigger parsing
                parse_elevation_sqlite_task.delay(elevation.id)
                triggered_count += 1
        
        return {
            "success": True,
            "task_id": task_id,
            "elevations_found": len(elevations_to_parse),
            "parsing_triggered": triggered_count,
            "scanned_at": datetime.utcnow().isoformat()
        }
        
    except Exception as exc:
        logger.error(f"File scan task {task_id} failed: {str(exc)}")
        return {
            "success": False,
            "task_id": task_id,
            "error": str(exc)
        }
    
    finally:
        if 'db' in locals():
            db.close()


def _is_retryable_error(error_message: str) -> bool:
    """Determine if an error is retryable"""
    retryable_errors = [
        "database is locked",
        "temporary failure",
        "connection timeout",
        "file is busy",
        "sqlite error",
        "connection error"
    ]
    return any(retryable in error_message.lower() for retryable in retryable_errors)


def _is_retryable_exception(exc: Exception) -> bool:
    """Determine if an exception is retryable"""
    retryable_exceptions = [
        sqlite3.OperationalError,
        sqlite3.DatabaseError,
        ConnectionError,
        TimeoutError,
        OSError
    ]
    return isinstance(exc, tuple(retryable_exceptions))


class SQLiteParserWorkerManager:
    """
    Manages SQLite parsing workers with 2-worker limit
    """
    
    MAX_CONCURRENT_WORKERS = 2
    
    @staticmethod
    async def process_elevations_with_limit(elevation_ids: List[int]):
        """Process elevations with semaphore-based concurrency control"""
        semaphore = asyncio.Semaphore(SQLiteParserWorkerManager.MAX_CONCURRENT_WORKERS)
        
        async def parse_with_semaphore(elevation_id):
            async with semaphore:
                return await _parse_single_elevation(elevation_id)
        
        tasks = [parse_with_semaphore(eid) for eid in elevation_ids]
        return await asyncio.gather(*tasks, return_exceptions=True)


async def _parse_single_elevation(elevation_id: int) -> Dict:
    """Parse a single elevation (helper function)"""
    try:
        db = next(get_db())
        parser_service = IdempotentParserService(db)
        result = await parser_service.parse_elevation_idempotent(elevation_id)
        return result
    except Exception as e:
        logger.error(f"Error parsing elevation {elevation_id}: {str(e)}")
        return {"success": False, "error": str(e)}
    finally:
        if 'db' in locals():
            db.close()
