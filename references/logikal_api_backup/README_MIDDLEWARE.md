# Logikal API Module - Middleware Integration

## Overview

This module provides comprehensive integration with the Logikal API system, supporting both direct API connections and middleware-based integration. The middleware integration offers simplified navigation, cached data access, and improved performance.

## Features

### Dual Integration Support
- **Direct API**: Traditional direct connection to Logikal API (existing functionality)
- **Middleware**: Modern integration via Logikal Middleware (recommended)

### Middleware Benefits
- Simplified navigation (no folder selection required)
- Cached data for improved performance
- JWT-based authentication
- Unified service layer
- Better error handling and logging

## Installation

### Prerequisites

1. **Odoo 18.0** or compatible version
2. **Python dependencies**:
   - `requests` (already included in Odoo)
3. **Logikal Middleware** (if using middleware integration)
   - Running on `http://localhost:8001` (default)
   - Client authentication configured

### Installation Steps

1. **Copy the module** to your Odoo addons directory:
   ```bash
   cp -r logikal_api /path/to/odoo/addons/
   ```

2. **Update the addons list**:
   ```bash
   # Restart Odoo or update addons list through UI
   # Settings > Apps > Update Apps List
   ```

3. **Install the module**:
   - Go to Apps menu in Odoo
   - Search for "Logikal"
   - Click Install

4. **Configure the integration**:
   - Go to Settings > General Settings
   - Find "Logikal API Integration" section
   - Choose integration mode and configure accordingly

## Configuration

### Integration Mode Selection

The module supports two integration modes:

#### Option 1: Middleware Integration (Recommended)

1. **Enable Middleware Integration**:
   - Check "Use Middleware Integration" in settings

2. **Configure Middleware Settings**:
   - **Middleware API URL**: `http://localhost:8001` (default)
   - **Client ID**: Your middleware client ID
   - **Client Secret**: Your middleware client secret
   - **Connection Timeout**: 30 seconds (default)
   - **Log Retention**: 30 days (default)

#### Option 2: Direct API Integration

1. **Disable Middleware Integration**:
   - Uncheck "Use Middleware Integration" in settings

2. **Configure Direct API Settings**:
   - **Logikal API URL**: Your Logikal API endpoint
   - **Username**: Your Logikal API username
   - **Password**: Your Logikal API password
   - **Connection Timeout**: 30 seconds (default)
   - **Log Retention**: 30 days (default)

### Configuration Validation

The module validates configuration settings:
- API URLs must start with `http://` or `https://`
- Connection timeouts must be between 5 and 300 seconds
- Log retention days cannot be negative
- Required fields must be filled when integration mode is enabled

## Usage

### Operations Console

Access the operations console through:
**Logikal > Operations Console**

#### Available Operations:

1. **Test Connection**: Verify connectivity to the active system
2. **Sync All Projects**: Synchronize all projects from the active system
3. **Sync Single Project**: Synchronize a specific project (opens wizard)
4. **Switch Integration Mode**: Toggle between middleware and direct API
5. **Refresh Data**: Update the console statistics
6. **Cleanup Old Logs**: Remove old session log entries

### Project Management

Access projects through:
**Logikal > Projects**

#### Features:
- View all synchronized projects
- Filter by sync status (synced, pending, error)
- Search projects by name or description
- Group by status or sync status
- Access project details, phases, and elevations

### Phase Management

Access phases through:
**Logikal > Phases**

#### Features:
- View all synchronized phases
- Filter by project, status, or sync status
- Group by project or status
- Access phase details and elevations

### Elevation Management

Access elevations through:
**Logikal > Elevations**

#### Features:
- View all synchronized elevations
- Filter by project, phase, or sync status
- Group by project, phase, or status
- View elevation thumbnails
- Access elevation details and dimensions

### Session Logs

Access session logs through:
**Logikal > Session Logs**

#### Features:
- View all API operation logs
- Filter by operation type, status, or user
- View request/response details
- Monitor system performance
- Debug integration issues

## Testing

### Running Tests

The module includes comprehensive test coverage:

```bash
# Run all tests
odoo-bin -d test_db -i logikal_api --test-enable --stop-after-init

# Run specific test file
odoo-bin -d test_db -i logikal_api --test-enable --test-tags /logikal_api/tests/test_middleware_client.py --stop-after-init
```

### Test Coverage

The test suite covers:

1. **Middleware Client** (`test_middleware_client.py`):
   - Authentication success/failure
   - Project retrieval
   - Project complete data retrieval
   - Project search
   - Connection error handling
   - Token expiration handling

2. **Logikal Service** (`test_logikal_service.py`):
   - Configuration type detection
   - Connection testing
   - Project synchronization
   - Session log management
   - Error handling
   - MBIOE fallback

