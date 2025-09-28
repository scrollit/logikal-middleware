# Logikal Middleware API - Quick Reference Guide

## 🚀 Quick Start

### Base URL
```
http://localhost:8001
```

### Admin UI
```
http://localhost:8001/ui
```

## 📋 Most Common Endpoints

### For Admin UI Development
```bash
# View cached data
GET /api/v1/directories/cached
GET /api/v1/projects/cached
GET /api/v1/phases/cached
GET /api/v1/elevations/cached

# Trigger sync operations
POST /api/v1/sync/directories
POST /api/v1/sync/projects
POST /api/v1/sync/phases
POST /api/v1/sync/elevations

# Check sync status
GET /api/v1/sync/status
```

### For Odoo Integration
```bash
# Get project data
GET /api/v1/odoo/projects
GET /api/v1/odoo/projects/{project_id}

# Get phase data
GET /api/v1/odoo/projects/{project_id}/phases

# Get elevation data
GET /api/v1/odoo/projects/{project_id}/phases/{phase_id}/elevations

# Search functionality
GET /api/v1/odoo/search?q=search_term

# System stats
GET /api/v1/odoo/stats
```

## 🔐 Authentication

### Admin UI
- No authentication required for cached endpoints
- Uses environment credentials for sync operations

### Odoo Integration
```bash
# Register client
POST /api/v1/client-auth/register
{
    "client_name": "odoo_integration",
    "permissions": ["projects_read", "phases_read", "elevations_read"]
}

# Login
POST /api/v1/client-auth/login
{
    "client_name": "odoo_integration",
    "client_secret": "your_secret"
}

# Use token in requests
Authorization: Bearer <jwt_token>
```

## 📊 Response Formats

### Success Response
```json
{
    "success": true,
    "data": [...],
    "count": 24,
    "last_updated": "2025-09-28T10:30:00Z",
    "sync_status": "cached"
}
```

### Error Response
```json
{
    "detail": "Error message",
    "code": "ERROR_CODE"
}
```

## 🛠️ Development Commands

### Start Development Environment
```bash
docker-compose up -d
```

### View Logs
```bash
docker-compose logs web -f
```

### Test Endpoints
```bash
# Test directories endpoint
curl http://localhost:8001/api/v1/directories/cached

# Test sync
curl -X POST http://localhost:8001/api/v1/sync/directories
```

### Restart Services
```bash
docker-compose restart web
```

## 🔧 Configuration

### Environment Variables
```bash
# Logikal API
LOGIKAL_API_BASE_URL=http://128.199.57.77/MbioeService.svc/api/v3/
LOGIKAL_AUTH_USERNAME=Jasper
LOGIKAL_AUTH_PASSWORD=OdooAPI

# Database
DATABASE_URL=postgresql://admin:admin@db:5432/logikal_middleware

# Security
SECRET_KEY=your-super-secret-key
JWT_SECRET_KEY=your-jwt-secret-key
```

## 📈 Monitoring

### Health Check
```bash
curl http://localhost:8001/health
```

### Metrics (if Prometheus enabled)
```bash
curl http://localhost:8001/metrics
```

### Celery Monitoring
```bash
# Flower dashboard
http://localhost:5555
```

## 🐛 Troubleshooting

### Common Issues

1. **500 Error on cached endpoints**
   - Check database connectivity
   - Verify model field names match API response

2. **Authentication failures**
   - Verify Logikal API credentials
   - Check network connectivity to Logikal API

3. **Sync taking too long**
   - Normal for large datasets
   - Check logs for progress: `docker-compose logs web -f`

4. **UI not displaying data**
   - Check JavaScript field name mappings
   - Verify API response structure matches UI expectations

### Debug Commands
```bash
# Check container status
docker-compose ps

# View application logs
docker-compose logs web --tail=50

# Check database
docker exec -it logikal-db psql -U admin -d logikal_middleware

# Test API connectivity
curl -v http://localhost:8001/api/v1/directories/cached
```

## 📚 Additional Resources

- **Full Documentation**: `API_Architecture_Documentation.md`
- **UI Development Analysis**: `UI_Development_Analysis.md`
- **Postman Collections**: Available in project root
- **Docker Compose**: `docker-compose.yml`

---

*Quick Reference - Last Updated: September 28, 2025*
