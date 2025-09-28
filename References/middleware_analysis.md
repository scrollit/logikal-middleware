# Logikal Middleware Analysis & Implementation Plan

## Executive Summary

This document provides a comprehensive analysis for building a middleware solution that acts as a proxy between Odoo and the Logikal API. The middleware will handle authentication, data transformation, caching, and provide a simplified REST API for Odoo consumption.

## Current State Analysis

### Existing Odoo Integration
- **Module**: `logikal_api` (v18.0.1.9.1)
- **Direct API Integration**: Odoo connects directly to Logikal MBIOE API
- **Authentication**: Username/password with session token management
- **Key Services**: 
  - `MBIOEApiClient`: Core API communication
  - `MBIOEService`: Business logic wrapper
  - Various sync services for directories, projects, phases, elevations

### Logikal API Structure (from swagger.json)
- **Base URL**: `/api/v3`
- **Authentication**: POST `/auth` with LoginData
- **Key Endpoints**:
  - `/directories` - Get directory structure
  - `/projects/select` - Select project by identifier
  - `/phases` - Get project phases
  - `/elevations` - Get elevation data
  - Various other endpoints for detailed data

## Architecture Design

### High-Level Architecture
```
┌─────────────┐    HTTPS/REST    ┌─────────────────┐    HTTPS/REST    ┌─────────────┐
│    Odoo     │ ◄──────────────► │   Middleware    │ ◄──────────────► │   Logikal   │
│             │   Simplified     │   (FastAPI)     │   Complex API   │   MBIOE API │
│             │   JSON API       │                 │                 │             │
└─────────────┘                  └─────────────────┘                 └─────────────┘
                                        │
                                        ▼
                                 ┌─────────────┐
                                 │ PostgreSQL  │
                                 │   Database  │
                                 └─────────────┘
                                        │
                                        ▼
                                 ┌─────────────┐
                                 │    Redis    │
                                 │   Cache     │
                                 └─────────────┘
```

### Technology Stack
- **Framework**: FastAPI (Python 3.11+)
- **Database**: PostgreSQL 15
- **Cache**: Redis 7
- **Container**: Docker with docker-compose
- **ORM**: SQLAlchemy with Alembic migrations

## Implementation Plan

### Phase 1: Minimal Viable Product (MVP)

#### 1.1 Core Infrastructure
**Files to Create/Modify:**
- `app/main.py` - FastAPI application entry point
- `app/models/` - SQLAlchemy models
- `app/services/` - Business logic services
- `app/routers/` - API route handlers
- `app/core/` - Configuration and utilities

#### 1.2 Authentication Service
**Purpose**: Handle Logikal authentication and session management

**Implementation:**
```python
# app/services/auth_service.py
class AuthService:
    def __init__(self, base_url: str, username: str, password: str):
        self.base_url = base_url
        self.username = username
        self.password = password
        self.session_token = None
    
    async def authenticate(self) -> str:
        """Authenticate with Logikal API and return session token"""
        # Implementation based on existing MBIOEApiClient.authenticate()
    
    async def test_connection(self) -> bool:
        """Test connection to Logikal API"""
        # Implementation based on existing test_connection logic
```

**API Endpoints:**
- `POST /auth/login` - Authenticate with Logikal
- `GET /auth/test` - Test connection
- `POST /auth/logout` - Terminate session

#### 1.3 Directory Service
**Purpose**: Retrieve and cache directory structure from Logikal

**Implementation:**
```python
# app/services/directory_service.py
class DirectoryService:
    async def get_directories(self) -> List[Directory]:
        """Get directories from Logikal API"""
        # Implementation based on existing get_directories()
    
    async def cache_directories(self, directories: List[Directory]):
        """Cache directories in PostgreSQL"""
        # Store in database for fast access
```

**API Endpoints:**
- `GET /directories` - Get all directories
- `GET /directories/{directory_id}` - Get specific directory

#### 1.4 Database Models
**Purpose**: Define data structures for caching Logikal data

