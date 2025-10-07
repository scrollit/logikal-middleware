import sqlite3
import os
import traceback
from typing import Dict, List, Optional
from datetime import datetime
from sqlalchemy.orm import Session
from sqlalchemy.exc import SQLAlchemyError

from models.elevation import Elevation
from models.elevation_glass import ElevationGlass
from models.parsing_error_log import ParsingErrorLog
from services.sqlite_validation_service import SQLiteValidationService, ValidationResult
import logging

logger = logging.getLogger(__name__)


class ParsingStatus:
    """Parsing status enumeration"""
    PENDING = "pending"
    IN_PROGRESS = "in_progress"
    SUCCESS = "success"
    FAILED = "failed"
    PARTIAL = "partial"
    VALIDATION_FAILED = "validation_failed"


class ParsingError(Exception):
    """Custom exception for parsing errors"""
    pass


class SQLiteElevationParserService:
    """Enhanced parser with comprehensive error handling"""
    
    def __init__(self, db: Session):
        self.db = db
        self.logger = logger
        self.validation_service = SQLiteValidationService()
    
    async def parse_elevation_data(self, elevation_id: int) -> Dict:
        """Parse elevation data with full error handling and status tracking"""
        
        elevation = self.db.query(Elevation).filter(Elevation.id == elevation_id).first()
        if not elevation:
            return {"success": False, "error": "Elevation not found"}
        
        try:
            # Update status to in_progress
            elevation.parse_status = ParsingStatus.IN_PROGRESS
            elevation.data_parsed_at = datetime.utcnow()
            self.db.commit()
            
            # Validate file first
            if not elevation.parts_db_path or not os.path.exists(elevation.parts_db_path):
                raise ParsingError("SQLite file not found", "file_not_found")
            
            validation_result = await self.validation_service.validate_file(elevation.parts_db_path)
            
            if not validation_result.valid:
                elevation.parse_status = ParsingStatus.VALIDATION_FAILED
                elevation.parse_error = validation_result.message
                self._log_parsing_error(
                    elevation_id, 
                    "validation_failed", 
                    validation_result.message,
                    validation_result.details
                )
                self.db.commit()
                return {"success": False, "error": validation_result.message}
            
            # Extract data with error handling
            elevation_data = await self._extract_elevation_data_safe(elevation.parts_db_path)
            glass_data = await self._extract_glass_data_safe(elevation.parts_db_path)
            
            # Update database with atomic transaction
            await self._update_elevation_model_atomic(elevation_id, elevation_data)
            await self._create_glass_records_atomic(elevation_id, glass_data)
            
            # Update parsing status
            elevation.parse_status = ParsingStatus.SUCCESS
            elevation.parse_error = None
            elevation.data_parsed_at = datetime.utcnow()
            
            # Update file hash for future deduplication
            file_hash = await self.validation_service.calculate_file_hash(elevation.parts_db_path)
            elevation.parts_file_hash = file_hash
            
            # Commit all changes
            self.db.commit()
            
            return {
                "success": True, 
                "elevation_data": elevation_data,
                "glass_count": len(glass_data),
                "parsed_at": elevation.data_parsed_at.isoformat()
            }
            
        except Exception as e:
            # Handle parsing errors
            error_msg = str(e)
            elevation.parse_status = ParsingStatus.FAILED
            elevation.parse_error = error_msg
            
            self._log_parsing_error(
                elevation_id, 
                "parsing_failed", 
                error_msg, 
                {"traceback": traceback.format_exc()}
            )
            self.db.commit()
            
            return {"success": False, "error": error_msg}
    
    async def _extract_elevation_data_safe(self, sqlite_path: str) -> Dict:
        """Extract data from Elevations table with error handling"""
        
        try:
            conn = await self.validation_service._open_sqlite_readonly(sqlite_path)
            
            try:
                cursor = conn.cursor()
                
                # Extract from Elevations table with parameterized query
                # CRITICAL FIX: Use elevation name to find the correct record instead of LIMIT 1
                cursor.execute("""
                    SELECT 
                        AutoDescription,
                        AutoDescriptionShort,
                        Width_Output,
                        Width_Unit,
                        Height_Output,
                        Height_Unit,
                        Weight_Output,
                        Weight_Unit,
                        Area_Output,
                        Area_Unit,
                        SystemCode,
                        SystemName,
                        SystemLongName,
                        ColorBase_Long
                    FROM Elevations 
                    WHERE Name = ? OR Name LIKE ?
                    LIMIT 1
                """, (elevation.name, f"%{elevation.name}%"))
                
                result = cursor.fetchone()
                
                if not result:
                    # Fallback: If no exact match, try to get any record as fallback
                    logger.warning(f"No exact match found for elevation '{elevation.name}', trying fallback")
                    cursor.execute("""
                        SELECT 
                            AutoDescription,
                            AutoDescriptionShort,
                            Width_Output,
                            Width_Unit,
                            Height_Output,
                            Height_Unit,
                            Weight_Output,
                            Weight_Unit,
                            Area_Output,
                            Area_Unit,
                            SystemCode,
                            SystemName,
                            SystemLongName,
                            ColorBase_Long
                        FROM Elevations 
                        LIMIT 1
                    """)
                    result = cursor.fetchone()
                    
                    if not result:
                        raise ParsingError("No data found in Elevations table")
                
                # Map result to dictionary
                elevation_data = {
                    "auto_description": result[0],
                    "auto_description_short": result[1],
                    "width_out": result[2],
                    "width_unit": result[3],
                    "height_out": result[4],
                    "height_unit": result[5],
                    "weight_out": result[6],
                    "weight_unit": result[7],
                    "area_output": result[8],
                    "area_unit": result[9],
                    "system_code": result[10],
                    "system_name": result[11],
                    "system_long_name": result[12],
                    "color_base_long": result[13]
                }
                
                return elevation_data
                
            finally:
                conn.close()
                
        except sqlite3.Error as e:
            raise ParsingError(f"SQLite error extracting elevation data: {str(e)}")
        except Exception as e:
            raise ParsingError(f"Error extracting elevation data: {str(e)}")
    
    async def _extract_glass_data_safe(self, sqlite_path: str) -> List[Dict]:
        """Extract data from Glass table with error handling"""
        
        try:
            conn = await self.validation_service._open_sqlite_readonly(sqlite_path)
            
            try:
                cursor = conn.cursor()
                
                # Extract from Glass table
                cursor.execute("""
                    SELECT 
                        GlassID,
                        Name
                    FROM Glass
                    WHERE GlassID IS NOT NULL
                """)
                
                results = cursor.fetchall()
                
                glass_data = []
                for result in results:
                    glass_item = {
                        "GlassID": result[0],
                        "Name": result[1]
                    }
                    glass_data.append(glass_item)
                
                return glass_data
                
            finally:
                conn.close()
                
        except sqlite3.Error as e:
            raise ParsingError(f"SQLite error extracting glass data: {str(e)}")
        except Exception as e:
            raise ParsingError(f"Error extracting glass data: {str(e)}")
    
    async def _update_elevation_model_atomic(self, elevation_id: int, data: Dict) -> bool:
        """Update elevation model with parsed data using atomic transaction"""
        
        try:
            elevation = self.db.query(Elevation).filter(Elevation.id == elevation_id).first()
            if not elevation:
                raise ParsingError(f"Elevation {elevation_id} not found")
            
            # Update elevation fields atomically
            for field, value in data.items():
                if hasattr(elevation, field):
                    setattr(elevation, field, value)
            
            # Update timestamp
            elevation.data_parsed_at = datetime.utcnow()
            elevation.parse_status = ParsingStatus.SUCCESS
            
            self.db.commit()
            return True
            
        except SQLAlchemyError as e:
            self.db.rollback()
            raise ParsingError(f"Database error updating elevation: {str(e)}")
        except Exception as e:
            self.db.rollback()
            raise ParsingError(f"Error updating elevation: {str(e)}")
    
    async def _create_glass_records_atomic(self, elevation_id: int, glass_data: List[Dict]) -> bool:
        """Create glass records with deduplication and atomicity"""
        
        try:
            # Clear existing glass records for this elevation
            self.db.query(ElevationGlass).filter(
                ElevationGlass.elevation_id == elevation_id
            ).delete()
            
            # Create new glass records
            for glass_item in glass_data:
                glass_record = ElevationGlass(
                    elevation_id=elevation_id,
                    glass_id=glass_item.get('GlassID'),
                    name=glass_item.get('Name')
                )
                self.db.add(glass_record)
            
            self.db.commit()
            return True
            
        except SQLAlchemyError as e:
            self.db.rollback()
            raise ParsingError(f"Database error creating glass records: {str(e)}")
        except Exception as e:
            self.db.rollback()
            raise ParsingError(f"Error creating glass records: {str(e)}")
    
    def _log_parsing_error(self, elevation_id: int, error_type: str, message: str, details: Dict = None):
        """Log parsing error with detailed information"""
        try:
            error_log = ParsingErrorLog(
                elevation_id=elevation_id,
                error_type=error_type,
                error_message=message,
                error_details=details or {}
            )
            self.db.add(error_log)
            self.db.commit()
        except Exception as e:
            self.logger.error(f"Failed to log parsing error: {str(e)}")


