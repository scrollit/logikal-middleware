# Logikal Middleware API Architecture Documentation

## Overview

The Logikal Middleware provides a comprehensive API layer that serves three distinct client types:
- **Admin UI**: Management and monitoring interface
- **Odoo ERP**: Integration client for business operations
- **Logikal API**: External data source

## Architecture Diagram

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                        LOGIKAL MIDDLEWARE API                              │
│                          (FastAPI Application)                            │
└─────────────────────────────────────────────────────────────────────────────┘
                                    │
                    ┌───────────────┼───────────────┐
                    │               │               │
            ┌───────▼────────┐ ┌────▼────┐ ┌────────▼────────┐
            │   ADMIN UI     │ │  ODOO   │ │   LOGIKAL API   │
            │   (Frontend)   │ │ (Client)│ │   (External)    │
            └────────────────┘ └─────────┘ └─────────────────┘
```

## Data Flow Architecture

```
┌─────────────────┐    ┌─────────────────┐    ┌─────────────────┐
│   ADMIN UI      │    │   ODOO ERP      │    │  LOGIKAL API    │
│   (Dashboard)   │    │   (Client)      │    │   (External)    │
└─────────┬───────┘    └─────────┬───────┘    └─────────┬───────┘
          │                      │                      │
          │ Admin Operations     │ Data Queries         │ Data Source
          │ - Sync Management    │ - Project Data       │ - Raw Data
          │ - Configuration      │ - Phase Data         │ - Real-time
          │ - Monitoring         │ - Elevation Data     │   Updates
          │                      │                      │
          ▼                      ▼                      ▼