**Models to Create:**
```python
# app/models/directory.py
class Directory(Base):
    __tablename__ = "directories"
    
    id = Column(Integer, primary_key=True)
    logikal_id = Column(String, unique=True, nullable=False)
    name = Column(String, nullable=False)
    parent_id = Column(Integer, ForeignKey("directories.id"))
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
```

#### 1.5 Configuration Management
**Purpose**: Manage environment variables and settings

**Implementation:**
```python
# app/core/config.py
class Settings:
    # Logikal API Configuration
    LOGIKAL_BASE_URL: str
    AUTH_USERNAME: str
    AUTH_PASSWORD: str
    
    # Database Configuration
    DATABASE_URL: str
    
    # Redis Configuration
    REDIS_URL: str
```

### Phase 2: Enhanced Features

#### 2.1 Project and Phase Management
- Project selection and caching
- Phase synchronization
- Background job processing

#### 2.2 Elevation and Thumbnail Handling
- Elevation data retrieval
- Thumbnail download and serving
- Image caching and optimization

#### 2.3 Parts List Processing
- Base64 SQLite parts list decoding
- Structured data extraction
- PostgreSQL storage and querying

## API Design

### Authentication Endpoints
```http
POST /auth/login
Content-Type: application/json

{
  "base_url": "https://logikal.api",
  "username": "your_username",
  "password": "your_password"
}

Response:
{
  "success": true,
  "token": "session_token_here",
  "expires_at": "2024-01-01T12:00:00Z"
}
```

### Directory Endpoints
```http
GET /directories

Response:
{
  "success": true,
  "data": [
    {
      "id": "dir_123",
      "name": "Project Folder",
      "parent_id": null,
      "children": [...]
    }
  ]
}
```

### Connection Test Endpoint
```http
GET /auth/test

Response:
{
  "success": true,
  "message": "Connection successful",
  "timestamp": "2024-01-01T12:00:00Z"
}
```

## Database Schema

### Core Tables
```sql
-- Directories table
CREATE TABLE directories (
    id SERIAL PRIMARY KEY,
    logikal_id VARCHAR(255) UNIQUE NOT NULL,
    name VARCHAR(255) NOT NULL,
    parent_id INTEGER REFERENCES directories(id),
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Session management
CREATE TABLE sessions (
    id SERIAL PRIMARY KEY,
    token VARCHAR(255) UNIQUE NOT NULL,
    username VARCHAR(255) NOT NULL,
    base_url VARCHAR(255) NOT NULL,
    expires_at TIMESTAMP NOT NULL,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- API call logs
CREATE TABLE api_logs (
    id SERIAL PRIMARY KEY,
    endpoint VARCHAR(255) NOT NULL,
    method VARCHAR(10) NOT NULL,
    status_code INTEGER,
    response_time_ms INTEGER,
    success BOOLEAN NOT NULL,
    error_message TEXT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);
```

## Implementation Steps

### Step 1: Project Structure Setup
1. Create directory structure in `app/`
2. Set up SQLAlchemy models
3. Configure Alembic for migrations
4. Set up FastAPI application structure

**Testing Scenarios:**
- **Unit Tests**: Test model creation and validation
- **Integration Tests**: Test database connection and migrations
- **Structure Tests**: Verify all required directories and files exist
- **Import Tests**: Ensure all modules can be imported without errors

```python
# Example test structure
def test_project_structure():
    """Test that all required directories and files exist"""
    assert os.path.exists("app/models")
    assert os.path.exists("app/services")
    assert os.path.exists("app/routers")
    assert os.path.exists("app/core")

def test_database_models():
    """Test SQLAlchemy model creation"""
    from app.models.directory import Directory
    directory = Directory(name="Test", logikal_id="test_123")
    assert directory.name == "Test"
    assert directory.logikal_id == "test_123"

def test_alembic_migrations():
    """Test database migration functionality"""
    # Test migration creation
    # Test migration execution
    # Test rollback functionality
```

### Step 2: Core Services Implementation
1. Implement `AuthService` based on existing `MBIOEApiClient`
2. Implement `DirectoryService` for directory management
3. Add database models and migrations
4. Create API routers

