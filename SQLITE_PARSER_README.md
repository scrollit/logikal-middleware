# SQLite Parser for Elevations

This document describes the SQLite Parser feature that enriches elevation data by extracting information from SQLite database files provided by Logikal.

## Overview

The SQLite Parser automatically extracts detailed elevation information from SQLite files that are downloaded during the parts list sync process. This enrichment provides additional metadata that enhances the elevation records with:

- **Auto-generated descriptions** (AutoDescription, AutoDescriptionShort)
- **Dimensional data** (Width_Out, Heighth_Out, Weight_Out, Area_Output with units)
- **System information** (Systemcode, SystemName, SystemLongName, ColorBase_Long)
- **Glass specifications** (multiple glass types per elevation)

## Architecture

### Components

1. **Database Models**
   - Enhanced `Elevation` model with new parsing fields
   - New `ElevationGlass` model for glass specifications
   - New `ParsingErrorLog` model for error tracking

2. **Services**
   - `SQLiteValidationService`: Validates SQLite files before parsing
   - `SQLiteElevationParserService`: Core parsing logic with error handling
   - `IdempotentParserService`: Ensures parsing operations are idempotent

3. **Celery Tasks**
   - `parse_elevation_sqlite_task`: Parse individual elevations
   - `batch_parse_elevations_task`: Batch parsing with 2-worker limit
   - `trigger_parsing_for_new_files_task`: Automatic file scanning

4. **API Endpoints**
   - `/elevations/{id}/enrichment` - Get enrichment status and data
   - `/elevations/{id}/enrichment/trigger` - Manually trigger parsing
   - `/elevations/enrichment/status` - Global enrichment statistics
   - `/elevations/{id}` - Enhanced elevation details with enrichment data

5. **Admin UI**
   - `/admin/parsing-status` - Web interface for monitoring parsing status
   - `/admin/` - Admin dashboard with links to various functions

## Features

### ✅ Security
- Read-only SQLite file access
- Comprehensive file validation (size, integrity, schema)
- Parameterized queries to prevent SQL injection
- Sandboxed parsing environment

### ✅ Error Handling
- Structured error logging with detailed information
- Retry logic with exponential backoff (max 3 retries)
- Parsing status tracking (pending, in_progress, success, failed, validation_failed)
- Atomic database transactions

### ✅ Concurrency Control
- 2-worker limit for parsing tasks
- Semaphore-based concurrency control
- Redis locks for race condition prevention

### ✅ Idempotency
- File hash-based change detection
- Deduplication of parsing requests
- Safe re-execution of parsing operations

### ✅ Monitoring & Observability
- Structured logging with context
- Prometheus metrics integration
- Sentry error tracking
- Admin UI for status monitoring

## Database Schema

### Enhanced Elevation Model

New fields added to the `elevations` table:

```sql
-- Enrichment data from SQLite
auto_description TEXT,
auto_description_short VARCHAR(255),
width_out FLOAT,
width_unit VARCHAR(50),
height_out FLOAT,
height_unit VARCHAR(50),
weight_out FLOAT,
weight_unit VARCHAR(50),
area_output FLOAT,
area_unit VARCHAR(50),
system_code VARCHAR(100),
system_name VARCHAR(255),
system_long_name VARCHAR(500),
color_base_long VARCHAR(255),

-- Parsing metadata
parts_file_hash VARCHAR(64),
parse_status VARCHAR(50) DEFAULT 'pending',
parse_error TEXT,
parse_retry_count INTEGER DEFAULT 0,
data_parsed_at TIMESTAMP
```

### New Tables

#### elevation_glass
```sql
CREATE TABLE elevation_glass (
    id SERIAL PRIMARY KEY,
    elevation_id INTEGER REFERENCES elevations(id),
    glass_id VARCHAR(100) NOT NULL,
    name VARCHAR(255),
    created_at TIMESTAMP DEFAULT NOW()
);
```

#### parsing_error_logs
```sql
CREATE TABLE parsing_error_logs (
    id SERIAL PRIMARY KEY,
    elevation_id INTEGER REFERENCES elevations(id),
    error_type VARCHAR(100) NOT NULL,
    error_message TEXT NOT NULL,
    error_details JSON,
    retry_count INTEGER DEFAULT 0,
    created_at TIMESTAMP DEFAULT NOW()
);
```

## Usage

### Automatic Triggering

Parsing is automatically triggered when:
1. Parts list data is synced from Logikal API
2. SQLite file is successfully saved
3. Elevation record is updated with parts data

### Manual Triggering

#### Via API
```bash
# Trigger parsing for a specific elevation
curl -X POST "http://localhost:8000/api/v1/elevations/{elevation_id}/enrichment/trigger"

# Get enrichment status
curl "http://localhost:8000/api/v1/elevations/{elevation_id}/enrichment"

# Get global enrichment status
curl "http://localhost:8000/api/v1/elevations/enrichment/status"
```

