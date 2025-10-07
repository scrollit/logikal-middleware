# External Service Guide - Session Isolation Issue

## Quick Start

This package contains everything needed to understand and debug a critical session isolation issue in a FastAPI + SQLAlchemy application.

## Problem Summary

**Issue**: Projects are processed and committed successfully, but disappear from the database after the operation completes.

**Root Cause**: FastAPI's `get_db` dependency closes the session in a `finally` block, causing SQLAlchemy to rollback committed changes.

## Files to Review

### 1. Core Issue Files
- `database.py` - Database configuration and problematic `get_db()` function
- `sync_router.py` - API endpoint using `Depends(get_db)`
- `sync_service.py` - Service layer with commit calls
- `project_sync_service.py` - Project processing with commits

### 2. Evidence Files
- `sync_logs.txt` - Complete logs showing successful commits but no persistence
- `database_schema.sql` - Database schema for reference
- `ISSUE_ANALYSIS.md` - Detailed technical analysis

### 3. Test Files
- `test_script.py` - Standalone script to reproduce the issue
- `run_tests.sh` - Automated test runner
- `requirements.txt` - Dependencies

## How to Reproduce

### Option 1: Use the Test Script
```bash
cd debug_session_isolation
python3 test_script.py
```

### Option 2: Use the Automated Runner
```bash
cd debug_session_isolation
./run_tests.sh
```

### Option 3: Manual Testing
1. Start the application: `docker-compose up -d`
2. Trigger sync: `curl -X POST http://localhost:8001/api/v1/sync/projects`
3. Check database: `SELECT COUNT(*) FROM projects;`
4. Result: 0 rows despite successful processing

## Key Questions

1. **Why does `session.close()` rollback committed changes?**
2. **How should FastAPI dependency injection work with SQLAlchemy?**
3. **What's the proper pattern for long-running transactions?**
4. **Is there a way to ensure commits persist after session closure?**

## Expected Behavior vs Actual

### Expected
- Projects are processed ✅
- Projects are committed ✅
- Projects persist in database ❌

### Actual
- Projects are processed ✅
- Projects are committed ✅
- Projects disappear after session closure ❌

## Code Pattern Causing Issue

```python
# database.py - PROBLEMATIC
def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()  # This causes rollback

# sync_router.py - USAGE
@router.post("/projects")
async def sync_projects_ui(db: Session = Depends(get_db)):
    # Session is closed here, causing rollback
```

## Potential Solutions to Investigate

1. **Session Management**: Use different session lifecycle
2. **Transaction Control**: Explicit transaction boundaries
3. **Connection Pooling**: Direct connection management
4. **Context Managers**: Proper session cleanup

## Environment

- **Framework**: FastAPI
- **ORM**: SQLAlchemy 1.4+
- **Database**: PostgreSQL 13+
- **Session Factory**: `sessionmaker(autocommit=False, autoflush=False)`
- **Container**: Docker

## Success Criteria

A solution should ensure that:
1. Projects are processed successfully ✅
2. Projects are committed successfully ✅
3. Projects persist in database after session closure ✅
4. No data loss occurs ✅

## Contact Information

This is a critical production issue affecting core functionality. Any insights or solutions would be greatly appreciated.