**Testing Scenarios:**
- **Service Unit Tests**: Test individual service methods
- **Mock API Tests**: Test services with mocked Logikal API responses
- **Database Integration Tests**: Test data persistence and retrieval
- **Error Handling Tests**: Test service error scenarios

```python
# Example service tests
def test_auth_service_authentication():
    """Test authentication service with valid credentials"""
    auth_service = AuthService("https://test.api", "user", "pass")
    with patch('requests.post') as mock_post:
        mock_post.return_value.json.return_value = {
            "data": {"token": "test_token"}
        }
        token = auth_service.authenticate()
        assert token == "test_token"

def test_directory_service_get_directories():
    """Test directory service retrieval"""
    directory_service = DirectoryService()
    with patch('requests.get') as mock_get:
        mock_get.return_value.json.return_value = {
            "data": [{"id": "dir1", "name": "Test Directory"}]
        }
        directories = directory_service.get_directories()
        assert len(directories) == 1
        assert directories[0]["name"] == "Test Directory"

def test_database_caching():
    """Test directory data caching in PostgreSQL"""
    # Test data insertion
    # Test data retrieval
    # Test data update
    # Test data deletion
```

### Step 3: Testing and Validation
1. Test authentication with Logikal API
2. Test directory retrieval
3. Validate data caching in PostgreSQL
4. Test API endpoints

**Testing Scenarios:**
- **API Integration Tests**: Test real Logikal API connections
- **End-to-End Tests**: Test complete workflows
- **Performance Tests**: Test response times and throughput
- **Data Validation Tests**: Test data integrity and consistency

```python
# Example integration tests
def test_logikal_api_authentication():
    """Test real authentication with Logikal API"""
    auth_service = AuthService(
        base_url="https://logikal.api",
        username="test_user",
        password="test_pass"
    )
    try:
        token = auth_service.authenticate()
        assert token is not None
        assert len(token) > 0
    except Exception as e:
        pytest.skip(f"Logikal API not available: {e}")

def test_directory_retrieval_workflow():
    """Test complete directory retrieval workflow"""
    # 1. Authenticate
    # 2. Get directories
    # 3. Select directory
    # 4. Get projects
    # 5. Validate data structure

def test_api_endpoints():
    """Test all API endpoints"""
    # Test GET /directories
    # Test POST /auth/login
    # Test GET /auth/test
    # Test error responses
    # Test authentication requirements

def test_data_caching():
    """Test PostgreSQL data caching"""
    # Test directory data persistence
    # Test session data storage
    # Test API log recording
    # Test data retrieval performance
```

### Step 4: Minimal Interface
1. Create simple HTML interface for testing
2. Add connection test functionality
3. Display directory structure
4. Add basic error handling

**Testing Scenarios:**
- **UI Tests**: Test web interface functionality
- **User Experience Tests**: Test interface usability
- **Error Display Tests**: Test error message presentation
- **Responsive Tests**: Test interface on different screen sizes

```python
# Example UI tests
def test_web_interface_loading():
    """Test web interface loads correctly"""
    response = client.get("/")
    assert response.status_code == 200
    assert "Logikal Middleware" in response.text

def test_connection_test_functionality():
    """Test connection test feature"""
    # Test successful connection
    # Test failed connection
    # Test connection status display
    # Test error message handling

def test_directory_display():
    """Test directory structure display"""
    # Test directory list rendering
    # Test directory selection
    # Test project display
    # Test navigation functionality

def test_error_handling_ui():
    """Test error handling in UI"""
    # Test authentication errors
    # Test API connection errors
    # Test data loading errors
    # Test error message display
```

## Error Handling Strategy

### API Error Responses
```json
{
  "success": false,
  "error": {
    "code": "AUTHENTICATION_FAILED",
    "message": "Invalid credentials",
    "details": "Username or password incorrect"
  },
  "timestamp": "2024-01-01T12:00:00Z"
}
```

### Logging Strategy
- Structured logging with JSON format
- Different log levels for different components
- Request/response logging for debugging
- Error tracking and monitoring

## Security Considerations

