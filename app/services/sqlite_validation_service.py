import sqlite3
import os
import hashlib
from typing import Dict, Optional
from dataclasses import dataclass
import logging

logger = logging.getLogger(__name__)


@dataclass
class ValidationResult:
    """Result of SQLite file validation"""
    valid: bool
    message: str = ""
    details: Dict = None
    
    def __post_init__(self):
        if self.details is None:
            self.details = {}


class SQLiteValidationService:
    """Comprehensive validation for SQLite files before parsing"""
    
    MAX_FILE_SIZE = 10 * 1024 * 1024  # 10MB limit
    REQUIRED_TABLES = ['Elevations', 'Glass']
    EXPECTED_SCHEMA_VERSION = "3.0"  # Based on Logikal format
    
    def __init__(self):
        self.logger = logger
    
    async def validate_file(self, sqlite_path: str) -> ValidationResult:
        """Multi-layer validation of SQLite file"""
        
        # 1. File system validation
        if not os.path.exists(sqlite_path):
            return ValidationResult(False, "File does not exist")
            
        file_size = os.path.getsize(sqlite_path)
        if file_size > self.MAX_FILE_SIZE:
            return ValidationResult(
                False, 
                f"File size exceeds {self.MAX_FILE_SIZE} bytes",
                {"file_size": file_size, "max_size": self.MAX_FILE_SIZE}
            )
        
        if file_size == 0:
            return ValidationResult(False, "File is empty")
        
        # 2. SQLite integrity check
        integrity_result = await self._check_sqlite_integrity(sqlite_path)
        if not integrity_result.valid:
            return integrity_result
        
        # 3. Schema validation
        schema_result = await self._validate_schema(sqlite_path)
        if not schema_result.valid:
            return schema_result
        
        # 4. Data validation
        data_result = await self._validate_required_data(sqlite_path)
        return data_result
    
    async def _check_sqlite_integrity(self, sqlite_path: str) -> ValidationResult:
        """Check SQLite file integrity before processing"""
        
        try:
            conn = await self._open_sqlite_readonly(sqlite_path)
            
            try:
                # Perform integrity check
                cursor = conn.cursor()
                cursor.execute("PRAGMA integrity_check")
                result = cursor.fetchone()
                
                if result[0] != "ok":
                    return ValidationResult(
                        False, 
                        f"SQLite integrity check failed: {result[0]}",
                        {"integrity_result": result[0]}
                    )
                
                return ValidationResult(True, "SQLite integrity check passed")
                
            finally:
                conn.close()
                
        except sqlite3.Error as e:
            return ValidationResult(
                False, 
                f"SQLite integrity check error: {str(e)}",
                {"error_type": "sqlite_error", "error_details": str(e)}
            )
        except Exception as e:
            return ValidationResult(
                False, 
                f"Unexpected error during integrity check: {str(e)}",
                {"error_type": "unexpected_error", "error_details": str(e)}
            )
    
    async def _validate_schema(self, sqlite_path: str) -> ValidationResult:
        """Validate that required tables and columns exist"""
        
        try:
            conn = await self._open_sqlite_readonly(sqlite_path)
            
            try:
                cursor = conn.cursor()
                
                # Check required tables exist
                cursor.execute("SELECT name FROM sqlite_master WHERE type='table'")
                tables = [row[0] for row in cursor.fetchall()]
                
                missing_tables = set(self.REQUIRED_TABLES) - set(tables)
                if missing_tables:
                    return ValidationResult(
                        False, 
                        f"Required table(s) not found: {list(missing_tables)}",
                        {
                            "missing_tables": list(missing_tables),
                            "available_tables": tables
                        }
                    )
                
                # Validate Elevations table schema
                elevation_validation = await self._validate_elevations_table(cursor)
                if not elevation_validation.valid:
                    return elevation_validation
                
                # Validate Glass table schema
                glass_validation = await self._validate_glass_table(cursor)
                if not glass_validation.valid:
                    return glass_validation
                
                return ValidationResult(True, "Schema validation passed")
                
            finally:
                conn.close()
                
        except sqlite3.Error as e:
            return ValidationResult(
                False, 
                f"Schema validation error: {str(e)}",
                {"error_type": "sqlite_error", "error_details": str(e)}
            )
        except Exception as e:
            return ValidationResult(
                False, 
                f"Unexpected error during schema validation: {str(e)}",
                {"error_type": "unexpected_error", "error_details": str(e)}
            )
    
    async def _validate_elevations_table(self, cursor) -> ValidationResult:
        """Validate Elevations table schema"""
        
        required_elevation_columns = [
            'AutoDescription', 'AutoDescriptionShort', 'Width_Output', 'Width_Unit',
            'Height_Output', 'Height_Unit', 'Weight_Output', 'Weight_Unit',
            'Area_Output', 'Area_Unit', 'SystemCode', 'SystemName',
            'SystemLongName', 'ColorBase_Long'
        ]
        
        try:
            cursor.execute("PRAGMA table_info(Elevations)")
            elevation_columns = [row[1] for row in cursor.fetchall()]
            
            missing_columns = set(required_elevation_columns) - set(elevation_columns)
            if missing_columns:
                return ValidationResult(
                    False, 
                    f"Missing columns in Elevations table: {list(missing_columns)}",
                    {
                        "missing_columns": list(missing_columns),
                        "available_columns": elevation_columns,
                        "table": "Elevations"
                    }
                )
            
            return ValidationResult(True, "Elevations table schema valid")
            
        except sqlite3.Error as e:
            return ValidationResult(
                False, 
                f"Error validating Elevations table: {str(e)}",
                {"error_type": "sqlite_error", "table": "Elevations"}
            )
    
    async def _validate_glass_table(self, cursor) -> ValidationResult:
        """Validate Glass table schema"""
        
        required_glass_columns = ['GlassID', 'Name']
        
        try:
            cursor.execute("PRAGMA table_info(Glass)")
            glass_columns = [row[1] for row in cursor.fetchall()]
            
            missing_columns = set(required_glass_columns) - set(glass_columns)
            if missing_columns:
                return ValidationResult(
                    False, 
                    f"Missing columns in Glass table: {list(missing_columns)}",
                    {
                        "missing_columns": list(missing_columns),
                        "available_columns": glass_columns,
                        "table": "Glass"
                    }
                )
            
            return ValidationResult(True, "Glass table schema valid")
            
        except sqlite3.Error as e:
            return ValidationResult(
                False, 
                f"Error validating Glass table: {str(e)}",
                {"error_type": "sqlite_error", "table": "Glass"}
            )
    
    async def _validate_required_data(self, sqlite_path: str) -> ValidationResult:
        """Validate that required data exists in tables"""
        
        try:
            conn = await self._open_sqlite_readonly(sqlite_path)
            
            try:
                cursor = conn.cursor()
                
                # Check if Elevations table has data
                cursor.execute("SELECT COUNT(*) FROM Elevations")
                elevation_count = cursor.fetchone()[0]
                
                if elevation_count == 0:
                    return ValidationResult(
                        False, 
                        "Elevations table is empty",
                        {"table": "Elevations", "record_count": 0}
                    )
                
                # Check if Glass table has data (optional, but good to know)
                cursor.execute("SELECT COUNT(*) FROM Glass")
                glass_count = cursor.fetchone()[0]
                
                return ValidationResult(
                    True, 
                    "Data validation passed",
                    {
                        "elevation_records": elevation_count,
                        "glass_records": glass_count
                    }
                )
                
            finally:
                conn.close()
                
        except sqlite3.Error as e:
            return ValidationResult(
                False, 
                f"Data validation error: {str(e)}",
                {"error_type": "sqlite_error", "error_details": str(e)}
            )
        except Exception as e:
            return ValidationResult(
                False, 
                f"Unexpected error during data validation: {str(e)}",
                {"error_type": "unexpected_error", "error_details": str(e)}
            )
    
    async def _open_sqlite_readonly(self, sqlite_path: str) -> sqlite3.Connection:
        """Open SQLite file in read-only mode for security"""
        
        # Security measures:
        # 1. Read-only mode prevents any modifications
        # 2. URI connection string with mode=ro
        # 3. No shell access or file operations
        # 4. Sandboxed connection
        
        try:
            conn = sqlite3.connect(
                f"file:{sqlite_path}?mode=ro", 
                uri=True,
                timeout=30.0  # Prevent hanging connections
            )
            
            # Disable potentially dangerous features
            conn.execute("PRAGMA foreign_keys = OFF")  # Prevent FK constraints
            
            # Don't disable journaling if WAL files exist - this can cause I/O errors
            # The read-only mode already prevents modifications
            
            return conn
            
        except sqlite3.Error as e:
            raise Exception(f"Failed to open SQLite file securely: {str(e)}")
    
    async def calculate_file_hash(self, file_path: str) -> str:
        """Calculate SHA256 hash of SQLite file for change detection"""
        
        try:
            hash_sha256 = hashlib.sha256()
            with open(file_path, "rb") as f:
                for chunk in iter(lambda: f.read(4096), b""):
                    hash_sha256.update(chunk)
            
            return hash_sha256.hexdigest()
            
        except Exception as e:
            self.logger.error(f"Error calculating file hash: {str(e)}")
            raise Exception(f"Failed to calculate file hash: {str(e)}")
