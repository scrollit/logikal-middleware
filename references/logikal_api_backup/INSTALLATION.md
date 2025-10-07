# Installation and Configuration Guide

## Quick Start

### Prerequisites

1. **Odoo 18.0** or compatible version
2. **Logikal Middleware** running (for middleware integration)
3. **Python requests** library (included with Odoo)

### Installation Steps

1. **Install the module**:
   ```bash
   # Copy module to addons directory
   cp -r logikal_api /path/to/odoo/addons/
   
   # Restart Odoo
   sudo systemctl restart odoo
   
   # Or update apps list in Odoo UI: Settings > Apps > Update Apps List
   ```

2. **Install through Odoo UI**:
   - Go to Apps menu
   - Search for "Logikal"
   - Click Install

3. **Configure integration**:
   - Go to Settings > General Settings
   - Find "Logikal API Integration" section
   - Choose integration mode and configure

## Configuration Options

### Option 1: Middleware Integration (Recommended)

**Advantages:**
- Simplified navigation (no folder selection)
- Cached data for better performance
- JWT authentication
- Better error handling

**Configuration:**
```
Integration Mode: ☑ Use Middleware Integration

Middleware Settings:
- API URL: http://localhost:8001
- Client ID: your_client_id
- Client Secret: your_client_secret
- Connection Timeout: 30 seconds
- Log Retention: 30 days
```

**Requirements:**
- Logikal Middleware must be running
- Client authentication configured in middleware
- Middleware has synced data from Logikal API

### Option 2: Direct API Integration

**Advantages:**
- Direct connection to Logikal API
- No additional middleware dependency
- Existing functionality preserved

**Configuration:**
```
Integration Mode: ☐ Use Middleware Integration

Direct API Settings:
- API URL: https://your-logikal-api.com/api/v3
- Username: your_username
- Password: your_password
- Connection Timeout: 30 seconds
- Log Retention: 30 days
- Debug Logging: ☐ (optional)
```

**Requirements:**
- Direct access to Logikal API
- Valid API credentials
- Network connectivity to Logikal API

## Testing the Installation

### 1. Test Connection

1. Go to **Logikal > Operations Console**
2. Click **"Test Connection"**
3. Verify success message appears

### 2. Test Data Sync

**For Middleware Integration:**
1. Click **"Sync All Projects"**
2. Go to **Logikal > Projects**
3. Verify projects appear in the list

**For Direct API Integration:**
1. Use existing MBIOE sync operations
2. Verify projects sync correctly

### 3. Verify Functionality

1. **Browse Projects**: Go to Logikal > Projects
2. **View Details**: Click on a project to see details
3. **Check Phases**: Verify phases are populated
4. **Check Elevations**: Verify elevations are available
5. **Test Search**: Use search functionality
6. **View Logs**: Check Logikal > Session Logs

## Troubleshooting

### Connection Issues

**Problem**: Connection test fails
**Solutions**:
- Verify middleware is running: `curl http://localhost:8001/health`
- Check middleware URL configuration
- Verify client credentials
- Check network connectivity
- Review middleware logs

### No Projects Appearing

**Problem**: Projects don't appear after sync
**Solutions**:
- Check middleware has data: `curl http://localhost:8001/api/v1/odoo/projects`
- Verify middleware sync is up to date
- Check Odoo logs for errors
- Verify user permissions
- Test with middleware admin interface

### Configuration Errors

**Problem**: Configuration validation errors
**Solutions**:
- Ensure API URLs start with `http://` or `https://`
- Check timeout values are 5-300 seconds
- Verify log retention days are not negative
- Fill all required fields

### Permission Errors

**Problem**: Access denied errors
**Solutions**:
- Check user group membership
- Verify model access rights
- Check record rules
- Ensure proper permissions

## Advanced Configuration

### Environment Variables

You can also configure using environment variables:

```bash
# Middleware Configuration
export LOGIKAL_USE_MIDDLEWARE=true
export LOGIKAL_MIDDLEWARE_URL=http://localhost:8001
export LOGIKAL_MIDDLEWARE_CLIENT_ID=your_client_id
export LOGIKAL_MIDDLEWARE_CLIENT_SECRET=your_client_secret

# Direct API Configuration
export LOGIKAL_API_URL=https://your-api.com/api/v3
export LOGIKAL_USERNAME=your_username
export LOGIKAL_PASSWORD=your_password
```

### Database Configuration

For production deployments, consider:

1. **Database backup** before installation
2. **Migration scripts** for existing data
3. **Performance tuning** for large datasets
4. **Monitoring setup** for production use

### Security Considerations

1. **Secure credentials** storage
2. **Network security** for API connections
3. **User access control** and permissions
4. **Audit logging** for compliance
5. **Regular security updates**

## Migration from Existing Installation

### From Direct API to Middleware

1. **Backup existing data**:
   ```sql
   pg_dump -t mbioe_project -t mbioe_phase -t mbioe_elevation your_db > backup.sql
   ```

2. **Deploy middleware**:
   - Install and configure Logikal Middleware
   - Sync data from Logikal API to middleware
   - Verify middleware functionality

3. **Update Odoo configuration**:
   - Enable middleware integration
   - Configure middleware settings
   - Test connection

4. **Sync data**:
   - Use "Sync All Projects" to populate new models
   - Verify data consistency
   - Test user workflows

5. **Clean up** (optional):
   - Remove old MBIOE data if no longer needed
   - Update documentation and training

### Data Validation

Ensure data consistency during migration:

```sql
-- Compare project counts
SELECT COUNT(*) FROM mbioe_project;
SELECT COUNT(*) FROM logikal_project;

-- Compare specific projects
SELECT name, logikal_id FROM mbioe_project ORDER BY name;
SELECT name, logikal_id FROM logikal_project ORDER BY name;
```

## Performance Optimization

### For Large Datasets

1. **Batch processing**: Sync projects in smaller batches
2. **Background jobs**: Use Odoo's queue_job for large operations
3. **Database optimization**: Index frequently queried fields
4. **Caching**: Leverage middleware caching capabilities

### Monitoring

1. **Session logs**: Monitor API call performance
2. **Database queries**: Track query performance
3. **Memory usage**: Monitor Odoo worker memory
4. **Network latency**: Track API response times

## Support and Maintenance

### Regular Maintenance

1. **Log cleanup**: Regular cleanup of old session logs
2. **Data sync**: Regular sync to keep data current
3. **Performance monitoring**: Track system performance
4. **Security updates**: Keep system and dependencies updated

### Backup Strategy

1. **Database backups**: Regular database backups
2. **Configuration backups**: Backup configuration settings
3. **Middleware backups**: Backup middleware data
4. **Disaster recovery**: Test restore procedures

### Monitoring Setup

1. **Health checks**: Monitor Odoo and middleware health
2. **Error tracking**: Set up error monitoring and alerting
3. **Performance metrics**: Track key performance indicators
4. **User activity**: Monitor user usage patterns

## Getting Help

### Documentation

1. **Module documentation**: README_MIDDLEWARE.md
2. **API documentation**: Logikal Middleware API docs
3. **Odoo documentation**: Official Odoo documentation
4. **Community forums**: Odoo community support

### Support Channels

1. **Issue tracking**: Report bugs and feature requests
2. **Community support**: Odoo community forums
3. **Professional support**: Contact for commercial support
4. **Documentation**: Check documentation for common issues

### Debugging

1. **Enable debug mode**: Turn on detailed logging
2. **Check logs**: Review Odoo and middleware logs
3. **Test endpoints**: Verify API endpoints directly
4. **Isolate issues**: Test with minimal configuration

## Conclusion

This installation guide provides comprehensive instructions for setting up the Logikal API module with both middleware and direct API integration options. The middleware integration is recommended for new installations due to its improved performance, simplified navigation, and better error handling.

For additional support or questions, refer to the main documentation or contact support with detailed information about your specific setup and issues.