### Authentication
- Secure token storage in Redis
- Token expiration and refresh
- Rate limiting on API endpoints
- Input validation and sanitization

### Data Protection
- Environment variable management
- Secure database connections
- HTTPS enforcement
- CORS configuration

## Performance Optimization

### Caching Strategy
- Redis for session management
- PostgreSQL for persistent data
- In-memory caching for frequently accessed data
- Background job processing for heavy operations

### Database Optimization
- Proper indexing on frequently queried fields
- Connection pooling
- Query optimization
- Regular maintenance tasks

## Monitoring and Observability

### Health Checks
- Database connectivity
- Redis connectivity
- Logikal API connectivity
- Service status endpoints

### Metrics Collection
- API response times
- Error rates
- Cache hit rates
- Database performance metrics

## Deployment Strategy

### Development Environment
- Docker Compose for local development
- Hot reloading for development
- Local PostgreSQL and Redis instances
- Environment variable configuration

### Production Considerations
- Container orchestration (Kubernetes/Docker Swarm)
- Load balancing
- Database clustering
- Redis clustering
- Monitoring and alerting

## Testing Strategy

### Unit Tests
- Service layer testing
- Model testing
- Utility function testing
- Mock external API calls

**Testing Scenarios:**
```python
# Service layer tests
def test_auth_service_methods():
    """Test all authentication service methods"""
    # Test authenticate()
    # Test validate_session()
    # Test logout()
    # Test error handling

def test_directory_service_methods():
    """Test all directory service methods"""
    # Test get_directories()
    # Test select_directory()
    # Test cache_directories()
    # Test error scenarios

def test_model_validation():
    """Test SQLAlchemy model validation"""
    # Test required fields
    # Test unique constraints
    # Test foreign key relationships
    # Test data types

def test_utility_functions():
    """Test utility and helper functions"""
    # Test data transformation
    # Test validation functions
    # Test formatting functions
    # Test error handling
```

### Integration Tests
- Database integration
- Redis integration
- API endpoint testing
- End-to-end workflow testing

**Testing Scenarios:**
```python
# Database integration tests
def test_database_operations():
    """Test database CRUD operations"""
    # Test data insertion
    # Test data retrieval
    # Test data updates
    # Test data deletion
    # Test transactions
    # Test rollbacks

def test_redis_operations():
    """Test Redis cache operations"""
    # Test cache storage
    # Test cache retrieval
    # Test cache expiration
    # Test cache invalidation
    # Test session storage

def test_api_endpoint_integration():
    """Test API endpoint integration"""
    # Test authentication endpoints
    # Test directory endpoints
    # Test project endpoints
    # Test error endpoints
    # Test response formats

def test_end_to_end_workflows():
    """Test complete user workflows"""
    # Test authentication flow
    # Test directory browsing flow
    # Test project selection flow
    # Test error recovery flow
```

### Performance Tests
- Load testing
- Stress testing
- Database performance testing
- Cache performance testing

**Testing Scenarios:**
```python
# Load testing scenarios
def test_concurrent_requests():
    """Test system under concurrent load"""
    # Test 100 concurrent users
    # Test 500 concurrent users
    # Test 1000 concurrent users
    # Measure response times
    # Test error rates

def test_database_performance():
    """Test database performance under load"""
    # Test query performance
    # Test connection pooling
    # Test transaction performance
    # Test index effectiveness
    # Test memory usage

def test_cache_performance():
    """Test Redis cache performance"""
    # Test cache hit rates
    # Test cache response times
    # Test memory usage
    # Test eviction policies
    # Test cluster performance

def test_api_response_times():
    """Test API response time performance"""
    # Test authentication response time
    # Test directory retrieval time
    # Test project listing time
    # Test error response time
    # Test under various loads
```

## Future Enhancements

### Phase 3: Advanced Features
- Project and phase synchronization
- Elevation and thumbnail management
- Parts list processing
- Background job processing with Celery