#### Via Admin UI
1. Navigate to `/admin/parsing-status`
2. View global statistics and individual elevation status
3. Click "Parse" button to manually trigger parsing
4. View enriched data and error logs

### Celery Worker Setup

To run the parsing workers:

```bash
# Start Celery worker for SQLite parsing queue
celery -A app.celery_app worker --loglevel=info --queues=sqlite_parser --concurrency=2

# Start Celery beat for scheduled tasks (optional)
celery -A app.celery_app beat --loglevel=info
```

## Configuration

### Environment Variables

No additional environment variables are required. The parser uses existing Redis and database configurations.

### Celery Configuration

The parser tasks are configured with:
- Queue: `sqlite_parser`
- Concurrency: 2 workers maximum
- Timeout: 30 minutes
- Retry: 3 attempts with exponential backoff

## API Response Examples

### Enrichment Status
```json
{
  "elevation_id": 123,
  "parse_status": "success",
  "data_parsed_at": "2025-01-02T12:00:00Z",
  "parse_error": null,
  "has_enriched_data": true,
  "enriched_fields": {
    "auto_description": "Sample Elevation Description",
    "auto_description_short": "Sample Desc",
    "system_code": "SYS001",
    "system_name": "Standard System",
    "system_long_name": "Standard Glass System with Frame",
    "color_base_long": "White RAL 9016",
    "dimensions": {
      "width_out": 1200.5,
      "width_unit": "mm",
      "height_out": 800.0,
      "height_unit": "mm",
      "area_output": 0.96,
      "area_unit": "m²",
      "weight_out": 150.2,
      "weight_unit": "kg"
    }
  },
  "glass_specifications": [
    {
      "glass_id": "GLASS001",
      "name": "Clear Glass 6mm"
    },
    {
      "glass_id": "GLASS002", 
      "name": "Tempered Glass 8mm"
    }
  ]
}
```

### Global Status
```json
{
  "total_elevations": 150,
  "elevations_with_parts": 120,
  "parse_status_summary": {
    "success": 95,
    "pending": 15,
    "failed": 8,
    "in_progress": 2
  },
  "enrichment_rate": 79.17
}
```

## Error Handling

### Parsing Status Values

- `pending`: Not yet parsed
- `in_progress`: Currently being parsed
- `success`: Successfully parsed and enriched
- `failed`: Parsing failed (with error details)
- `validation_failed`: SQLite file validation failed
- `partial`: Partial parsing success (future enhancement)

### Error Types

- **validation**: File format or schema validation errors
- **parsing**: Data extraction errors
- **database**: Database operation errors
- **security**: Security validation failures

### Retry Logic

Retryable errors include:
- Database locked
- Temporary failures
- Connection timeouts
- File busy errors

Non-retryable errors include:
- Invalid file format
- Missing required tables/columns
- Security violations

## Monitoring

### Logs

Structured logging includes:
- Elevation ID and name
- File path and size
- Parsing duration
- Error details and stack traces

### Metrics

Prometheus metrics track:
- Parsing success/failure rates
- Processing time per elevation
- Queue length and worker utilization
- Error rates by type

### Health Checks

Monitor parsing health via:
- `/api/v1/health` - Overall system health
- `/api/v1/elevations/enrichment/status` - Parsing statistics
- Celery Flower UI - Task monitoring

## Performance

### Expected Performance

- **File size limit**: 10MB per SQLite file
- **Processing time**: 1-5 seconds per elevation (depending on file size)
- **Concurrency**: 2 workers maximum
- **Throughput**: ~100-200 elevations per hour

### Scalability Considerations

- Worker concurrency can be increased if needed
- Redis queue can handle high volumes
- Database indexing on parse_status for fast queries
- File cleanup policies for old SQLite files

## Troubleshooting

### Common Issues

1. **Parsing fails with "File not found"**
   - Check if parts list sync completed successfully
   - Verify SQLite file exists in `/app/parts_db/elevations/`

2. **Validation fails with "Missing columns"**
   - Logikal SQLite format may have changed
   - Check required table schema in validation service

3. **Workers not processing tasks**
   - Verify Celery workers are running
   - Check Redis connection
   - Monitor queue status in Flower UI

### Debug Mode

Enable debug logging:
```python
import logging
logging.getLogger('app.services.sqlite_parser_service').setLevel(logging.DEBUG)
```

### Manual File Validation

Test SQLite file manually:
```python
from services.sqlite_validation_service import SQLiteValidationService
validator = SQLiteValidationService()
result = await validator.validate_file('/path/to/file.db')
print(result)
```

## Future Enhancements

- **Batch processing**: Process multiple files in parallel
- **Incremental parsing**: Only parse changed files
- **Data validation**: Validate extracted data against business rules
- **Export functionality**: Export enriched data to external systems
- **Advanced UI**: Real-time parsing status updates with WebSockets

## Support

For issues or questions:
1. Check the error logs in `/app/logs/`
2. Monitor parsing status via admin UI
3. Review Celery task status in Flower UI
4. Check database parsing_error_logs table for detailed error information