3. **Logikal Models** (`test_logikal_models.py`):
   - Project model operations
   - Phase model operations
   - Elevation model operations
   - Session log operations
   - Data validation
   - Access control

4. **Configuration** (`test_configuration.py`):
   - Configuration validation
   - Default values
   - Active configuration detection
   - Error handling

### Manual Testing

#### Test Middleware Integration:

1. **Configure middleware settings**:
   - Enable middleware integration
   - Set correct middleware URL, client ID, and secret

2. **Test connection**:
   - Go to Operations Console
   - Click "Test Connection"
   - Verify success message

3. **Sync projects**:
   - Click "Sync All Projects"
   - Verify projects appear in Projects view
   - Check that phases and elevations are populated

4. **Test individual operations**:
   - Sync single project
   - Search projects
   - View project details
   - Access session logs

#### Test Direct API Integration:

1. **Configure direct API settings**:
   - Disable middleware integration
   - Set correct API URL, username, and password

2. **Test connection**:
   - Go to Operations Console
   - Click "Test Connection"
   - Verify success message

3. **Test operations**:
   - Use existing MBIOE functionality
   - Verify backward compatibility

## Troubleshooting

### Common Issues

#### 1. Connection Test Fails

**Symptoms**: "Connection Test Failed" message
**Solutions**:
- Verify middleware is running and accessible
- Check middleware URL configuration
- Verify client ID and secret are correct
- Check network connectivity
- Review middleware logs for errors

#### 2. Projects Not Syncing

**Symptoms**: No projects appear after sync operation
**Solutions**:
- Check middleware has data available
- Verify middleware sync is up to date
- Check Odoo logs for errors
- Verify user permissions
- Test middleware API endpoints directly

#### 3. Configuration Validation Errors

**Symptoms**: Configuration validation errors on save
**Solutions**:
- Ensure API URLs start with `http://` or `https://`
- Check timeout values are between 5-300 seconds
- Verify log retention days are not negative
- Ensure all required fields are filled

#### 4. Permission Errors

**Symptoms**: Access denied errors
**Solutions**:
- Check user has proper group membership
- Verify model access rights
- Check record rules
- Ensure user has appropriate permissions

### Debug Mode

Enable debug logging for detailed troubleshooting:

1. **Enable debug logging** in settings (for direct API mode)
2. **Check session logs** for detailed API call information
3. **Review Odoo logs** for error messages
4. **Test middleware endpoints** directly using curl or Postman

### Log Analysis

Session logs provide detailed information about API operations:

- **Operation type**: login, api_call, etc.
- **Status**: success or failed
- **Response code**: HTTP status code
- **Duration**: Operation time in milliseconds
- **Request details**: URL, method, payload
- **Response details**: Response body and summary
- **Error messages**: Detailed error information

## Migration from Direct API

### Migration Steps

1. **Backup existing data**:
   ```sql
   -- Backup MBIOE tables
   pg_dump -t mbioe_project -t mbioe_phase -t mbioe_elevation your_db > mbioe_backup.sql
   ```

2. **Install middleware integration**:
   - Deploy and configure middleware
   - Update Odoo module
   - Configure middleware settings

3. **Test middleware integration**:
   - Run connection tests
   - Sync sample projects
   - Verify data consistency

4. **Switch to middleware mode**:
   - Enable middleware integration in settings
   - Sync all projects
   - Verify functionality

5. **Clean up old data** (optional):
   - Remove old MBIOE data if no longer needed
   - Update user training and documentation

### Data Consistency

Ensure data consistency during migration:

1. **Compare project counts** between old and new systems
2. **Verify project details** match between systems
3. **Check phase and elevation data** completeness
4. **Test search functionality** with known data
5. **Validate user workflows** work correctly

## Support

### Getting Help

1. **Check this documentation** for common issues and solutions
2. **Review session logs** for error details
3. **Check Odoo logs** for system errors
4. **Test middleware endpoints** directly
5. **Contact support** with detailed error information

### Reporting Issues

When reporting issues, include:

1. **Odoo version** and module version
2. **Integration mode** (middleware or direct API)
3. **Configuration details** (without sensitive data)
4. **Error messages** from logs
5. **Steps to reproduce** the issue
6. **Expected vs actual behavior**

### Development

For developers working on the module:

1. **Follow Odoo coding standards**
2. **Add tests** for new functionality
3. **Update documentation** for changes
4. **Test both integration modes**
5. **Ensure backward compatibility**

## Version History

### Version 18.0.1.9.1

- Added middleware integration support
- Implemented unified service layer
- Added new middleware-based models
- Created comprehensive test suite
- Added operations console for middleware
- Enhanced configuration management
- Improved error handling and logging

### Future Enhancements

- Real-time sync notifications
- Advanced search capabilities
- Bulk operations optimization
- Performance monitoring dashboard
- Automated data validation
- Enhanced reporting features