**Testing Scenarios:**
```python
# Advanced features tests
def test_project_synchronization():
    """Test project and phase synchronization"""
    # Test project data sync
    # Test phase data sync
    # Test data consistency
    # Test sync performance
    # Test error handling

def test_elevation_management():
    """Test elevation and thumbnail management"""
    # Test elevation data retrieval
    # Test thumbnail download
    # Test image caching
    # Test metadata storage
    # Test performance optimization

def test_parts_list_processing():
    """Test parts list processing and decoding"""
    # Test base64 decoding
    # Test SQLite parsing
    # Test data extraction
    # Test database storage
    # Test error handling

def test_background_jobs():
    """Test Celery background job processing"""
    # Test job queuing
    # Test job execution
    # Test job monitoring
    # Test error handling
    # Test job retry logic
```

### Phase 4: Production Features
- Multi-tenant support
- Advanced caching strategies
- Monitoring and alerting
- Performance optimization

**Testing Scenarios:**
```python
# Production features tests
def test_multi_tenant_support():
    """Test multi-tenant functionality"""
    # Test tenant isolation
    # Test tenant-specific data
    # Test tenant management
    # Test security boundaries
    # Test performance impact

def test_advanced_caching():
    """Test advanced caching strategies"""
    # Test cache invalidation
    # Test cache warming
    # Test cache partitioning
    # Test cache performance
    # Test cache consistency

def test_monitoring_alerting():
    """Test monitoring and alerting systems"""
    # Test metrics collection
    # Test alert generation
    # Test dashboard functionality
    # Test log aggregation
    # Test performance monitoring

def test_performance_optimization():
    """Test performance optimization features"""
    # Test query optimization
    # Test connection pooling
    # Test load balancing
    # Test resource utilization
    # Test scalability testing
```

### Phase 5: Odoo Integration
- Odoo module modification
- Middleware API integration
- Data synchronization
- Error handling and recovery

**Testing Scenarios:**
```python
# Odoo integration tests
def test_odoo_module_integration():
    """Test Odoo module integration"""
    # Test module installation
    # Test configuration
    # Test API integration
    # Test data flow
    # Test error handling

def test_middleware_api_integration():
    """Test middleware API integration with Odoo"""
    # Test authentication
    # Test data retrieval
    # Test data synchronization
    # Test error handling
    # Test performance

def test_data_synchronization():
    """Test data synchronization between systems"""
    # Test real-time sync
    # Test batch sync
    # Test conflict resolution
    # Test data consistency
    # Test sync performance

def test_error_handling_recovery():
    """Test error handling and recovery mechanisms"""
    # Test connection failures
    # Test data corruption
    # Test recovery procedures
    # Test rollback functionality
    # Test system resilience
```

## Recommendations (Optional Improvements)

### SQLite Decoder Pipeline
**Purpose**: Process and decode SQLite files in the background for performance optimization

**Implementation**:
- Add a task queue (e.g., Celery) to handle SQLite file processing
- Background jobs for base64 decoding and SQLite parsing
- Avoid blocking Odoo requests during heavy processing
- Queue management for handling multiple files concurrently

**Benefits**:
- Non-blocking API responses
- Better resource utilization
- Scalable processing of large parts lists
- Improved user experience

**Technical Stack**:
```python
# Task queue implementation
from celery import Celery

app = Celery('logikal_middleware')

@app.task
def process_sqlite_parts_list(parts_list_data: str, position_id: str):
    """Background task to decode and process SQLite parts list"""
    # Decode base64 SQLite data
    # Parse SQLite content
    # Store structured data in PostgreSQL
    # Update processing status
```

**Testing Scenarios:**
```python
# SQLite decoder pipeline tests
def test_sqlite_decoding():
    """Test SQLite file decoding functionality"""
    # Test base64 decoding
    # Test SQLite file parsing
    # Test data extraction
    # Test error handling
    # Test performance

def test_background_job_processing():
    """Test background job processing with Celery"""
    # Test job queuing
    # Test job execution
    # Test job monitoring
    # Test error handling
    # Test retry logic

def test_concurrent_processing():
    """Test concurrent SQLite file processing"""
    # Test multiple files processing
    # Test queue management
    # Test resource utilization
    # Test performance under load
    # Test error isolation

def test_data_consistency():
    """Test data consistency during processing"""
    # Test data integrity
    # Test transaction handling
    # Test rollback scenarios
    # Test data validation
    # Test error recovery
```