┌─────────────────────────────────────────────────────────────────┐
│                    LOGIKAL MIDDLEWARE                          │
│                                                                 │
│  ┌─────────────┐  ┌─────────────┐  ┌─────────────┐             │
│  │   Admin     │  │   Odoo      │  │   Sync      │             │
│  │   APIs      │  │   APIs      │  │   Engine    │             │
│  │             │  │             │  │             │             │
│  │ • Cached    │  │ • Projects  │  │ • Directories│            │
│  │   Data      │  │ • Phases    │  │ • Projects  │            │
│  │ • Sync      │  │ • Elevations│  │ • Phases    │            │
│  │   Control   │  │ • Search    │  │ • Elevations│            │
│  │ • Monitoring│  │ • Stats     │  │ • Smart     │            │
│  └─────────────┘  └─────────────┘  │   Logic     │            │
│                                    └─────────────┘             │
│                                                                 │
│  ┌─────────────────────────────────────────────────────────────┐│
│  │                POSTGRESQL DATABASE                         ││
│  │  ┌─────────┐ ┌─────────┐ ┌─────────┐ ┌─────────┐          ││
│  │  │Directories│ │Projects│ │ Phases  │ │Elevations│         ││
│  │  │   Table  │ │  Table  │ │  Table  │ │  Table  │         ││
│  │  └─────────┘ └─────────┘ └─────────┘ └─────────┘          ││
│  └─────────────────────────────────────────────────────────────┘│
└─────────────────────────────────────────────────────────────────┘
```

## API Endpoint Classification

### 🎛️ ADMIN UI ENDPOINTS
*For the Admin Dashboard Interface*

#### 📁 Directories Management
- `GET /api/v1/directories/cached` - View cached directories
- `POST /api/v1/directories/{id}/exclude` - Exclude directory from sync
- `POST /api/v1/directories/bulk-exclude` - Bulk exclude directories
- `GET /api/v1/directories/syncable` - Get syncable directories

#### 📂 Projects Management
- `GET /api/v1/projects/cached` - View cached projects
- `POST /api/v1/projects/{id}/exclude` - Exclude project from sync

#### 📋 Phases Management
- `GET /api/v1/phases/cached` - View cached phases
- `POST /api/v1/phases/{id}/exclude` - Exclude phase from sync

#### 📐 Elevations Management
- `GET /api/v1/elevations/cached` - View cached elevations
- `POST /api/v1/elevations/{id}/exclude` - Exclude elevation from sync

#### 🔄 Sync Operations
- `POST /api/v1/sync/directories` - Sync directories from Logikal
- `POST /api/v1/sync/projects` - Sync projects from Logikal
- `POST /api/v1/sync/phases` - Sync phases from Logikal
- `POST /api/v1/sync/elevations` - Sync elevations from Logikal
- `POST /api/v1/sync/full` - Full sync (all data types)
- `POST /api/v1/sync/incremental` - Incremental sync
- `GET /api/v1/sync/status` - Get sync status and logs

#### ⚙️ Advanced Sync Features
- `POST /api/v1/advanced-sync/object` - Sync specific object
- `POST /api/v1/advanced-sync/cascade` - Cascading sync
- `POST /api/v1/advanced-sync/selective` - Selective sync
- `GET /api/v1/advanced-sync/dependencies` - Get sync dependencies

#### 📊 Monitoring & Analytics
- `GET /api/v1/sync-metrics/performance` - Performance metrics
- `GET /api/v1/sync-metrics/data-quality` - Data quality metrics
- `GET /api/v1/sync-metrics/efficiency` - Sync efficiency metrics
- `GET /api/v1/alert-system/health` - System health status
- `GET /api/v1/alert-system/alerts` - Active alerts
- `POST /api/v1/alert-system/acknowledge` - Acknowledge alerts

#### 🎯 Admin Interface
- `GET /ui` - Admin dashboard UI (HTML)

### 🏢 ODOO ENDPOINTS
*For Odoo ERP Integration*

#### 📋 Project Data Access
- `GET /api/v1/odoo/projects` - Get all projects for Odoo
- `GET /api/v1/odoo/projects/{project_id}` - Get specific project details
- `GET /api/v1/odoo/projects/{project_id}/complete` - Complete project data

#### 📂 Phase Data Access
- `GET /api/v1/odoo/projects/{project_id}/phases` - Get phases for project

#### 📐 Elevation Data Access
- `GET /api/v1/odoo/projects/{project_id}/phases/{phase_id}/elevations` - Get elevations

#### 🔍 Search & Discovery
- `GET /api/v1/odoo/search` - Search projects/phases/elevations
- `GET /api/v1/odoo/stats` - Get system statistics

#### 🔐 Authentication
- `POST /api/v1/client-auth/register` - Register Odoo client
- `POST /api/v1/client-auth/login` - Odoo client authentication
- `GET /api/v1/client-auth/validate` - Validate client token

### 🔄 INTERNAL OPERATIONAL ENDPOINTS
*For System Operations*

#### 📊 Sync Status & Logs
- `GET /api/v1/sync-status` - Current sync status
- `GET /api/v1/sync-status/logs` - Sync operation logs

#### ⏰ Scheduler Management
- `GET /api/v1/scheduler/status` - Scheduler status
- `POST /api/v1/scheduler/start` - Start scheduled sync
- `POST /api/v1/scheduler/stop` - Stop scheduled sync
- `GET /api/v1/scheduler/jobs` - List scheduled jobs

## Authentication & Authorization

### Admin UI
- **Authentication**: No authentication required (internal admin interface)
- **Access Control**: Uses session-based or basic auth for admin operations
- **Purpose**: Management and monitoring of the middleware system

### Odoo Integration
- **Authentication**: JWT Token-based authentication
- **Access Control**: Client registration and validation required
- **Permissions**: Permission-based access control
- **Purpose**: Secure integration with Odoo ERP system

### Logikal API
- **Authentication**: Username/Password authentication
- **Session Management**: Automatic session handling
- **API Token Handling**: Secure token management for external API calls

## Key Differences Between UI and Odoo Endpoints

| Feature | Admin UI Endpoints | Odoo Endpoints |
|---------|-------------------|----------------|
| **Purpose** | Management & Control | Data Access |
| **Authentication** | Internal/Admin | JWT Client Auth |
| **Data Format** | Raw/Detailed | Odoo-Optimized |
| **Operations** | CRUD + Sync Control | Read-Only |
| **Response** | Full Objects + Metadata | Simplified Objects |
| **Usage** | Human Interface | System Integration |

## Data Models

### Directory Model
```python
{
    "id": "integer",
    "logikal_id": "string",
    "name": "string",
    "full_path": "string",
    "level": "integer",
    "parent_id": "integer",
    "exclude_from_sync": "boolean",
    "synced_at": "datetime",
    "sync_status": "string",
    "created_at": "datetime",
    "updated_at": "datetime"
}
```

### Project Model
```python
{
    "id": "integer",
    "logikal_id": "string",
    "name": "string",
    "description": "string",
    "directory_id": "integer",
    "status": "string",
    "last_sync_date": "datetime",
    "last_update_date": "datetime",
    "created_at": "datetime",
    "updated_at": "datetime"
}
```

### Phase Model
```python
{
    "id": "integer",
    "logikal_id": "string",
    "name": "string",
    "description": "string",
    "project_id": "integer",
    "status": "string",
    "last_sync_date": "datetime",
    "last_update_date": "datetime",
    "created_at": "datetime",
    "updated_at": "datetime"
}
```

### Elevation Model
```python
{
    "id": "integer",
    "logikal_id": "string",
    "name": "string",
    "description": "string",
    "project_id": "integer",
    "phase_id": "string",
    "thumbnail_url": "string",
    "width": "float",
    "height": "float",
    "depth": "float",
    "last_sync_date": "datetime",
    "last_update_date": "datetime",
    "created_at": "datetime",
    "updated_at": "datetime"
}
```

## Error Handling

### Standard Error Response Format
```json
{
    "detail": "Error message",
    "code": "ERROR_CODE",
    "timestamp": "2025-09-28T10:30:00Z"
}
```

### Common Error Codes
- `AUTHENTICATION_FAILED` - Invalid credentials
- `PERMISSION_DENIED` - Insufficient permissions
- `OBJECT_NOT_FOUND` - Requested resource not found
- `SYNC_IN_PROGRESS` - Sync operation already running
- `EXTERNAL_API_ERROR` - Error from Logikal API
- `VALIDATION_ERROR` - Invalid request data

## Rate Limiting

### Admin UI
- **Limit**: 1000 requests per minute
- **Burst**: 100 requests per second
- **Purpose**: Prevent admin interface abuse

### Odoo Integration
- **Limit**: 10000 requests per hour
- **Burst**: 100 requests per minute
- **Purpose**: Ensure fair usage for ERP integration

## Monitoring & Observability

### Metrics Exposed
- Request count and duration
- Sync operation success/failure rates
- Data quality metrics
- System health indicators
- Cache hit/miss ratios

### Logging
- Structured logging with JSON format
- Request/response logging
- Error tracking and alerting
- Performance monitoring

## Deployment Configuration

### Environment Variables
```bash
# Logikal API Configuration
LOGIKAL_API_BASE_URL=http://128.199.57.77/MbioeService.svc/api/v3/
LOGIKAL_AUTH_USERNAME=Jasper
LOGIKAL_AUTH_PASSWORD=OdooAPI