class ParsingDeduplicationService:
    """Handles deduplication of parsing requests"""
    
    def __init__(self, db: Session):
        self.db = db
        self.logger = logger
    
    async def should_parse_elevation(self, elevation_id: int, sqlite_path: str) -> bool:
        """Check if elevation should be parsed (deduplication logic)"""
        
        # 1. Check if already parsing in progress
        elevation = self.db.query(Elevation).filter(Elevation.id == elevation_id).first()
        if not elevation:
            return False
        
        if elevation.parse_status == ParsingStatus.IN_PROGRESS:
            self.logger.info(f"Elevation {elevation_id} already being parsed")
            return False
        
        # 2. Check file hash for changes
        validation_service = SQLiteValidationService()
        file_hash = await validation_service.calculate_file_hash(sqlite_path)
        
        if elevation.parts_file_hash == file_hash and elevation.parse_status == ParsingStatus.SUCCESS:
            self.logger.info(f"Elevation {elevation_id} already parsed with same file")
            return False
        
        return True


class IdempotentParserService:
    """Ensures parsing operations are idempotent"""
    
    def __init__(self, db: Session):
        self.db = db
        self.parser_service = SQLiteElevationParserService(db)
        self.dedup_service = ParsingDeduplicationService(db)
    
    async def parse_elevation_idempotent(self, elevation_id: int) -> Dict:
        """Parse elevation with idempotency guarantees"""
        
        elevation = self.db.query(Elevation).filter(Elevation.id == elevation_id).first()
        
        if not elevation or not elevation.parts_db_path:
            return {"success": False, "error": "Elevation or SQLite file not found"}
        
        # Check if should parse
        should_parse = await self.dedup_service.should_parse_elevation(elevation_id, elevation.parts_db_path)
        if not should_parse:
            return {
                "success": True, 
                "skipped": True, 
                "reason": "Already parsed or parsing in progress",
                "parse_status": elevation.parse_status
            }
        
        try:
            # Perform parsing
            result = await self.parser_service.parse_elevation_data(elevation_id)
            return result
            
        except Exception as e:
            self.logger.error(f"Idempotent parsing failed for elevation {elevation_id}: {str(e)}")
            return {"success": False, "error": str(e)}