### Monitoring Stack
**Purpose**: Comprehensive observability and monitoring of the middleware system

#### Prometheus Metrics
- **API Metrics**: Request count, response time, error rates
- **Database Metrics**: Connection pool status, query performance
- **Cache Metrics**: Redis hit/miss rates, memory usage
- **Business Metrics**: Authentication success rates, data sync status

**Implementation**:
```python
from prometheus_client import Counter, Histogram, Gauge

# API metrics
api_requests_total = Counter('api_requests_total', 'Total API requests', ['method', 'endpoint', 'status'])
api_request_duration = Histogram('api_request_duration_seconds', 'API request duration')

# Database metrics
db_connections_active = Gauge('db_connections_active', 'Active database connections')
db_query_duration = Histogram('db_query_duration_seconds', 'Database query duration')
```

#### Grafana Dashboards
- **System Overview**: Service health, resource utilization
- **API Performance**: Response times, error rates, throughput
- **Database Performance**: Query performance, connection status
- **Business Metrics**: Logikal API integration status, data sync progress

#### Logging and Tracing
- **Structured Logging**: JSON format with correlation IDs
- **Distributed Tracing**: Request flow across services
- **Error Tracking**: Integration with Sentry or similar
- **Audit Logging**: Authentication events, data access logs

**Implementation**:
```python
import structlog
import sentry_sdk

# Structured logging
logger = structlog.get_logger()

# Error tracking
sentry_sdk.init(
    dsn="your-sentry-dsn",
    traces_sample_rate=1.0,
    environment="production"
)
```

**Testing Scenarios:**
```python
# Monitoring stack tests
def test_prometheus_metrics():
    """Test Prometheus metrics collection"""
    # Test API metrics collection
    # Test database metrics collection
    # Test cache metrics collection
    # Test business metrics collection
    # Test metrics accuracy

def test_grafana_dashboards():
    """Test Grafana dashboard functionality"""
    # Test dashboard loading
    # Test data visualization
    # Test alert configuration
    # Test dashboard performance
    # Test user access control

def test_structured_logging():
    """Test structured logging functionality"""
    # Test log format consistency
    # Test correlation ID tracking
    # Test log level filtering
    # Test log aggregation
    # Test log performance

def test_error_tracking():
    """Test error tracking and alerting"""
    # Test error capture
    # Test error categorization
    # Test alert generation
    # Test error resolution tracking
    # Test performance impact
```

### Middleware Authentication for Odoo Clients
**Purpose**: Secure authentication layer for external systems connecting to the middleware

**Implementation**:
- JWT-based authentication for Odoo instances
- API key management for different clients
- Role-based access control (RBAC)
- Rate limiting per client

**Authentication Flow**:
```python
# JWT token generation
from jose import jwt
from datetime import datetime, timedelta

def generate_client_token(client_id: str, permissions: List[str]) -> str:
    payload = {
        "client_id": client_id,
        "permissions": permissions,
        "exp": datetime.utcnow() + timedelta(hours=24)
    }
    return jwt.encode(payload, SECRET_KEY, algorithm="HS256")
```

**API Endpoints**:
```http
POST /auth/client/register
POST /auth/client/login
GET /auth/client/validate
POST /auth/client/refresh
```

**Database Schema**:
```sql
CREATE TABLE client_credentials (
    id SERIAL PRIMARY KEY,
    client_id VARCHAR(255) UNIQUE NOT NULL,
    client_secret_hash VARCHAR(255) NOT NULL,
    permissions JSONB NOT NULL,
    rate_limit_per_hour INTEGER DEFAULT 1000,
    is_active BOOLEAN DEFAULT true,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);
```