# Database Configuration
DATABASE_URL=postgresql://admin:admin@db:5432/logikal_middleware

# Security Configuration
SECRET_KEY=your-super-secret-key
JWT_SECRET_KEY=your-jwt-secret-key

# Rate Limiting
RATE_LIMIT_PER_MINUTE=1000
RATE_LIMIT_PER_HOUR=10000

# Monitoring
PROMETHEUS_ENABLED=true
LOG_LEVEL=DEBUG
```

### Docker Services
- **web**: Main FastAPI application
- **db**: PostgreSQL database
- **redis**: Caching and session storage
- **celery-worker**: Background sync tasks
- **celery-beat**: Scheduled sync operations
- **flower**: Celery monitoring

## Security Considerations

### Data Protection
- All sensitive data encrypted in transit (HTTPS)
- Database credentials secured
- API tokens properly managed
- Client authentication enforced

### Access Control
- Role-based access control for Odoo clients
- Admin interface access restrictions
- API endpoint permission validation
- Rate limiting to prevent abuse

## Performance Optimization

### Caching Strategy
- Database query result caching
- API response caching
- Session data caching in Redis
- Smart cache invalidation

### Sync Optimization
- Incremental sync capabilities
- Batch processing for large datasets
- Parallel sync operations
- Smart dependency resolution

## Maintenance & Operations

### Health Checks
- Database connectivity monitoring
- External API availability checks
- Sync operation status monitoring
- System resource usage tracking

### Backup & Recovery
- Database backup procedures
- Configuration backup
- Disaster recovery plans
- Data consistency validation

---

*Last Updated: September 28, 2025*
*Version: 1.0.0*
