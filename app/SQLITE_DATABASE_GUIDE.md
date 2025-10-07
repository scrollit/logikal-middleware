# SQLite Parts Database Exploration Guide

## Overview
The sample parts database files contain complete parts databases for window/door elevation projects from the Logikal API. These databases represent real projects with different systems and configurations.

## Database Structure

### Original Sample (`sample_parts_database.db`)
- **File**: `app/sample_parts_database.db`
- **Size**: 716,800 bytes (~700KB)
- **Project**: DOS22410, Elevation P03
- **System**: Reynaers MasterLine 8
- **Elevation Value**: €889.84

### New Sample (`sample_parts_database_new.db`)
- **File**: `app/sample_parts_database_new.db`
- **Size**: 1,720,320 bytes (~1.7MB)
- **Project**: DOS22309, Elevation P11
- **System**: Reynaers ConceptPatio 130-LS (CP 130-LS)
- **Elevation Value**: €547.76
- **Dimensions**: 3.1m x 2.245m

Both databases contain:
- **Tables**: 71 tables
- **Total Records**: ~1,000+ records across all tables

## Key Tables for Exploration

### 1. Project Information
- **Projects**: Main project data (1 record)
- **Elevations**: Elevation specifications (1 record)
- **Phases**: Project phases (1 record)

### 2. Parts and Components
- **Articles**: Hardware and accessories (32 records)
- **Profiles**: Aluminum profiles (21 records)
- **Glass**: Glass specifications (2 records)
- **Insertions**: Window/door elements (4 records)

### 3. Manufacturing Data
- **LabourTimes**: Production times (27 records)
- **LabourCosts**: Labor cost calculations (21 records)
- **CalcDetailItems**: Cost breakdowns (140 records)
- **MountingLines**: Installation positioning (4 records)

### 4. Technical Specifications
- **UValue**: Thermal performance data (22 records)
- **Colors**: Color options (6 records)
- **ElevationCE**: CE marking information (20 records)

### 5. Supply Chain
- **Suppliers**: Supplier information (4 records)
- **Manufacturers**: Manufacturer details (3 records)

## Exploration Tools

### Using SQLite Command Line
```bash
# Connect to original database
sqlite3 app/sample_parts_database.db

# Connect to new database
sqlite3 app/sample_parts_database_new.db

# List all tables
.tables

# Show table schema
.schema Projects
.schema Elevations
.schema Articles

# Query examples
SELECT * FROM Projects;
SELECT * FROM Elevations;
SELECT ArticleCode, Description, Amount FROM Articles LIMIT 10;
SELECT * FROM Profiles WHERE Length > 1.0;
SELECT Name, U, U_Unit FROM UValue WHERE U > 0;
```

### Using Python
```python
import sqlite3

# Connect to original database
conn = sqlite3.connect('app/sample_parts_database.db')
cursor = conn.cursor()

# Connect to new database
conn = sqlite3.connect('app/sample_parts_database_new.db')
cursor = conn.cursor()

# Get table names
cursor.execute("SELECT name FROM sqlite_master WHERE type='table'")
tables = cursor.fetchall()

# Query specific data
cursor.execute("SELECT * FROM Articles WHERE Amount > 0")
articles = cursor.fetchall()

# Get table schema
cursor.execute("PRAGMA table_info(Articles)")
columns = cursor.fetchall()

conn.close()
```

## Sample Queries

### Get Project Overview
```sql
SELECT 
    p.Name as ProjectName,
    e.Name as ElevationName,
    e.SystemName,
    e.Width,
    e.Height
FROM Projects p
JOIN Elevations e ON p.ProjectID = 1;
```

### Get Parts List
```sql
SELECT 
    ArticleCode,
    Description,
    Amount,
    Color
FROM Articles 
WHERE Amount > 0
ORDER BY ArticleCode;
```

### Get Profile Information
```sql
SELECT 
    ArticleCode,
    Description,
    Length,
    Color,
    Price
FROM Profiles
ORDER BY Length DESC;
```

### Get Cost Breakdown
```sql
SELECT 
    cdi.CalcDetailItemID,
    cin.Name as ItemName,
    cdi.Value
FROM CalcDetailItems cdi
JOIN CalcItemNames cin ON cdi.CalcItemNameID = cin.CalcItemNameID
WHERE cdi.Value > 0
ORDER BY cdi.Value DESC;
```

### Get Thermal Performance
```sql
SELECT 
    Name,
    U,
    U_Unit,
    Area,
    Area_Unit
FROM UValue
WHERE U > 0
ORDER BY U;
```

## Data Insights

### Project Details
- **Project**: DOS22410
- **Elevation**: P03
- **System**: Reynaers MasterLine 8
- **Dimensions**: 2.29m x 1.403m
- **GUID**: {15782E4D-A69C-4CE5-9C17-D3060A039B2D}

### Key Components
- **32 Articles**: Hardware, screws, connectors
- **21 Profiles**: Aluminum profiles for frame construction
- **2 Glass Types**: Different glass specifications
- **4 Insertions**: Window/door elements (base, fixed, casement)

### Manufacturing Data
- **27 Labour Times**: Production operations and times
- **140 Cost Items**: Detailed cost breakdown
- **22 U-Values**: Thermal performance measurements

## File Location
The database files are located at:
```
app/sample_parts_database.db          # Original sample (716KB)
app/sample_parts_database_new.db      # New sample (1.7MB)
```

## Troubleshooting

### Database Locked Error
If you encounter a "database is locked" error:

1. **Check for active connections**: Make sure no other applications are using the database
2. **File permissions**: The database should have read permissions (644)
3. **WSL/Windows access**: If accessing from Windows via WSL, try copying the file to a Windows location first

### Alternative Access Methods

#### Copy to Windows (if using WSL)
```bash
# Copy to Windows desktop
cp app/sample_parts_database.db /mnt/c/Users/YourUsername/Desktop/sample_parts_database.db
```

#### Use SQLite Browser
Download SQLite Browser from https://sqlitebrowser.org/ and open the database file directly.

#### Command Line Access
```bash
# Navigate to the directory
cd /home/jasperhendrickx/clients/logikal-middleware-dev

# Open with SQLite command line
sqlite3 app/sample_parts_database.db
```

## Notes
- This is a read-only copy for exploration purposes
- The original database is stored in `app/parts_db/elevations/`
- All data represents a real project from the Logikal API
- The database structure follows the Logikal parts-list format
- If you encounter access issues, try copying the file to a different location