**Testing Scenarios:**
```python
# Middleware authentication tests
def test_jwt_token_generation():
    """Test JWT token generation and validation"""
    # Test token creation
    # Test token validation
    # Test token expiration
    # Test token refresh
    # Test token security

def test_api_key_management():
    """Test API key management functionality"""
    # Test key generation
    # Test key validation
    # Test key rotation
    # Test key revocation
    # Test key security

def test_role_based_access_control():
    """Test role-based access control (RBAC)"""
    # Test permission checking
    # Test role assignment
    # Test access control enforcement
    # Test permission inheritance
    # Test security boundaries

def test_rate_limiting():
    """Test rate limiting functionality"""
    # Test rate limit enforcement
    # Test rate limit reset
    # Test rate limit bypass
    # Test rate limit monitoring
    # Test performance impact
```

### Multi-Tenant Support (Future Phase)
**Purpose**: Support multiple Odoo instances connecting to the same middleware

**Implementation Strategy**:
- Tenant-aware database schema with `tenant_id` columns
- Tenant isolation at the application level
- Shared infrastructure with data segregation
- Tenant-specific configuration management

**Database Schema Updates**:
```sql
-- Add tenant_id to core tables
ALTER TABLE directories ADD COLUMN tenant_id VARCHAR(255) NOT NULL;
ALTER TABLE projects ADD COLUMN tenant_id VARCHAR(255) NOT NULL;
ALTER TABLE phases ADD COLUMN tenant_id VARCHAR(255) NOT NULL;
ALTER TABLE elevations ADD COLUMN tenant_id VARCHAR(255) NOT NULL;

-- Create tenant management table
CREATE TABLE tenants (
    id SERIAL PRIMARY KEY,
    tenant_id VARCHAR(255) UNIQUE NOT NULL,
    name VARCHAR(255) NOT NULL,
    logikal_config JSONB NOT NULL,
    is_active BOOLEAN DEFAULT true,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);
```

**Application-Level Changes**:
```python
# Tenant-aware service
class TenantAwareService:
    def __init__(self, tenant_id: str):
        self.tenant_id = tenant_id
    
    async def get_directories(self) -> List[Directory]:
        return await self.db.query(Directory).filter(
            Directory.tenant_id == self.tenant_id
        ).all()
```

**Benefits**:
- Cost-effective shared infrastructure
- Centralized management and monitoring
- Easier maintenance and updates
- Scalable architecture for multiple clients

**Testing Scenarios:**
```python
# Multi-tenant support tests
def test_tenant_isolation():
    """Test tenant data isolation"""
    # Test data segregation
    # Test cross-tenant access prevention
    # Test tenant-specific queries
    # Test data leakage prevention
    # Test security boundaries

def test_tenant_management():
    """Test tenant management functionality"""
    # Test tenant creation
    # Test tenant configuration
    # Test tenant deactivation
    # Test tenant data migration
    # Test tenant monitoring

def test_shared_infrastructure():
    """Test shared infrastructure functionality"""
    # Test resource sharing
    # Test performance isolation
    # Test resource allocation
    # Test scalability testing
    # Test cost optimization

def test_tenant_specific_configuration():
    """Test tenant-specific configuration management"""
    # Test configuration isolation
    # Test configuration inheritance
    # Test configuration validation
    # Test configuration updates
    # Test configuration security
```

## Conclusion

This middleware solution will provide a robust, scalable foundation for integrating Odoo with the Logikal API. The phased approach ensures a working MVP can be delivered quickly while providing a clear path for future enhancements.

The key benefits of this approach include:
- **Decoupling**: Odoo no longer directly depends on Logikal API complexity
- **Performance**: Caching and preprocessing improve response times
- **Reliability**: Centralized error handling and monitoring
- **Scalability**: Can handle multiple Odoo instances and Logikal connections
- **Maintainability**: Clear separation of concerns and modular design

The implementation should start with the MVP features (authentication, directory retrieval, basic interface) and then gradually add more sophisticated features based on requirements and testing results.

### Recommended Implementation Order
1. **Phase 1**: MVP with basic authentication and directory retrieval
2. **Phase 2**: Add monitoring stack (Prometheus, Grafana, structured logging)
3. **Phase 3**: Implement SQLite decoder pipeline with Celery
4. **Phase 4**: Add middleware authentication for Odoo clients
5. **Phase 5**: Implement multi-tenant support for production scale
