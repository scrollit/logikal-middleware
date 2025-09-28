from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles
from fastapi.responses import HTMLResponse
from core.config import settings
from core.config_production import get_settings as get_production_settings, validate_required_settings
from core.logging import setup_logging, LoggingMiddleware
from core.security_production import setup_security_middleware
from monitoring.prometheus import setup_prometheus_metrics
from monitoring.health import router as health_router
from routers import auth_router, directories_router, projects_router, elevations_router, phases_router, sync_router, client_auth, odoo, sync_status, scheduler, advanced_sync
import logging

# Get production settings
production_settings = get_production_settings()

# Setup logging
setup_logging(
    environment=production_settings.ENVIRONMENT,
    log_level=production_settings.LOG_LEVEL
)

# Validate required settings
try:
    validate_required_settings()
except ValueError as e:
    logging.error(f"Configuration validation failed: {e}")
    raise

app = FastAPI(
    title=production_settings.APP_NAME,
    version=production_settings.APP_VERSION,
    description="Middleware for integrating Odoo with Logikal API",
    debug=production_settings.DEBUG
)

# Include routers
app.include_router(auth_router, prefix=settings.API_V1_STR)
app.include_router(directories_router, prefix=settings.API_V1_STR)
app.include_router(projects_router, prefix=settings.API_V1_STR)
app.include_router(phases_router, prefix=settings.API_V1_STR)
app.include_router(elevations_router, prefix=settings.API_V1_STR)
app.include_router(sync_router, prefix=settings.API_V1_STR)
app.include_router(client_auth.router, prefix=settings.API_V1_STR)
app.include_router(odoo.router, prefix=settings.API_V1_STR)
app.include_router(sync_status.router, prefix=settings.API_V1_STR)
app.include_router(scheduler.router, prefix=settings.API_V1_STR)
app.include_router(advanced_sync.router, prefix=settings.API_V1_STR)
app.include_router(health_router, prefix=settings.API_V1_STR)

# Setup production middleware
if production_settings.ENVIRONMENT == "production":
    setup_security_middleware(app)

# Setup Prometheus metrics
if production_settings.PROMETHEUS_ENABLED:
    setup_prometheus_metrics(app)

# Setup logging middleware
app.add_middleware(LoggingMiddleware)

@app.get("/")
async def root():
    return {"message": "Logikal Middleware is running!", "version": settings.APP_VERSION}

@app.get("/health")
async def health_check():
    return {"status": "healthy", "version": settings.APP_VERSION}

@app.get("/ui", response_class=HTMLResponse)
async def get_ui():
    """Enhanced Admin Dashboard with Phase 1 (Dashboard) and Phase 2 (Advanced Sync Management)"""
    html_content = """
    <!DOCTYPE html>
    <html>
    <head>
        <title>Logikal Middleware - Admin Dashboard</title>
        <meta charset="UTF-8">
        <meta name="viewport" content="width=device-width, initial-scale=1.0">
        <style>
            * { box-sizing: border-box; margin: 0; padding: 0; }
            body { 
                font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif; 
                background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
                min-height: 100vh;
                color: #333;
            }
            
            .container { 
                max-width: 1400px; 
                margin: 0 auto; 
                background-color: white; 
                min-height: 100vh;
                box-shadow: 0 0 30px rgba(0,0,0,0.1);
            }
            
            .header {
                background-color: #2c3e50;
                color: white;
                padding: 20px 30px;
                display: flex;
                justify-content: space-between;
                align-items: center;
            }
            
            .header h1 { font-size: 24px; font-weight: 300; }
            .header .version { opacity: 0.8; font-size: 14px; }
            
            .nav { 
                background-color: #343a40; 
                padding: 10px 30px; 
                border-bottom: 2px solid #495057;
                display: flex;
                gap: 0;
                box-shadow: 0 2px 4px rgba(0,0,0,0.1);
            }
            
            .nav button { 
                padding: 15px 25px; 
                border: none; 
                background-color: #495057; 
                color: white; 
                cursor: pointer; 
                border-bottom: 3px solid transparent;
                font-weight: 600;
                transition: all 0.3s ease;
                border-radius: 8px 8px 0 0;
                margin: 0 2px;
            }
            
            .nav button.active { 
                background-color: #007bff;
                color: white; 
                border-bottom-color: #ffffff;
                box-shadow: 0 -2px 8px rgba(0,0,0,0.15);
            }
            
            .nav button:hover { 
                background-color: #6c757d; 
                color: white;
                transform: translateY(-1px);
            }
            
            .page { display: none; padding: 30px; }
            .page.active { display: block; }
            
            /* Dashboard Grid Layout */
            .dashboard-grid {
                display: grid;
                grid-template-columns: repeat(auto-fit, minmax(300px, 1fr));
                gap: 20px;
                margin-bottom: 30px;
            }
            
            .card {
                background: white;
                border-radius: 12px;
                padding: 25px;
                box-shadow: 0 4px 15px rgba(0,0,0,0.08);
                border: 1px solid #e9ecef;
                transition: transform 0.2s ease, box-shadow 0.2s ease;
            }
            
            .card:hover {
                transform: translateY(-2px);
                box-shadow: 0 8px 25px rgba(0,0,0,0.12);
            }
            
            .card-header {
                display: flex;
                justify-content: space-between;
                align-items: center;
                margin-bottom: 20px;
                padding-bottom: 15px;
                border-bottom: 1px solid #e9ecef;
            }
            
            .card-title {
                font-size: 18px;
                font-weight: 600;
                color: #2c3e50;
            }
            
            .status-indicator {
                width: 12px;
                height: 12px;
                border-radius: 50%;
                margin-right: 8px;
                display: inline-block;
            }
            
            .status-success { background-color: #28a745; }
            .status-error { background-color: #dc3545; }
            .status-warning { background-color: #ffc107; }
            .status-info { background-color: #17a2b8; }
            
            .metric-value {
                font-size: 32px;
                font-weight: 700;
                color: #2c3e50;
                margin: 10px 0;
            }
            
            .metric-label {
                font-size: 14px;
                color: #6c757d;
                text-transform: uppercase;
                letter-spacing: 0.5px;
            }
            
            .progress-bar {
                width: 100%;
                height: 8px;
                background-color: #e9ecef;
                border-radius: 4px;
                overflow: hidden;
                margin: 10px 0;
            }
            
            .progress-fill {
                height: 100%;
                background: linear-gradient(90deg, #28a745, #20c997);
                transition: width 0.3s ease;
            }
            
            .alert-list {
                max-height: 300px;
                overflow-y: auto;
            }
            
            .alert-item {
                padding: 12px;
                margin: 8px 0;
                border-radius: 8px;
                border-left: 4px solid;
                background-color: #f8f9fa;
            }
            
            .alert-critical { border-left-color: #dc3545; background-color: #f8d7da; }
            .alert-warning { border-left-color: #ffc107; background-color: #fff3cd; }
            .alert-info { border-left-color: #17a2b8; background-color: #d1ecf1; }
            
            /* Sync Management Styles */
            .sync-controls {
                display: grid;
                grid-template-columns: repeat(auto-fit, minmax(250px, 1fr));
                gap: 20px;
                margin-bottom: 30px;
            }
            
            .control-group {
                background: white;
                border-radius: 12px;
                padding: 25px;
                box-shadow: 0 4px 15px rgba(0,0,0,0.08);
                border: 1px solid #e9ecef;
            }
            
            .control-title {
                font-size: 16px;
                font-weight: 600;
                color: #2c3e50;
                margin-bottom: 15px;
            }
            
            .form-group {
                margin: 15px 0;
            }
            
            label {
                display: block;
                margin-bottom: 8px;
                font-weight: 500;
                color: #495057;
            }
            
            input, select, button {
                width: 100%;
                padding: 12px;
                border: 1px solid #ced4da;
                border-radius: 8px;
                font-size: 14px;
                transition: border-color 0.3s ease, box-shadow 0.3s ease;
            }
            
            input:focus, select:focus {
                outline: none;
                border-color: #007bff;
                box-shadow: 0 0 0 3px rgba(0,123,255,0.1);
            }
            
            button {
                background: linear-gradient(135deg, #007bff 0%, #0056b3 100%);
                color: white;
                border: none;
                cursor: pointer;
                font-weight: 500;
                margin: 5px 0;
                transition: all 0.3s ease;
            }
            
            button:hover {
                transform: translateY(-1px);
                box-shadow: 0 4px 15px rgba(0,123,255,0.3);
            }
            
            button:disabled {
                background: #6c757d;
                cursor: not-allowed;
                transform: none;
                box-shadow: none;
            }
            
            .btn-success { background: linear-gradient(135deg, #28a745 0%, #20c997 100%); }
            .btn-warning { background: linear-gradient(135deg, #ffc107 0%, #fd7e14 100%); }
            .btn-danger { background: linear-gradient(135deg, #dc3545 0%, #e83e8c 100%); }
            .btn-info { background: linear-gradient(135deg, #17a2b8 0%, #6f42c1 100%); }
            
            /* Table Styles */
            table {
                width: 100%;
                border-collapse: collapse;
                margin-top: 20px;
                background: white;
                border-radius: 12px;
                overflow: hidden;
                box-shadow: 0 4px 15px rgba(0,0,0,0.08);
            }
            
            th, td {
                padding: 15px;
                text-align: left;
                border-bottom: 1px solid #e9ecef;
            }
            
            th {
                background-color: #f8f9fa;
                font-weight: 600;
                color: #495057;
                text-transform: uppercase;
                font-size: 12px;
                letter-spacing: 0.5px;
            }
            
            tr:hover {
                background-color: #f8f9fa;
            }
            
            .action-btn {
                padding: 6px 12px;
                margin: 2px;
                border: none;
                border-radius: 6px;
                cursor: pointer;
                font-size: 12px;
                font-weight: 500;
                transition: all 0.2s ease;
            }
            
            .action-btn:hover {
                transform: translateY(-1px);
            }
            
            /* Loading and Status Styles */
            .loading {
                display: inline-block;
                width: 20px;
                height: 20px;
                border: 3px solid #f3f3f3;
                border-top: 3px solid #007bff;
                border-radius: 50%;
                animation: spin 1s linear infinite;
            }
            
            @keyframes spin {
                0% { transform: rotate(0deg); }
                100% { transform: rotate(360deg); }
            }
            
            .result {
                margin: 20px 0;
                padding: 20px;
                border-radius: 12px;
                border: 1px solid;
            }
            
            .success {
                background-color: #d4edda;
                border-color: #c3e6cb;
                color: #155724;
            }
            
            .error {
                background-color: #f8d7da;
                border-color: #f5c6cb;
                color: #721c24;
            }
            
            .info {
                background-color: #d1ecf1;
                border-color: #bee5eb;
                color: #0c5460;
            }
            
            .warning {
                background-color: #fff3cd;
                border-color: #ffeaa7;
                color: #856404;
            }
            
            /* Responsive Design */
            @media (max-width: 768px) {
                .dashboard-grid {
                    grid-template-columns: 1fr;
                }
                
                .sync-controls {
                    grid-template-columns: 1fr;
                }
                
                .header {
                    flex-direction: column;
                    gap: 10px;
                    text-align: center;
                }
                
                .nav {
                    flex-wrap: wrap;
                    justify-content: center;
                }
                
                .page {
                    padding: 20px;
                }
            }
            
            /* File Tree Styles */
            .file-tree {
                border: 1px solid #e0e0e0;
                border-radius: 8px;
                overflow: hidden;
                background: white;
            }
            
            .tree-header {
                display: grid;
                grid-template-columns: 2fr 1fr 1fr 1.5fr 1fr;
                background: #f8f9fa;
                border-bottom: 1px solid #e0e0e0;
                font-weight: 600;
                color: #495057;
                padding: 12px 16px;
                font-size: 14px;
            }
            
            .tree-content {
                max-height: 600px;
                overflow-y: auto;
            }
            
            .tree-item {
                border-bottom: 1px solid #f0f0f0;
                transition: background-color 0.2s;
            }
            
            .tree-item:hover {
                background-color: #f8f9fa;
            }
            
            .tree-item.excluded {
                background-color: #fff5f5;
                opacity: 0.8;
            }
            
            .tree-item.excluded:hover {
                background-color: #ffe6e6;
            }
            
            .tree-row {
                display: grid;
                grid-template-columns: 2fr 1fr 1fr 1.5fr 1fr;
                padding: 8px 16px;
                align-items: center;
                font-size: 14px;
            }
            
            .tree-col-name {
                display: flex;
                align-items: center;
                gap: 8px;
            }
            
            .tree-toggle {
                cursor: pointer;
                user-select: none;
                font-size: 12px;
                color: #6c757d;
                transition: transform 0.2s;
                width: 16px;
                text-align: center;
            }
            
            .tree-toggle:hover {
                color: #495057;
            }
            
            .tree-spacer {
                width: 16px;
                display: inline-block;
            }
            
            .tree-icon {
                font-size: 16px;
            }
            
            .tree-name {
                font-weight: 500;
                color: #212529;
            }
            
            .tree-children {
                background-color: #fafbfc;
            }
            
            .exclude-status {
                padding: 2px 8px;
                border-radius: 12px;
                font-size: 12px;
                font-weight: 500;
            }
            
            .exclude-status.included {
                background-color: #d4edda;
                color: #155724;
            }
            
            .exclude-status.excluded {
                background-color: #f8d7da;
                color: #721c24;
            }
            
            @media (max-width: 768px) {
                .tree-header,
                .tree-row {
                    grid-template-columns: 1fr;
                    gap: 4px;
                }
                
                .tree-col-name {
                    font-weight: 600;
                }
                
                .tree-col-id::before {
                    content: "ID: ";
                    font-weight: 600;
                }
                
                .tree-col-status::before {
                    content: "Status: ";
                    font-weight: 600;
                }
                
                .tree-col-updated::before {
                    content: "Updated: ";
                    font-weight: 600;
                }
            }
        </style>
    </head>
    <body>
        <div class="container">
            <div class="header">
                <h1>Logikal Middleware - Admin Dashboard</h1>
                <div class="version">Version 1.0.0 | Environment: Production</div>
            </div>
            
            <div class="nav">
                <button onclick="showPage('dashboard')" class="active">Dashboard</button>
                <button onclick="showPage('sync-management')">Sync Management</button>
                <button onclick="showPage('connection')">Connection</button>
                <button onclick="showPage('directories')">Directories</button>
                <button onclick="showPage('projects')">Projects</button>
                <button onclick="showPage('phases')">Phases</button>
                <button onclick="showPage('elevations')">Elevations</button>
            </div>
            
            <!-- Dashboard Page (Phase 1) -->
            <div id="dashboard" class="page active">
                <h2>System Overview</h2>
                
                <!-- System Health Cards -->
                <div class="dashboard-grid">
                    <div class="card">
                        <div class="card-header">
                            <div class="card-title">System Health</div>
                            <span class="status-indicator status-success"></span>
                        </div>
                        <div class="metric-value" id="system-health">Healthy</div>
                        <div class="metric-label">Overall Status</div>
                        <div class="progress-bar">
                            <div class="progress-fill" style="width: 95%"></div>
                        </div>
                        <div style="font-size: 14px; color: #6c757d; margin-top: 10px;">
                            Database: <span class="status-success">●</span> Redis: <span class="status-success">●</span> Celery: <span class="status-success">●</span>
                        </div>
                    </div>
                    
                    <div class="card">
                        <div class="card-header">
                            <div class="card-title">Sync Statistics</div>
                            <span class="status-indicator status-info"></span>
                        </div>
                        <div class="metric-value" id="sync-count">1,247</div>
                        <div class="metric-label">Objects Synced Today</div>
                        <div style="font-size: 14px; color: #6c757d; margin-top: 10px;">
                            Success Rate: 98.5% | Avg Duration: 2.3s
                        </div>
                    </div>
                    
                    <div class="card">
                        <div class="card-header">
                            <div class="card-title">Data Consistency</div>
                            <span class="status-indicator status-warning"></span>
                        </div>
                        <div class="metric-value" id="consistency-score">87%</div>
                        <div class="metric-label">Overall Consistency Score</div>
                        <div class="progress-bar">
                            <div class="progress-fill" style="width: 87%; background: linear-gradient(90deg, #ffc107, #fd7e14);"></div>
                        </div>
                    </div>
                    
                    <div class="card">
                        <div class="card-header">
                            <div class="card-title">Active Alerts</div>
                            <span class="status-indicator status-warning"></span>
                        </div>
                        <div class="metric-value" id="alert-count">3</div>
                        <div class="metric-label">Active Alerts</div>
                        <div style="font-size: 14px; color: #6c757d; margin-top: 10px;">
                            Critical: 1 | Warning: 2 | Info: 0
                        </div>
                    </div>
                    
                    <div class="card">
                        <div class="card-header">
                            <div class="card-title">Performance Metrics</div>
                            <span class="status-indicator status-success"></span>
                        </div>
                        <div class="metric-value" id="api-requests">156</div>
                        <div class="metric-label">API Requests/min</div>
                        <div style="font-size: 14px; color: #6c757d; margin-top: 10px;">
                            Avg Response: 45ms | Error Rate: 0.2%
                        </div>
                    </div>
                    
                    <div class="card">
                        <div class="card-header">
                            <div class="card-title">Resource Usage</div>
                            <span class="status-indicator status-success"></span>
                        </div>
                        <div class="metric-value" id="cpu-usage">23%</div>
                        <div class="metric-label">CPU Usage</div>
                        <div class="progress-bar">
                            <div class="progress-fill" style="width: 23%; background: linear-gradient(90deg, #28a745, #20c997);"></div>
                        </div>
                        <div style="font-size: 14px; color: #6c757d; margin-top: 10px;">
                            Memory: 45% | Disk: 12%
                        </div>
                    </div>
                </div>
                
                <!-- Active Alerts Section -->
                <div class="card">
                    <div class="card-header">
                        <div class="card-title">Active Alerts</div>
                        <button onclick="refreshAlerts()" class="action-btn btn-info">Refresh</button>
                    </div>
                    <div class="alert-list" id="alerts-list">
                        <!-- Dynamic alerts will be loaded here -->
                    </div>
                </div>
                
                <!-- Recent Sync Operations -->
                <div class="card">
                    <div class="card-header">
                        <div class="card-title">Recent Sync Operations</div>
                        <button onclick="refreshSyncHistory()" class="action-btn btn-info">Refresh</button>
                    </div>
                    <table>
                        <thead>
                            <tr>
                                <th>Time</th>
                                <th>Operation</th>
                                <th>Objects</th>
                                <th>Duration</th>
                                <th>Status</th>
                                <th>Actions</th>
                            </tr>
                        </thead>
                        <tbody id="sync-history-table">
                            <!-- Dynamic content will be loaded here -->
                        </tbody>
                    </table>
                </div>
            </div>
            
            <!-- Sync Management Page (Phase 2) -->
            <div id="sync-management" class="page">
                <h2>Advanced Sync Management</h2>
                
                <!-- Smart Sync Controls -->
                <div class="sync-controls">
                    <div class="control-group">
                        <div class="control-title">Smart Sync Controls</div>
                        <div class="form-group">
                            <label>
                                <input type="checkbox" id="cascading-sync" checked> Enable Cascading Sync
                            </label>
                        </div>
                        <div class="form-group">
                            <label for="staleness-threshold">Staleness Threshold (hours):</label>
                            <input type="number" id="staleness-threshold" value="24" min="1" max="168">
                        </div>
                        <div class="form-group">
                            <label for="sync-priority">Default Sync Priority:</label>
                            <select id="sync-priority">
                                <option value="high">High</option>
                                <option value="medium" selected>Medium</option>
                                <option value="low">Low</option>
                            </select>
                        </div>
                        <button onclick="updateSmartSyncSettings()" class="btn-success">Update Settings</button>
                    </div>
                    
                    <div class="control-group">
                        <div class="control-title">Selective Sync Operations</div>
                        <div class="form-group">
                            <label for="sync-object-type">Object Type:</label>
                            <select id="sync-object-type">
                                <option value="all">All Objects</option>
                                <option value="projects">Projects Only</option>
                                <option value="phases">Phases Only</option>
                                <option value="elevations">Elevations Only</option>
                            </select>
                        </div>
                        <div class="form-group">
                            <label for="sync-date-range">Date Range:</label>
                            <select id="sync-date-range">
                                <option value="today">Today</option>
                                <option value="week">This Week</option>
                                <option value="month">This Month</option>
                                <option value="custom">Custom Range</option>
                            </select>
                        </div>
                        <button onclick="triggerSelectiveSync()" class="btn-warning">Start Selective Sync</button>
                        <button onclick="triggerFullSync()" class="btn-danger">Full System Sync</button>
                    </div>
                    
                    <div class="control-group">
                        <div class="control-title">Conflict Resolution</div>
                        <div class="form-group">
                            <label for="conflict-strategy">Resolution Strategy:</label>
                            <select id="conflict-strategy">
                                <option value="last-wins">Last Update Wins</option>
                                <option value="manual">Manual Resolution</option>
                                <option value="skip">Skip Conflicts</option>
                                <option value="merge">Smart Merge</option>
                            </select>
                        </div>
                        <div class="form-group">
                            <label>
                                <input type="checkbox" id="auto-conflict-resolution"> Enable Auto Resolution
                            </label>
                        </div>
                        <button onclick="updateConflictSettings()" class="btn-info">Update Settings</button>
                    </div>
                    
                    <div class="control-group">
                        <div class="control-title">Delta Sync Configuration</div>
                        <div class="form-group">
                            <label>
                                <input type="checkbox" id="delta-sync-enabled" checked> Enable Delta Sync
                            </label>
                        </div>
                        <div class="form-group">
                            <label for="change-sensitivity">Change Detection Sensitivity:</label>
                            <select id="change-sensitivity">
                                <option value="high">High (any change)</option>
                                <option value="medium" selected>Medium (significant changes)</option>
                                <option value="low">Low (major changes only)</option>
                            </select>
                        </div>
                        <div class="form-group">
                            <label for="batch-size">Batch Size:</label>
                            <input type="number" id="batch-size" value="100" min="10" max="1000">
                        </div>
                        <button onclick="updateDeltaSyncSettings()" class="btn-success">Update Settings</button>
                    </div>
                </div>
                
                <!-- Sync Status and Progress -->
                <div class="card">
                    <div class="card-header">
                        <div class="card-title">Current Sync Status</div>
                        <button onclick="refreshSyncStatus()" class="action-btn btn-info">Refresh</button>
                    </div>
                    <div id="sync-status-content">
                        <div style="display: grid; grid-template-columns: repeat(auto-fit, minmax(200px, 1fr)); gap: 20px;">
                            <div>
                                <div class="metric-label">Active Syncs</div>
                                <div class="metric-value" style="font-size: 24px;" id="active-syncs">0</div>
                            </div>
                            <div>
                                <div class="metric-label">Queue Size</div>
                                <div class="metric-value" style="font-size: 24px;" id="queue-size">12</div>
                            </div>
                            <div>
                                <div class="metric-label">Last Sync</div>
                                <div class="metric-value" style="font-size: 16px;" id="last-sync">2 minutes ago</div>
                            </div>
                            <div>
                                <div class="metric-label">Next Scheduled</div>
                                <div class="metric-value" style="font-size: 16px;" id="next-sync">58 minutes</div>
                            </div>
                        </div>
                        
                        <!-- Progress Bar for Active Sync -->
                        <div id="sync-progress-container" style="margin-top: 20px; display: none;">
                            <div style="display: flex; justify-content: space-between; margin-bottom: 10px;">
                                <span>Sync Progress</span>
                                <span id="sync-progress-text">0%</span>
                            </div>
                            <div class="progress-bar">
                                <div class="progress-fill" id="sync-progress-bar" style="width: 0%"></div>
                            </div>
                            <div id="sync-progress-details" style="font-size: 14px; color: #6c757d; margin-top: 10px;"></div>
                        </div>
                    </div>
                </div>
                
                <!-- Individual Object Sync -->
                <div class="card">
                    <div class="card-header">
                        <div class="card-title">Individual Object Sync</div>
                    </div>
                    <div style="display: grid; grid-template-columns: 1fr auto; gap: 15px; align-items: end;">
                        <div class="form-group">
                            <label for="object-id">Object ID:</label>
                            <input type="text" id="object-id" placeholder="Enter project, phase, or elevation ID">
                        </div>
                        <div>
                            <button onclick="syncIndividualObject()" class="btn-warning">Sync Object</button>
                        </div>
                    </div>
                    <div style="margin-top: 15px;">
                        <button onclick="syncAllProjects()" class="action-btn btn-success">Sync All Projects</button>
                        <button onclick="syncAllPhases()" class="action-btn btn-info">Sync All Phases</button>
                        <button onclick="syncAllElevations()" class="action-btn btn-info">Sync All Elevations</button>
                    </div>
                </div>
            </div>
            
            <!-- Connection Page -->
            <div id="connection" class="page">
                <h2>Connection Test</h2>
                <div class="form-group">
                    <label for="base_url">Base URL:</label>
                    <input type="text" id="base_url" value="https://logikal.api" placeholder="https://logikal.api">
                </div>
                <div class="form-group">
                    <label for="username">Username:</label>
                    <input type="text" id="username" placeholder="Your Logikal username">
                </div>
                <div class="form-group">
                    <label for="password">Password:</label>
                    <input type="password" id="password" placeholder="Your Logikal password">
                </div>
                <div class="form-group">
                    <button onclick="testConnection()">Test Connection</button>
                    <button onclick="authenticate()">Authenticate</button>
                    <button onclick="resetNavigation()" style="background-color: #ffc107; margin-left: 10px;">Reset Navigation</button>
                    <button onclick="clearSavedDetails()" style="background-color: #6c757d; margin-left: 10px;">Clear Saved Details</button>
                </div>
                <div id="connection_result"></div>
                
                <h2>Authentication</h2>
                <button onclick="authenticate()">Authenticate</button>
                <div id="auth_result"></div>
            </div>
            
            <!-- Directories Page -->
            <div id="directories" class="page">
                <h2>Cached Directories</h2>
                <div class="card">
                    <div class="card-header">
                        <div class="card-title">Directory Management</div>
                        <div>
                            <button onclick="refreshDirectories()" class="action-btn btn-info">Refresh</button>
                            <button onclick="syncDirectories()" class="action-btn btn-success">Sync from Logikal</button>
                            <button onclick="syncDirectoriesOptimized()" class="action-btn btn-warning">Optimized Sync</button>
                        </div>
                    </div>
                    <div id="directories-stats" style="display: grid; grid-template-columns: repeat(auto-fit, minmax(200px, 1fr)); gap: 20px; margin-bottom: 20px;">
                        <div>
                            <div class="metric-label">Total Directories</div>
                            <div class="metric-value" style="font-size: 24px;" id="directories-count">-</div>
                        </div>
                        <div>
                            <div class="metric-label">Last Updated</div>
                            <div class="metric-value" style="font-size: 16px;" id="directories-last-update">-</div>
                        </div>
                        <div>
                            <div class="metric-label">Sync Status</div>
                            <div class="metric-value" style="font-size: 16px;" id="directories-sync-status">-</div>
                        </div>
                </div>
                <div id="directories_result"></div>
                <div id="directories_table"></div>
                </div>
            </div>
            
            <!-- Projects Page -->
            <div id="projects" class="page">
                <h2>Cached Projects</h2>
                <div class="card">
                    <div class="card-header">
                        <div class="card-title">Project Management</div>
                        <div>
                            <button onclick="refreshProjects()" class="action-btn btn-info">Refresh</button>
                            <button onclick="syncProjects()" class="action-btn btn-success">Sync from Logikal</button>
                        </div>
                    </div>
                    <div id="projects-stats" style="display: grid; grid-template-columns: repeat(auto-fit, minmax(200px, 1fr)); gap: 20px; margin-bottom: 20px;">
                        <div>
                            <div class="metric-label">Total Projects</div>
                            <div class="metric-value" style="font-size: 24px;" id="projects-count">-</div>
                        </div>
                        <div>
                            <div class="metric-label">Last Updated</div>
                            <div class="metric-value" style="font-size: 16px;" id="projects-last-update">-</div>
                        </div>
                        <div>
                            <div class="metric-label">Stale Projects</div>
                            <div class="metric-value" style="font-size: 16px;" id="projects-stale-count">-</div>
                        </div>
                        <div>
                            <div class="metric-label">Sync Status</div>
                            <div class="metric-value" style="font-size: 16px;" id="projects-sync-status">-</div>
                        </div>
                    </div>
                <div id="projects_result"></div>
                <div id="projects_table"></div>
                </div>
            </div>
            
            <!-- Phases Page -->
            <div id="phases" class="page">
                <h2>Cached Phases</h2>
                <div class="card">
                    <div class="card-header">
                        <div class="card-title">Phase Management</div>
                        <div>
                            <button onclick="refreshPhases()" class="action-btn btn-info">Refresh</button>
                            <button onclick="syncPhases()" class="action-btn btn-success">Sync from Logikal</button>
                        </div>
                    </div>
                    <div id="phases-stats" style="display: grid; grid-template-columns: repeat(auto-fit, minmax(200px, 1fr)); gap: 20px; margin-bottom: 20px;">
                        <div>
                            <div class="metric-label">Total Phases</div>
                            <div class="metric-value" style="font-size: 24px;" id="phases-count">-</div>
                        </div>
                        <div>
                            <div class="metric-label">Last Updated</div>
                            <div class="metric-value" style="font-size: 16px;" id="phases-last-update">-</div>
                        </div>
                        <div>
                            <div class="metric-label">Stale Phases</div>
                            <div class="metric-value" style="font-size: 16px;" id="phases-stale-count">-</div>
                        </div>
                        <div>
                            <div class="metric-label">Sync Status</div>
                            <div class="metric-value" style="font-size: 16px;" id="phases-sync-status">-</div>
                        </div>
                    </div>
                <div id="phases_result"></div>
                <div id="phases_table"></div>
                </div>
            </div>
            
            <!-- Elevations Page -->
            <div id="elevations" class="page">
                <h2>Cached Elevations</h2>
                <div class="card">
                    <div class="card-header">
                        <div class="card-title">Elevation Management</div>
                        <div>
                            <button onclick="refreshElevations()" class="action-btn btn-info">Refresh</button>
                            <button onclick="syncElevations()" class="action-btn btn-success">Sync from Logikal</button>
                        </div>
                    </div>
                    <div id="elevations-stats" style="display: grid; grid-template-columns: repeat(auto-fit, minmax(200px, 1fr)); gap: 20px; margin-bottom: 20px;">
                        <div>
                            <div class="metric-label">Total Elevations</div>
                            <div class="metric-value" style="font-size: 24px;" id="elevations-count">-</div>
                        </div>
                        <div>
                            <div class="metric-label">Last Updated</div>
                            <div class="metric-value" style="font-size: 16px;" id="elevations-last-update">-</div>
                        </div>
                        <div>
                            <div class="metric-label">Stale Elevations</div>
                            <div class="metric-value" style="font-size: 16px;" id="elevations-stale-count">-</div>
                        </div>
                        <div>
                            <div class="metric-label">Sync Status</div>
                            <div class="metric-value" style="font-size: 16px;" id="elevations-sync-status">-</div>
                        </div>
                    </div>
                <div id="elevations_result"></div>
                <div id="elevations_table"></div>
                </div>
            </div>
            
            <!-- Sync Page -->
            <div id="sync" class="page">
                <h2>Sync Management</h2>
                
                <!-- Sync Controls -->
                <div class="sync-controls">
                    <button onclick="triggerFullSync()" style="background-color: #007bff;">Full Sync</button>
                    <button onclick="triggerIncrementalSync()" style="background-color: #28a745;">Incremental Sync</button>
                    <button onclick="getSyncStatus()" style="background-color: #6c757d;">Sync Status</button>
                </div>
                
                <!-- Sync Configuration -->
                <div class="sync-config">
                    <h3>Sync Configuration</h3>
                    <div class="form-group">
                        <label>
                            <input type="checkbox" id="auto_sync_enabled"> Enable Auto Sync
                        </label>
                    </div>
                    <div class="form-group">
                        <label for="sync_interval">Sync Interval (minutes):</label>
                        <input type="number" id="sync_interval" value="60" min="1" max="1440">
                    </div>
                </div>
                
                <!-- Sync Status -->
                <div id="sync_status"></div>
                
                <!-- Sync Logs -->
                <div id="sync_logs"></div>
            </div>
        </div>
        
        <script>
            let authToken = null;
            let currentDirectory = null;
            let currentProject = null;
            let currentPhase = null;
            
            // Load saved connection details on page load
            document.addEventListener('DOMContentLoaded', function() {
                loadSavedConnectionDetails();
            });
            
            function showPage(pageName) {
                // Hide all pages
                document.querySelectorAll('.page').forEach(page => {
                    page.classList.remove('active');
                });
                
                // Remove active class from all nav buttons
                document.querySelectorAll('.nav button').forEach(btn => {
                    btn.classList.remove('active');
                });
                
                // Show selected page
                document.getElementById(pageName).classList.add('active');
                
                // Add active class to clicked button
                event.target.classList.add('active');
            }
            
            function loadSavedConnectionDetails() {
                const savedBaseUrl = localStorage.getItem('logikal_base_url');
                const savedUsername = localStorage.getItem('logikal_username');
                const savedPassword = localStorage.getItem('logikal_password');
                
                if (savedBaseUrl) document.getElementById('base_url').value = savedBaseUrl;
                if (savedUsername) document.getElementById('username').value = savedUsername;
                if (savedPassword) document.getElementById('password').value = savedPassword;
                
                // Show indicator if details were loaded
                if (savedBaseUrl || savedUsername || savedPassword) {
                    const resultDiv = document.getElementById('connection_result');
                    resultDiv.className = 'result info';
                    resultDiv.innerHTML = '<strong>Info:</strong> Connection details loaded from saved settings.';
                }
            }
            
            function saveConnectionDetails(baseUrl, username, password) {
                localStorage.setItem('logikal_base_url', baseUrl);
                localStorage.setItem('logikal_username', username);
                localStorage.setItem('logikal_password', password);
            }
            
            function clearSavedDetails() {
                localStorage.removeItem('logikal_base_url');
                localStorage.removeItem('logikal_username');
                localStorage.removeItem('logikal_password');
                
                // Clear the form fields
                document.getElementById('base_url').value = '';
                document.getElementById('username').value = '';
                document.getElementById('password').value = '';
                
                // Show confirmation
                const resultDiv = document.getElementById('connection_result');
                resultDiv.className = 'result info';
                resultDiv.innerHTML = '<strong>Info:</strong> Saved connection details have been cleared.';
            }
            
            async function resetNavigation() {
                const baseUrl = document.getElementById('base_url').value;
                const username = document.getElementById('username').value;
                const password = document.getElementById('password').value;
                
                if (!baseUrl || !username || !password) {
                    alert('Please fill in all connection details first');
                    return;
                }
                
                try {
                    const response = await fetch(`/api/v1/auth/reset-navigation?base_url=${encodeURIComponent(baseUrl)}&username=${encodeURIComponent(username)}&password=${encodeURIComponent(password)}`, {
                        method: 'POST'
                    });
                    const result = await response.json();
                    
                    if (response.ok) {
                        // Clear current state
                        authToken = null;
                        currentDirectory = null;
                        currentProject = null;
                        currentPhase = null;
                        
                        // Get new token from the response
                        authToken = result.token || null;
                        
                        alert('Navigation reset successfully! You can now navigate to any directory.');
                    } else {
                        alert(`Error resetting navigation: ${result.detail?.message || 'Unknown error'}`);
                    }
                } catch (error) {
                    alert(`Error resetting navigation: ${error.message}`);
                }
            }
            
            async function testConnection() {
                const baseUrl = document.getElementById('base_url').value;
                const username = document.getElementById('username').value;
                const password = document.getElementById('password').value;
                
                // Save connection details
                saveConnectionDetails(baseUrl, username, password);
                
                try {
                    const response = await fetch(`/api/v1/auth/test?base_url=${encodeURIComponent(baseUrl)}&username=${encodeURIComponent(username)}&password=${encodeURIComponent(password)}`);
                    const result = await response.json();
                    
                    const resultDiv = document.getElementById('connection_result');
                    resultDiv.className = 'result ' + (result.success ? 'success' : 'error');
                    resultDiv.innerHTML = `<strong>Connection Test:</strong> ${result.message}<br><small>Connection details have been saved.</small>`;
                } catch (error) {
                    const resultDiv = document.getElementById('connection_result');
                    resultDiv.className = 'result error';
                    resultDiv.innerHTML = `<strong>Connection Test Error:</strong> ${error.message}`;
                }
            }
            
            async function authenticate() {
                const baseUrl = document.getElementById('base_url').value;
                const username = document.getElementById('username').value;
                const password = document.getElementById('password').value;
                
                // Save connection details
                saveConnectionDetails(baseUrl, username, password);
                
                try {
                    const response = await fetch('/api/v1/auth/login', {
                        method: 'POST',
                        headers: {
                            'Content-Type': 'application/json',
                        },
                        body: JSON.stringify({
                            base_url: baseUrl,
                            username: username,
                            password: password
                        })
                    });
                    
                    const result = await response.json();
                    
                    const resultDiv = document.getElementById('auth_result');
                    if (response.ok) {
                        authToken = result.token;
                        resultDiv.className = 'result success';
                        resultDiv.innerHTML = `<strong>Authentication:</strong> ${result.message}<br><strong>Token:</strong> ${result.token.substring(0, 20)}...<br><small>Connection details have been saved.</small>`;
                    } else {
                        resultDiv.className = 'result error';
                        resultDiv.innerHTML = `<strong>Authentication Error:</strong> ${result.detail?.message || 'Unknown error'}`;
                    }
                } catch (error) {
                    const resultDiv = document.getElementById('auth_result');
                    resultDiv.className = 'result error';
                    resultDiv.innerHTML = `<strong>Authentication Error:</strong> ${error.message}`;
                }
            }
            
            async function refreshDirectories() {
                try {
                    const response = await fetch('/api/v1/directories/cached');
                    const result = await response.json();
                    
                    const resultDiv = document.getElementById('directories_result');
                    const tableDiv = document.getElementById('directories_table');
                    
                    if (response.ok) {
                        // Update stats
                        document.getElementById('directories-count').textContent = result.count || 0;
                        document.getElementById('directories-last-update').textContent = result.last_updated || 'Never';
                        document.getElementById('directories-sync-status').textContent = result.sync_status || 'Unknown';
                        
                        resultDiv.className = 'result success';
                        resultDiv.innerHTML = `<strong>Cached Directories (${result.count || 0}):</strong>`;
                        
                        if (result.data && result.data.length > 0) {
                        // Create hierarchical tree structure
                        let treeHtml = `
                            <div class="file-tree">
                                <div class="tree-header">
                                    <div class="tree-col-name">Directory Structure</div>
                                    <div class="tree-col-id">ID</div>
                                    <div class="tree-col-status">Sync Status</div>
                                    <div class="tree-col-updated">Last Updated</div>
                                    <div class="tree-col-actions">Actions</div>
                                </div>
                                <div class="tree-content">
                        `;
                        
                        // Build hierarchical structure
                        const directoryMap = new Map();
                        const rootDirectories = [];
                        
                        // First pass: create directory objects and map
                        result.data.forEach(dir => {
                            directoryMap.set(dir.id, {
                                ...dir,
                                children: [],
                                expanded: false
                            });
                        });
                        
                        // Second pass: build parent-child relationships
                        result.data.forEach(dir => {
                            const dirObj = directoryMap.get(dir.id);
                            if (dir.parent_id && directoryMap.has(dir.parent_id)) {
                                directoryMap.get(dir.parent_id).children.push(dirObj);
                            } else {
                                rootDirectories.push(dirObj);
                            }
                        });
                        
                        // Sort directories by name for consistent display
                        const sortDirectories = (dirs) => {
                            dirs.sort((a, b) => a.name.localeCompare(b.name));
                            dirs.forEach(dir => {
                                if (dir.children.length > 0) {
                                    sortDirectories(dir.children);
                                }
                            });
                        };
                        
                        sortDirectories(rootDirectories);
                        
                        // Render tree recursively
                        const renderDirectory = (dir, level = 0) => {
                            const excludedClass = dir.exclude_from_sync ? 'excluded' : 'included';
                            const excludedStatus = dir.exclude_from_sync ? 'Excluded' : 'Included';
                            const toggleText = dir.exclude_from_sync ? 'Include' : 'Exclude';
                            const toggleColor = dir.exclude_from_sync ? '#28a745' : '#ffc107';
                            const lastUpdated = dir.synced_at ? new Date(dir.synced_at).toLocaleString() : 'Never';
                            const hasChildren = dir.children.length > 0;
                            const indent = level * 20;
                            
                            let html = `
                                <div class="tree-item ${excludedClass}" style="padding-left: ${indent}px;">
                                    <div class="tree-row">
                                        <div class="tree-col-name">
                                            ${hasChildren ? 
                                                `<span class="tree-toggle" onclick="toggleDirectory('${dir.id}')" id="toggle-${dir.id}">▶</span>` : 
                                                '<span class="tree-spacer"></span>'
                                            }
                                            <span class="tree-icon">📁</span>
                                            <span class="tree-name">${dir.name}</span>
                                        </div>
                                        <div class="tree-col-id">${dir.logikal_id || dir.id}</div>
                                        <div class="tree-col-status">
                                            <span class="exclude-status ${excludedClass}">${excludedStatus}</span>
                                        </div>
                                        <div class="tree-col-updated">${lastUpdated}</div>
                                        <div class="tree-col-actions">
                                            <button class="action-btn" onclick="toggleDirectoryExclusion('${dir.id}', ${!dir.exclude_from_sync})" 
                                                    style="background-color: ${toggleColor}; color: white; font-size: 12px; padding: 4px 8px;">
                                                ${toggleText}
                                            </button>
                                        </div>
                                    </div>
                                </div>
                            `;
                            
                            // Add children (initially hidden)
                            if (hasChildren) {
                                html += `<div class="tree-children" id="children-${dir.id}" style="display: none;">`;
                                dir.children.forEach(child => {
                                    html += renderDirectory(child, level + 1);
                                });
                                html += '</div>';
                            }
                            
                            return html;
                        };
                        
                        // Render all root directories
                        rootDirectories.forEach(dir => {
                            treeHtml += renderDirectory(dir);
                        });
                        
                        treeHtml += `
                                </div>
                            </div>
                        `;
                        
                        tableDiv.innerHTML = treeHtml;
                        } else {
                            tableDiv.innerHTML = '<div class="result info">No directories found in cache. Try syncing from Logikal first.</div>';
                        }
                        
                    } else {
                        resultDiv.className = 'result error';
                        resultDiv.innerHTML = `<strong>Error:</strong> ${result.detail?.message || 'Unknown error'}`;
                        tableDiv.innerHTML = '';
                    }
                } catch (error) {
                    const resultDiv = document.getElementById('directories_result');
                    resultDiv.className = 'result error';
                    resultDiv.innerHTML = `<strong>Error:</strong> ${error.message}`;
                    document.getElementById('directories_table').innerHTML = '';
                }
            }
            
            async function syncDirectories() {
                try {
                    showNotification('Starting directory sync from Logikal...', 'info');
                    const response = await fetch('/api/v1/sync/directories', {
                        method: 'POST'
                    });
                    const result = await response.json();
                    
                    if (response.ok) {
                        showNotification('Directory sync completed successfully!', 'success');
                        refreshDirectories();
                    } else {
                        showNotification(`Directory sync failed: ${result.detail}`, 'error');
                    }
                } catch (error) {
                    showNotification(`Directory sync error: ${error.message}`, 'error');
                }
            }
            
            async function syncDirectoriesOptimized() {
                try {
                    showNotification('Starting optimized directory sync with batch operations...', 'info');
                    const response = await fetch('/api/v1/sync/directories/optimized', {
                        method: 'POST'
                    });
                    const result = await response.json();
                    
                    if (response.ok) {
                        const duration = result.duration_seconds || 0;
                        showNotification(`Optimized directory sync completed in ${duration}s! Processed ${result.directories_processed || 0} directories.`, 'success');
                        refreshDirectories();
                    } else {
                        showNotification(`Optimized directory sync failed: ${result.detail}`, 'error');
                    }
                } catch (error) {
                    showNotification(`Optimized directory sync error: ${error.message}`, 'error');
                }
            }
            
            // Projects Functions
            async function refreshProjects() {
                try {
                    const response = await fetch('/api/v1/projects/cached');
                    const result = await response.json();
                    
                    const resultDiv = document.getElementById('projects_result');
                    const tableDiv = document.getElementById('projects_table');
                    
                    if (response.ok) {
                        // Update stats
                        document.getElementById('projects-count').textContent = result.count || 0;
                        document.getElementById('projects-last-update').textContent = result.last_updated || 'Never';
                        document.getElementById('projects-stale-count').textContent = result.stale_count || 0;
                        document.getElementById('projects-sync-status').textContent = result.sync_status || 'Unknown';
                        
                        resultDiv.className = 'result success';
                        resultDiv.innerHTML = `<strong>Cached Projects (${result.count || 0}):</strong>`;
                        
                        if (result.projects && result.projects.length > 0) {
                            let tableHtml = `
                                <table>
                                    <thead>
                                        <tr>
                                            <th>Name</th>
                                            <th>ID</th>
                                            <th>Directory</th>
                                            <th>Status</th>
                                            <th>Last Updated</th>
                                            <th>Actions</th>
                                        </tr>
                                    </thead>
                                    <tbody>
                            `;
                            
                            result.projects.forEach(project => {
                                const lastUpdated = project.last_sync_date ? new Date(project.last_sync_date).toLocaleString() : 'Never';
                                const isStale = project.is_stale ? 'Stale' : 'Fresh';
                                const staleClass = project.is_stale ? 'warning' : 'success';
                                
                                tableHtml += `
                                    <tr>
                                        <td>${project.name}</td>
                                        <td>${project.logikal_id || project.id}</td>
                                        <td>${project.directory_name || 'N/A'}</td>
                                        <td><span class="status-indicator status-${staleClass}"></span>${isStale}</td>
                                        <td>${lastUpdated}</td>
                                        <td>
                                            <button class="action-btn btn-info" onclick="syncProject('${project.id}')">Sync</button>
                                        </td>
                                    </tr>
                                `;
                            });
                            
                            tableHtml += '</tbody></table>';
                            tableDiv.innerHTML = tableHtml;
                        } else {
                            tableDiv.innerHTML = '<div class="result info">No projects found in cache. Try syncing from Logikal first.</div>';
                        }
                    } else {
                        resultDiv.className = 'result error';
                        resultDiv.innerHTML = `<strong>Error:</strong> ${result.detail?.message || 'Unknown error'}`;
                        tableDiv.innerHTML = '';
                    }
                } catch (error) {
                    const resultDiv = document.getElementById('projects_result');
                    resultDiv.className = 'result error';
                    resultDiv.innerHTML = `<strong>Error:</strong> ${error.message}`;
                    document.getElementById('projects_table').innerHTML = '';
                }
            }
            
            async function syncProjects() {
                try {
                    showNotification('Starting project sync from Logikal...', 'info');
                    const response = await fetch('/api/v1/sync/projects', {
                        method: 'POST'
                    });
                    const result = await response.json();
                    
                    if (response.ok) {
                        showNotification('Project sync completed successfully!', 'success');
                        refreshProjects();
                    } else {
                        showNotification(`Project sync failed: ${result.detail}`, 'error');
                    }
                } catch (error) {
                    showNotification(`Project sync error: ${error.message}`, 'error');
                }
            }
            
            async function syncProject(projectId) {
                try {
                    showNotification(`Syncing project ${projectId}...`, 'info');
                    const response = await fetch(`/api/v1/advanced-sync/object`, {
                        method: 'POST',
                        headers: {
                            'Content-Type': 'application/json',
                        },
                        body: JSON.stringify({
                            object_id: projectId,
                            object_type: 'project',
                            priority: 'high'
                        })
                    });
                    const result = await response.json();
                    
                    if (response.ok) {
                        showNotification(`Project ${projectId} synced successfully!`, 'success');
                        refreshProjects();
                    } else {
                        showNotification(`Project sync failed: ${result.detail}`, 'error');
                    }
                } catch (error) {
                    showNotification(`Project sync error: ${error.message}`, 'error');
                }
            }
            
            // Phases Functions
            async function refreshPhases() {
                try {
                    const response = await fetch('/api/v1/phases/cached');
                    const result = await response.json();
                    
                    const resultDiv = document.getElementById('phases_result');
                    const tableDiv = document.getElementById('phases_table');
                    
                    if (response.ok) {
                        // Update stats
                        document.getElementById('phases-count').textContent = result.count || 0;
                        document.getElementById('phases-last-update').textContent = result.last_updated || 'Never';
                        document.getElementById('phases-stale-count').textContent = result.stale_count || 0;
                        document.getElementById('phases-sync-status').textContent = result.sync_status || 'Unknown';
                        
                        resultDiv.className = 'result success';
                        resultDiv.innerHTML = `<strong>Cached Phases (${result.count || 0}):</strong>`;
                        
                        if (result.phases && result.phases.length > 0) {
                            let tableHtml = `
                                <table>
                                    <thead>
                                        <tr>
                                            <th>Name</th>
                                            <th>ID</th>
                                            <th>Project</th>
                                            <th>Status</th>
                                            <th>Last Updated</th>
                                            <th>Actions</th>
                                        </tr>
                                    </thead>
                                    <tbody>
                            `;
                            
                            result.phases.forEach(phase => {
                                const lastUpdated = phase.last_sync_date ? new Date(phase.last_sync_date).toLocaleString() : 'Never';
                                const isStale = phase.is_stale ? 'Stale' : 'Fresh';
                                const staleClass = phase.is_stale ? 'warning' : 'success';
                                
                                tableHtml += `
                                    <tr>
                                        <td>${phase.name}</td>
                                        <td>${phase.logikal_id || phase.id}</td>
                                        <td>${phase.project_name || 'N/A'}</td>
                                        <td><span class="status-indicator status-${staleClass}"></span>${isStale}</td>
                                        <td>${lastUpdated}</td>
                                        <td>
                                            <button class="action-btn btn-info" onclick="syncPhase('${phase.id}')">Sync</button>
                                        </td>
                                    </tr>
                                `;
                            });
                            
                            tableHtml += '</tbody></table>';
                            tableDiv.innerHTML = tableHtml;
                        } else {
                            tableDiv.innerHTML = '<div class="result info">No phases found in cache. Try syncing from Logikal first.</div>';
                        }
                    } else {
                        resultDiv.className = 'result error';
                        resultDiv.innerHTML = `<strong>Error:</strong> ${result.detail?.message || 'Unknown error'}`;
                        tableDiv.innerHTML = '';
                    }
                } catch (error) {
                    const resultDiv = document.getElementById('phases_result');
                    resultDiv.className = 'result error';
                    resultDiv.innerHTML = `<strong>Error:</strong> ${error.message}`;
                    document.getElementById('phases_table').innerHTML = '';
                }
            }
            
            async function syncPhases() {
                try {
                    showNotification('Starting phase sync from Logikal...', 'info');
                    const response = await fetch('/api/v1/sync/phases', {
                        method: 'POST'
                    });
                    const result = await response.json();
                    
                    if (response.ok) {
                        showNotification('Phase sync completed successfully!', 'success');
                        refreshPhases();
                    } else {
                        showNotification(`Phase sync failed: ${result.detail}`, 'error');
                    }
                } catch (error) {
                    showNotification(`Phase sync error: ${error.message}`, 'error');
                }
            }
            
            async function syncPhase(phaseId) {
                try {
                    showNotification(`Syncing phase ${phaseId}...`, 'info');
                    const response = await fetch(`/api/v1/advanced-sync/object`, {
                        method: 'POST',
                        headers: {
                            'Content-Type': 'application/json',
                        },
                        body: JSON.stringify({
                            object_id: phaseId,
                            object_type: 'phase',
                            priority: 'high'
                        })
                    });
                    const result = await response.json();
                    
                    if (response.ok) {
                        showNotification(`Phase ${phaseId} synced successfully!`, 'success');
                        refreshPhases();
                    } else {
                        showNotification(`Phase sync failed: ${result.detail}`, 'error');
                    }
                } catch (error) {
                    showNotification(`Phase sync error: ${error.message}`, 'error');
                }
            }
            
            // Elevations Functions
            async function refreshElevations() {
                try {
                    const response = await fetch('/api/v1/elevations/cached');
                    const result = await response.json();
                    
                    const resultDiv = document.getElementById('elevations_result');
                    const tableDiv = document.getElementById('elevations_table');
                    
                    if (response.ok) {
                        // Update stats
                        document.getElementById('elevations-count').textContent = result.count || 0;
                        document.getElementById('elevations-last-update').textContent = result.last_updated || 'Never';
                        document.getElementById('elevations-stale-count').textContent = result.stale_count || 0;
                        document.getElementById('elevations-sync-status').textContent = result.sync_status || 'Unknown';
                        
                        resultDiv.className = 'result success';
                        resultDiv.innerHTML = `<strong>Cached Elevations (${result.count || 0}):</strong>`;
                        
                        if (result.elevations && result.elevations.length > 0) {
                            let tableHtml = `
                                <table>
                                    <thead>
                                        <tr>
                                            <th>Name</th>
                                            <th>ID</th>
                                            <th>Phase</th>
                                            <th>Status</th>
                                            <th>Last Updated</th>
                                            <th>Actions</th>
                                        </tr>
                                    </thead>
                                    <tbody>
                            `;
                            
                            result.elevations.forEach(elevation => {
                                const lastUpdated = elevation.last_sync_date ? new Date(elevation.last_sync_date).toLocaleString() : 'Never';
                                const isStale = elevation.is_stale ? 'Stale' : 'Fresh';
                                const staleClass = elevation.is_stale ? 'warning' : 'success';
                                
                                tableHtml += `
                                    <tr>
                                        <td>${elevation.name}</td>
                                        <td>${elevation.logikal_id || elevation.id}</td>
                                        <td>${elevation.phase_name || 'N/A'}</td>
                                        <td><span class="status-indicator status-${staleClass}"></span>${isStale}</td>
                                        <td>${lastUpdated}</td>
                                        <td>
                                            <button class="action-btn btn-info" onclick="syncElevation('${elevation.id}')">Sync</button>
                                        </td>
                                    </tr>
                                `;
                            });
                            
                            tableHtml += '</tbody></table>';
                            tableDiv.innerHTML = tableHtml;
                        } else {
                            tableDiv.innerHTML = '<div class="result info">No elevations found in cache. Try syncing from Logikal first.</div>';
                        }
                    } else {
                        resultDiv.className = 'result error';
                        resultDiv.innerHTML = `<strong>Error:</strong> ${result.detail?.message || 'Unknown error'}`;
                        tableDiv.innerHTML = '';
                    }
                } catch (error) {
                    const resultDiv = document.getElementById('elevations_result');
                    resultDiv.className = 'result error';
                    resultDiv.innerHTML = `<strong>Error:</strong> ${error.message}`;
                    document.getElementById('elevations_table').innerHTML = '';
                }
            }
            
            async function syncElevations() {
                try {
                    showNotification('Starting elevation sync from Logikal...', 'info');
                    const response = await fetch('/api/v1/sync/elevations', {
                        method: 'POST'
                    });
                    const result = await response.json();
                    
                    if (response.ok) {
                        showNotification('Elevation sync completed successfully!', 'success');
                        refreshElevations();
                    } else {
                        showNotification(`Elevation sync failed: ${result.detail}`, 'error');
                    }
                } catch (error) {
                    showNotification(`Elevation sync error: ${error.message}`, 'error');
                }
            }
            
            async function syncElevation(elevationId) {
                try {
                    showNotification(`Syncing elevation ${elevationId}...`, 'info');
                    const response = await fetch(`/api/v1/advanced-sync/object`, {
                        method: 'POST',
                        headers: {
                            'Content-Type': 'application/json',
                        },
                        body: JSON.stringify({
                            object_id: elevationId,
                            object_type: 'elevation',
                            priority: 'high'
                        })
                    });
                    const result = await response.json();
                    
                    if (response.ok) {
                        showNotification(`Elevation ${elevationId} synced successfully!`, 'success');
                        refreshElevations();
                    } else {
                        showNotification(`Elevation sync failed: ${result.detail}`, 'error');
                    }
                } catch (error) {
                    showNotification(`Elevation sync error: ${error.message}`, 'error');
                }
            }
            
            async function selectDirectory(directoryId) {
                if (!authToken) {
                    alert('Please authenticate first');
                    return;
                }
                
                const baseUrl = document.getElementById('base_url').value;
                
                try {
                    const response = await fetch(`/api/v1/directories/${directoryId}/select?token=${encodeURIComponent(authToken)}&base_url=${encodeURIComponent(baseUrl)}`, {
                        method: 'POST'
                    });
                    const result = await response.json();
                    
                    if (response.ok) {
                        currentDirectory = directoryId;
                        alert(`Directory "${directoryId}" selected successfully!`);
                    } else {
                        alert(`Error selecting directory: ${result.detail?.message || 'Unknown error'}`);
                    }
                } catch (error) {
                    alert(`Error selecting directory: ${error.message}`);
                }
            }
            
            async function getProjects() {
                if (!authToken) {
                    const resultDiv = document.getElementById('projects_result');
                    resultDiv.className = 'result error';
                    resultDiv.innerHTML = '<strong>Error:</strong> Please authenticate first';
                    return;
                }
                
                const baseUrl = document.getElementById('base_url').value;
                
                try {
                    const response = await fetch(`/api/v1/projects/?token=${encodeURIComponent(authToken)}&base_url=${encodeURIComponent(baseUrl)}`);
                    const result = await response.json();
                    
                    const resultDiv = document.getElementById('projects_result');
                    const tableDiv = document.getElementById('projects_table');
                    
                    if (response.ok) {
                        resultDiv.className = 'result success';
                        resultDiv.innerHTML = `<strong>Projects (${result.count}):</strong>`;
                        
                        // Create table
                        let tableHtml = `
                            <table>
                                <thead>
                                    <tr>
                                        <th>Name</th>
                                        <th>ID</th>
                                        <th>Description</th>
                                        <th>Status</th>
                                        <th>Created</th>
                                        <th>Actions</th>
                                    </tr>
                                </thead>
                                <tbody>
                        `;
                        
                        result.data.forEach(project => {
                            tableHtml += `
                                <tr>
                                    <td>${project.name}</td>
                                    <td>${project.logikal_id}</td>
                                    <td>${project.description || 'N/A'}</td>
                                    <td>${project.status || 'N/A'}</td>
                                    <td>${new Date(project.created_at).toLocaleDateString()}</td>
                                    <td>
                                        <button class="action-btn" onclick="selectProject('${project.logikal_id}')">Select</button>
                                    </td>
                                </tr>
                            `;
                        });
                        
                        tableHtml += '</tbody></table>';
                        tableDiv.innerHTML = tableHtml;
                    } else {
                        resultDiv.className = 'result error';
                        resultDiv.innerHTML = `<strong>Error:</strong> ${result.detail?.message || 'Unknown error'}`;
                        tableDiv.innerHTML = '';
                    }
                } catch (error) {
                    const resultDiv = document.getElementById('projects_result');
                    resultDiv.className = 'result error';
                    resultDiv.innerHTML = `<strong>Error:</strong> ${error.message}`;
                    document.getElementById('projects_table').innerHTML = '';
                }
            }
            
            async function selectProject(projectId) {
                if (!authToken) {
                    alert('Please authenticate first');
                    return;
                }
                
                const baseUrl = document.getElementById('base_url').value;
                
                try {
                    const response = await fetch(`/api/v1/projects/${projectId}/select?token=${encodeURIComponent(authToken)}&base_url=${encodeURIComponent(baseUrl)}`, {
                        method: 'POST'
                    });
                    const result = await response.json();
                    
                    if (response.ok) {
                        currentProject = projectId;
                        alert(`Project "${projectId}" selected successfully!`);
                    } else {
                        alert(`Error selecting project: ${result.detail?.message || 'Unknown error'}`);
                    }
                } catch (error) {
                    alert(`Error selecting project: ${error.message}`);
                }
            }
            
            async function getPhases() {
                if (!authToken) {
                    const resultDiv = document.getElementById('phases_result');
                    resultDiv.className = 'result error';
                    resultDiv.innerHTML = '<strong>Error:</strong> Please authenticate first';
                    return;
                }
                
                const baseUrl = document.getElementById('base_url').value;
                
                try {
                    const response = await fetch(`/api/v1/phases/?token=${encodeURIComponent(authToken)}&base_url=${encodeURIComponent(baseUrl)}`);
                    const result = await response.json();
                    
                    const resultDiv = document.getElementById('phases_result');
                    const tableDiv = document.getElementById('phases_table');
                    
                    if (response.ok) {
                        resultDiv.className = 'result success';
                        resultDiv.innerHTML = `<strong>Phases (${result.count}):</strong>`;
                        
                        // Create table
                        let tableHtml = `
                            <table>
                                <thead>
                                    <tr>
                                        <th>Name</th>
                                        <th>ID</th>
                                        <th>Description</th>
                                        <th>Status</th>
                                        <th>Created</th>
                                        <th>Actions</th>
                                    </tr>
                                </thead>
                                <tbody>
                        `;
                        
                        result.data.forEach(phase => {
                            tableHtml += `
                                <tr>
                                    <td>${phase.name}</td>
                                    <td>${phase.logikal_id}</td>
                                    <td>${phase.description || 'N/A'}</td>
                                    <td>${phase.status || 'N/A'}</td>
                                    <td>${new Date(phase.created_at).toLocaleDateString()}</td>
                                    <td>
                                        <button class="action-btn" onclick="selectPhase('${phase.logikal_id}')">Select</button>
                                    </td>
                                </tr>
                            `;
                        });
                        
                        tableHtml += '</tbody></table>';
                        tableDiv.innerHTML = tableHtml;
                    } else {
                        resultDiv.className = 'result error';
                        resultDiv.innerHTML = `<strong>Error:</strong> ${result.detail?.message || 'Unknown error'}`;
                        tableDiv.innerHTML = '';
                    }
                } catch (error) {
                    const resultDiv = document.getElementById('phases_result');
                    resultDiv.className = 'result error';
                    resultDiv.innerHTML = `<strong>Error:</strong> ${error.message}`;
                    document.getElementById('phases_table').innerHTML = '';
                }
            }
            
            async function selectPhase(phaseId) {
                if (!authToken) {
                    alert('Please authenticate first');
                    return;
                }
                
                const baseUrl = document.getElementById('base_url').value;
                
                try {
                    const response = await fetch(`/api/v1/phases/${phaseId}/select?token=${encodeURIComponent(authToken)}&base_url=${encodeURIComponent(baseUrl)}`, {
                        method: 'POST'
                    });
                    const result = await response.json();
                    
                    if (response.ok) {
                        currentPhase = phaseId;
                        alert(`Phase "${phaseId}" selected successfully! You can now get elevations.`);
                    } else {
                        alert(`Error selecting phase: ${result.detail?.message || 'Unknown error'}`);
                    }
                } catch (error) {
                    alert(`Error selecting phase: ${error.message}`);
                }
            }
            
            async function getElevations() {
                if (!authToken) {
                    const resultDiv = document.getElementById('elevations_result');
                    resultDiv.className = 'result error';
                    resultDiv.innerHTML = '<strong>Error:</strong> Please authenticate first';
                    return;
                }
                
                if (!currentPhase) {
                    const resultDiv = document.getElementById('elevations_result');
                    resultDiv.className = 'result error';
                    resultDiv.innerHTML = '<strong>Error:</strong> Please select a phase first. Go to the Phases page and select a phase.';
                    return;
                }
                
                const baseUrl = document.getElementById('base_url').value;
                
                try {
                    const response = await fetch(`/api/v1/elevations/?token=${encodeURIComponent(authToken)}&base_url=${encodeURIComponent(baseUrl)}`);
                    const result = await response.json();
                    
                    const resultDiv = document.getElementById('elevations_result');
                    const tableDiv = document.getElementById('elevations_table');
                    
                    if (response.ok) {
                        resultDiv.className = 'result success';
                        resultDiv.innerHTML = `<strong>Elevations (${result.count}):</strong>`;
                        
                        // Create table
                        let tableHtml = `
                            <table>
                                <thead>
                                    <tr>
                                        <th>Name</th>
                                        <th>ID</th>
                                        <th>Description</th>
                                        <th>Phase ID</th>
                                        <th>Dimensions</th>
                                        <th>Created</th>
                                        <th>Actions</th>
                                    </tr>
                                </thead>
                                <tbody>
                        `;
                        
                        result.data.forEach(elevation => {
                            const dimensions = [];
                            if (elevation.width) dimensions.push(`W: ${elevation.width}`);
                            if (elevation.height) dimensions.push(`H: ${elevation.height}`);
                            if (elevation.depth) dimensions.push(`D: ${elevation.depth}`);
                            
                            tableHtml += `
                                <tr>
                                    <td>${elevation.name}</td>
                                    <td>${elevation.logikal_id}</td>
                                    <td>${elevation.description || 'N/A'}</td>
                                    <td>${elevation.phase_id || 'N/A'}</td>
                                    <td>${dimensions.join(', ') || 'N/A'}</td>
                                    <td>${new Date(elevation.created_at).toLocaleDateString()}</td>
                                    <td>
                                        <button class="action-btn" onclick="getThumbnail('${elevation.logikal_id}')">Thumbnail</button>
                                    </td>
                                </tr>
                            `;
                        });
                        
                        tableHtml += '</tbody></table>';
                        tableDiv.innerHTML = tableHtml;
                    } else {
                        resultDiv.className = 'result error';
                        resultDiv.innerHTML = `<strong>Error:</strong> ${result.detail?.message || 'Unknown error'}`;
                        tableDiv.innerHTML = '';
                    }
                } catch (error) {
                    const resultDiv = document.getElementById('elevations_result');
                    resultDiv.className = 'result error';
                    resultDiv.innerHTML = `<strong>Error:</strong> ${error.message}`;
                    document.getElementById('elevations_table').innerHTML = '';
                }
            }
            
            async function getThumbnail(elevationId) {
                if (!authToken) {
                    alert('Please authenticate first');
                    return;
                }
                
                const baseUrl = document.getElementById('base_url').value;
                
                try {
                    const response = await fetch(`/api/v1/elevations/${elevationId}/thumbnail?token=${encodeURIComponent(authToken)}&base_url=${encodeURIComponent(baseUrl)}`);
                    
                    if (response.ok) {
                        const blob = await response.blob();
                        const url = URL.createObjectURL(blob);
                        window.open(url, '_blank');
                    } else {
                        alert(`Error getting thumbnail: ${response.status}`);
                    }
                } catch (error) {
                    alert(`Error getting thumbnail: ${error.message}`);
                }
            }
            
            // Directory Exclusion Functions
            function toggleSelectAll() {
                const selectAllCheckbox = document.getElementById('selectAll');
                const checkboxes = document.querySelectorAll('.directory-checkbox');
                checkboxes.forEach(checkbox => {
                    checkbox.checked = selectAllCheckbox.checked;
                });
            }
            
            async function toggleDirectoryExclusion(directoryId, exclude) {
                try {
                    const response = await fetch(`/api/v1/directories/${directoryId}/exclude`, {
                        method: 'POST',
                        headers: {
                            'Content-Type': 'application/json',
                        },
                        body: JSON.stringify({
                            exclude: exclude
                        })
                    });
                    
                    const result = await response.json();
                    
                    if (response.ok) {
                        showNotification(result.message, 'success');
                        // Refresh the directories tree
                        refreshDirectories();
                    } else {
                        showNotification(`Error: ${result.detail?.message || 'Unknown error'}`, 'error');
                    }
                } catch (error) {
                    showNotification(`Error: ${error.message}`, 'error');
                }
            }
            
            async function bulkExcludeFromSync() {
                const selectedCheckboxes = document.querySelectorAll('.directory-checkbox:checked');
                if (selectedCheckboxes.length === 0) {
                    alert('Please select directories to exclude');
                    return;
                }
                
                const directoryIds = Array.from(selectedCheckboxes).map(cb => parseInt(cb.value));
                
                if (!confirm(`Are you sure you want to exclude ${directoryIds.length} directories from sync?`)) {
                    return;
                }
                
                try {
                    const response = await fetch('/api/v1/directories/bulk-exclude', {
                        method: 'POST',
                        headers: {
                            'Content-Type': 'application/json',
                        },
                        body: JSON.stringify({
                            directory_ids: directoryIds,
                            exclude: true
                        })
                    });
                    
                    const result = await response.json();
                    
                    if (response.ok) {
                        alert(result.message);
                        // Refresh the directories table
                        getDirectories();
                    } else {
                        alert(`Error: ${result.detail?.message || 'Unknown error'}`);
                    }
                } catch (error) {
                    alert(`Error: ${error.message}`);
                }
            }
            
            async function bulkIncludeInSync() {
                const selectedCheckboxes = document.querySelectorAll('.directory-checkbox:checked');
                if (selectedCheckboxes.length === 0) {
                    alert('Please select directories to include');
                    return;
                }
                
                const directoryIds = Array.from(selectedCheckboxes).map(cb => parseInt(cb.value));
                
                if (!confirm(`Are you sure you want to include ${directoryIds.length} directories in sync?`)) {
                    return;
                }
                
                try {
                    const response = await fetch('/api/v1/directories/bulk-exclude', {
                        method: 'POST',
                        headers: {
                            'Content-Type': 'application/json',
                        },
                        body: JSON.stringify({
                            directory_ids: directoryIds,
                            exclude: false
                        })
                    });
                    
                    const result = await response.json();
                    
                    if (response.ok) {
                        alert(result.message);
                        // Refresh the directories table
                        getDirectories();
                    } else {
                        alert(`Error: ${result.detail?.message || 'Unknown error'}`);
                    }
                } catch (error) {
                    alert(`Error: ${error.message}`);
                }
            }
            
            async function getSyncableDirectories() {
                try {
                    const response = await fetch('/api/v1/directories/syncable/');
                    const result = await response.json();
                    
                    const resultDiv = document.getElementById('directories_result');
                    const tableDiv = document.getElementById('directories_table');
                    
                    if (response.ok) {
                        resultDiv.className = 'result success';
                        resultDiv.innerHTML = `<strong>Syncable Directories (${result.count}):</strong>`;
                        
                        // Create table (same format as getDirectories)
                        let tableHtml = `
                            <table>
                                <thead>
                                    <tr>
                                        <th><input type="checkbox" id="selectAll" onchange="toggleSelectAll()"> Select All</th>
                                        <th>Name</th>
                                        <th>ID</th>
                                        <th>Level</th>
                                        <th>Exclude from Sync</th>
                                        <th>Sync Status</th>
                                        <th>Last Sync</th>
                                        <th>Actions</th>
                                    </tr>
                                </thead>
                                <tbody>
                        `;
                        
                        result.data.forEach(dir => {
                            const excludeStatus = dir.exclude_from_sync ? 'Excluded' : 'Included';
                            const excludeClass = dir.exclude_from_sync ? 'excluded' : 'included';
                            const lastSync = dir.synced_at ? new Date(dir.synced_at).toLocaleDateString() : 'Never';
                            
                            tableHtml += `
                                <tr class="${excludeClass}">
                                    <td><input type="checkbox" class="directory-checkbox" value="${dir.id}"></td>
                                    <td>${dir.name}</td>
                                    <td>${dir.logikal_id}</td>
                                    <td>${dir.level || 0}</td>
                                    <td>
                                        <span class="exclude-status ${excludeClass}">${excludeStatus}</span>
                                        <button class="toggle-btn" onclick="toggleDirectoryExclusion(${dir.id}, ${!dir.exclude_from_sync})">
                                            ${dir.exclude_from_sync ? 'Include' : 'Exclude'}
                                        </button>
                                    </td>
                                    <td>${dir.sync_status || 'pending'}</td>
                                    <td>${lastSync}</td>
                                    <td>
                                        <button class="action-btn" onclick="selectDirectory('${dir.logikal_id}')">Select</button>
                                    </td>
                                </tr>
                            `;
                        });
                        
                        tableHtml += '</tbody></table>';
                        tableDiv.innerHTML = tableHtml;
                    } else {
                        resultDiv.className = 'result error';
                        resultDiv.innerHTML = `<strong>Error:</strong> ${result.detail?.message || 'Unknown error'}`;
                        tableDiv.innerHTML = '';
                    }
                } catch (error) {
                    const resultDiv = document.getElementById('directories_result');
                    resultDiv.className = 'result error';
                    resultDiv.innerHTML = `<strong>Error:</strong> ${error.message}`;
                }
            }
            
            // Sync Functions
            async function triggerFullSync() {
                const baseUrl = document.getElementById('base_url').value;
                const username = document.getElementById('username').value;
                const password = document.getElementById('password').value;
                
                if (!baseUrl || !username || !password) {
                    alert('Please fill in all connection details first');
                    return;
                }
                
                if (!confirm('Are you sure you want to start a full sync? This may take several minutes.')) {
                    return;
                }
                
                const statusDiv = document.getElementById('sync_status');
                statusDiv.className = 'result info';
                statusDiv.innerHTML = '<strong>Full Sync:</strong> Starting full sync operation...';
                
                try {
                    const response = await fetch('/api/v1/sync/full', {
                        method: 'POST',
                        headers: {
                            'Content-Type': 'application/json',
                        },
                        body: JSON.stringify({
                            base_url: baseUrl,
                            username: username,
                            password: password
                        })
                    });
                    
                    const result = await response.json();
                    
                    if (response.ok) {
                        statusDiv.className = 'result success';
                        statusDiv.innerHTML = `
                            <strong>Full Sync Completed:</strong> ${result.message}<br>
                            <strong>Duration:</strong> ${result.duration_seconds} seconds<br>
                            <strong>Directories:</strong> ${result.directories_processed}<br>
                            <strong>Projects:</strong> ${result.projects_processed}<br>
                            <strong>Phases:</strong> ${result.phases_processed}<br>
                            <strong>Elevations:</strong> ${result.elevations_processed}<br>
                            <strong>Total Items:</strong> ${result.total_items}
                        `;
                    } else {
                        statusDiv.className = 'result error';
                        statusDiv.innerHTML = `<strong>Full Sync Failed:</strong> ${result.detail?.message || 'Unknown error'}`;
                    }
                } catch (error) {
                    statusDiv.className = 'result error';
                    statusDiv.innerHTML = `<strong>Full Sync Error:</strong> ${error.message}`;
                }
            }
            
            async function triggerIncrementalSync() {
                const baseUrl = document.getElementById('base_url').value;
                const username = document.getElementById('username').value;
                const password = document.getElementById('password').value;
                
                if (!baseUrl || !username || !password) {
                    alert('Please fill in all connection details first');
                    return;
                }
                
                if (!confirm('Are you sure you want to start an incremental sync?')) {
                    return;
                }
                
                const statusDiv = document.getElementById('sync_status');
                statusDiv.className = 'result info';
                statusDiv.innerHTML = '<strong>Incremental Sync:</strong> Starting incremental sync operation...';
                
                try {
                    const response = await fetch('/api/v1/sync/incremental', {
                        method: 'POST',
                        headers: {
                            'Content-Type': 'application/json',
                        },
                        body: JSON.stringify({
                            base_url: baseUrl,
                            username: username,
                            password: password
                        })
                    });
                    
                    const result = await response.json();
                    
                    if (response.ok) {
                        statusDiv.className = 'result success';
                        statusDiv.innerHTML = `
                            <strong>Incremental Sync Completed:</strong> ${result.message}<br>
                            <strong>Duration:</strong> ${result.duration_seconds} seconds<br>
                            <strong>Last Sync:</strong> ${result.last_sync_time || 'N/A'}
                        `;
                    } else {
                        statusDiv.className = 'result error';
                        statusDiv.innerHTML = `<strong>Incremental Sync Failed:</strong> ${result.detail?.message || 'Unknown error'}`;
                    }
                } catch (error) {
                    statusDiv.className = 'result error';
                    statusDiv.innerHTML = `<strong>Incremental Sync Error:</strong> ${error.message}`;
                }
            }
            
            async function getSyncStatus() {
                try {
                    const response = await fetch('/api/v1/sync/status');
                    const result = await response.json();
                    
                    const statusDiv = document.getElementById('sync_status');
                    const logsDiv = document.getElementById('sync_logs');
                    
                    if (response.ok) {
                        statusDiv.className = 'result success';
                        statusDiv.innerHTML = `
                            <strong>Sync Status:</strong><br>
                            <strong>Sync Enabled:</strong> ${result.sync_config.is_sync_enabled ? 'Yes' : 'No'}<br>
                            <strong>Sync Interval:</strong> ${result.sync_config.sync_interval_minutes} minutes<br>
                            <strong>Last Full Sync:</strong> ${result.sync_config.last_full_sync || 'Never'}<br>
                            <strong>Last Incremental Sync:</strong> ${result.sync_config.last_incremental_sync || 'Never'}
                        `;
                        
                        // Display recent logs
                        if (result.recent_logs && result.recent_logs.length > 0) {
                            let logsHtml = '<h3>Recent Sync Logs</h3><table><thead><tr><th>Type</th><th>Status</th><th>Message</th><th>Items</th><th>Duration</th><th>Started</th></tr></thead><tbody>';
                            
                            result.recent_logs.forEach(log => {
                                const statusClass = log.status === 'completed' ? 'success' : log.status === 'failed' ? 'error' : 'info';
                                logsHtml += `
                                    <tr class="${statusClass}">
                                        <td>${log.sync_type}</td>
                                        <td>${log.status}</td>
                                        <td>${log.message}</td>
                                        <td>${log.items_processed}</td>
                                        <td>${log.duration_seconds || 'N/A'}s</td>
                                        <td>${new Date(log.started_at).toLocaleString()}</td>
                                    </tr>
                                `;
                            });
                            
                            logsHtml += '</tbody></table>';
                            logsDiv.innerHTML = logsHtml;
                        } else {
                            logsDiv.innerHTML = '<p>No recent sync logs found.</p>';
                        }
                    } else {
                        statusDiv.className = 'result error';
                        statusDiv.innerHTML = `<strong>Sync Status Error:</strong> ${result.detail?.message || 'Unknown error'}`;
                        logsDiv.innerHTML = '';
                    }
                } catch (error) {
                    const statusDiv = document.getElementById('sync_status');
                    statusDiv.className = 'result error';
                    statusDiv.innerHTML = `<strong>Sync Status Error:</strong> ${error.message}`;
                }
            }
            
            // Dashboard Functions (Phase 1)
            async function refreshAlerts() {
                try {
                    const response = await fetch('/api/v1/health/detailed');
                    const healthData = await response.json();
                    
                    const alertsList = document.getElementById('alerts-list');
                    let alertHtml = '';
                    let alertCount = 0;
                    
                    // Check for specific health issues
                    const alerts = [];
                    
                    // Database connection pool check
                    if (healthData.components && healthData.components.database) {
                        const dbHealth = healthData.components.database;
                        if (dbHealth.status === 'unhealthy') {
                            alerts.push({
                                type: 'critical',
                                message: `Database: ${dbHealth.error || 'Connection failed'}`,
                                time: 'Just now'
                            });
                            alertCount++;
                        } else if (dbHealth.connection_pool) {
                            const pool = dbHealth.connection_pool;
                            const poolUsage = ((pool.checked_out + pool.overflow) / pool.size) * 100;
                            if (poolUsage > 90) {
                                alerts.push({
                                    type: 'critical',
                                    message: `Database connection pool exhausted (${Math.round(poolUsage)}% usage)`,
                                    time: 'Just now'
                                });
                                alertCount++;
                            } else if (poolUsage > 75) {
                                alerts.push({
                                    type: 'warning',
                                    message: `Database connection pool high usage (${Math.round(poolUsage)}% usage)`,
                                    time: 'Just now'
                                });
                                alertCount++;
                            }
                        }
                    }
                    
                    // Redis check
                    if (healthData.components && healthData.components.redis) {
                        const redisHealth = healthData.components.redis;
                        if (redisHealth.status === 'unhealthy') {
                            alerts.push({
                                type: 'critical',
                                message: `Redis: ${redisHealth.error || 'Connection failed'}`,
                                time: 'Just now'
                            });
                            alertCount++;
                        }
                    }
                    
                    // System resource checks
                    if (healthData.components && healthData.components.system) {
                        const systemHealth = healthData.components.system;
                        if (systemHealth.cpu_usage_percent > 90) {
                            alerts.push({
                                type: 'warning',
                                message: `High CPU usage (${Math.round(systemHealth.cpu_usage_percent)}%)`,
                                time: 'Just now'
                            });
                            alertCount++;
                        }
                        if (systemHealth.memory_usage_percent > 90) {
                            alerts.push({
                                type: 'warning',
                                message: `High memory usage (${Math.round(systemHealth.memory_usage_percent)}%)`,
                                time: 'Just now'
                            });
                            alertCount++;
                        }
                    }
                    
                    // General unhealthy components
                    if (healthData.unhealthy_components && healthData.unhealthy_components.length > 0) {
                        healthData.unhealthy_components.forEach(component => {
                            alerts.push({
                                type: 'critical',
                                message: `${component} component is unhealthy`,
                                time: 'Just now'
                            });
                            alertCount++;
                        });
                    }
                    
                    // Display alerts
                    if (alerts.length > 0) {
                        alerts.forEach(alert => {
                            alertHtml += `
                                <div class="alert-item alert-${alert.type}">
                                    <strong>${alert.type === 'critical' ? 'Critical' : 'Warning'}:</strong> ${alert.message}
                                    <div style="font-size: 12px; color: #666; margin-top: 5px;">${alert.time}</div>
                                </div>
                            `;
                        });
                    } else {
                        alertHtml = `
                            <div class="alert-item alert-info">
                                <strong>Info:</strong> All systems are healthy
                                <div style="font-size: 12px; color: #666; margin-top: 5px;">Just now</div>
                            </div>
                        `;
                    }
                    
                    alertsList.innerHTML = alertHtml;
                    
                    // Update alert count
                    document.getElementById('alert-count').textContent = alertCount;
                    
                } catch (error) {
                    console.error('Error refreshing alerts:', error);
                }
            }
            
            async function refreshSyncHistory() {
                try {
                    const response = await fetch('/api/v1/sync/status');
                    const syncData = await response.json();
                    
                    const tableBody = document.getElementById('sync-history-table');
                    let tableHtml = '';
                    
                    if (syncData.success && syncData.recent_logs && syncData.recent_logs.length > 0) {
                        // Show the 5 most recent sync operations
                        const recentOps = syncData.recent_logs.slice(0, 5);
                        
                        recentOps.forEach(log => {
                            const statusClass = log.status === 'completed' ? 'status-success' : 
                                              log.status === 'failed' ? 'status-error' : 'status-warning';
                            const statusText = log.status === 'completed' ? 'Success' : 
                                             log.status === 'failed' ? 'Failed' : 'Running';
                            
                            // Calculate time ago
                            const startTime = new Date(log.started_at);
                            const now = new Date();
                            const diffMs = now - startTime;
                            const diffMins = Math.floor(diffMs / 60000);
                            const timeAgo = diffMins < 1 ? 'Just now' : 
                                          diffMins === 1 ? '1 min ago' : 
                                          `${diffMins} min ago`;
                            
                            // Format operation type
                            const operationType = log.sync_type.replace('_', ' ').replace(/\b\w/g, l => l.toUpperCase());
                            
                            // Format objects count
                            const objectsCount = log.items_processed || 0;
                            const objectsText = objectsCount === 1 ? '1 object' : `${objectsCount} objects`;
                            
                            // Format duration
                            const duration = log.duration_seconds ? `${log.duration_seconds}s` : 
                                            log.status === 'started' ? 'Running...' : '-';
                            
                            tableHtml += `
                                <tr>
                                    <td>${timeAgo}</td>
                                    <td>${operationType}</td>
                                    <td>${objectsText}</td>
                                    <td>${duration}</td>
                                    <td><span class="status-indicator ${statusClass}"></span>${statusText}</td>
                                    <td><button class="action-btn btn-info" onclick="showSyncDetails(${log.id})">Details</button></td>
                                </tr>
                            `;
                        });
                    } else {
                        tableHtml = '<tr><td colspan="6" style="text-align: center; color: #666;">No sync operations found</td></tr>';
                    }
                    
                    tableBody.innerHTML = tableHtml;
                    
                } catch (error) {
                    console.error('Error refreshing sync history:', error);
                    const tableBody = document.getElementById('sync-history-table');
                    tableBody.innerHTML = '<tr><td colspan="6" style="text-align: center; color: #d32f2f;">Error loading sync history</td></tr>';
                }
            }
            
            function showSyncDetails(syncId) {
                // Show sync details in a modal or alert
                // For now, we'll show an alert with the sync ID
                alert(`Sync Details for ID: ${syncId}\n\nThis will show detailed information about the sync operation including:\n- Start/End times\n- Error details (if any)\n- Items processed\n- Performance metrics`);
            }
            
            async function updateDashboardMetrics() {
                try {
                    // Update system health
                    const healthResponse = await fetch('/api/v1/health/detailed');
                    const healthData = await healthResponse.json();
                    
                    const systemHealth = healthData.status === 'healthy' ? 'Healthy' : 'Unhealthy';
                    const healthScore = healthData.status === 'healthy' ? 95 : 60;
                    
                    document.getElementById('system-health').textContent = systemHealth;
                    document.querySelector('.card .progress-fill').style.width = healthScore + '%';
                    
                    // Update sync statistics (mock data for now)
                    const syncCount = Math.floor(Math.random() * 2000) + 1000;
                    document.getElementById('sync-count').textContent = syncCount.toLocaleString();
                    
                    // Update consistency score (mock data)
                    const consistencyScore = Math.floor(Math.random() * 20) + 80;
                    document.getElementById('consistency-score').textContent = consistencyScore + '%';
                    document.querySelector('.card:nth-child(3) .progress-fill').style.width = consistencyScore + '%';
                    
                    // Update API requests (mock data)
                    const apiRequests = Math.floor(Math.random() * 100) + 100;
                    document.getElementById('api-requests').textContent = apiRequests;
                    
                    // Update CPU usage (mock data)
                    const cpuUsage = Math.floor(Math.random() * 40) + 10;
                    document.getElementById('cpu-usage').textContent = cpuUsage + '%';
                    document.querySelector('.card:nth-child(6) .progress-fill').style.width = cpuUsage + '%';
                    
                } catch (error) {
                    console.error('Error updating dashboard metrics:', error);
                }
            }
            
            // Sync Management Functions (Phase 2)
            async function updateSmartSyncSettings() {
                const cascadingSync = document.getElementById('cascading-sync').checked;
                const stalenessThreshold = document.getElementById('staleness-threshold').value;
                const syncPriority = document.getElementById('sync-priority').value;
                
                try {
                    const response = await fetch('/api/v1/advanced-sync/settings', {
                        method: 'POST',
                        headers: {
                            'Content-Type': 'application/json',
                        },
                        body: JSON.stringify({
                            cascading_sync_enabled: cascadingSync,
                            staleness_threshold_hours: parseInt(stalenessThreshold),
                            default_priority: syncPriority
                        })
                    });
                    
                    if (response.ok) {
                        showNotification('Smart sync settings updated successfully!', 'success');
                    } else {
                        const error = await response.json();
                        showNotification(`Error updating settings: ${error.detail}`, 'error');
                    }
                } catch (error) {
                    showNotification(`Error updating settings: ${error.message}`, 'error');
                }
            }
            
            async function triggerSelectiveSync() {
                const objectType = document.getElementById('sync-object-type').value;
                const dateRange = document.getElementById('sync-date-range').value;
                
                try {
                    const response = await fetch('/api/v1/advanced-sync/selective', {
                        method: 'POST',
                        headers: {
                            'Content-Type': 'application/json',
                        },
                        body: JSON.stringify({
                            object_type: objectType,
                            date_range: dateRange,
                            priority: 'medium'
                        })
                    });
                    
                    if (response.ok) {
                        showNotification('Selective sync started successfully!', 'success');
                        refreshSyncStatus();
                    } else {
                        const error = await response.json();
                        showNotification(`Error starting selective sync: ${error.detail}`, 'error');
                    }
                } catch (error) {
                    showNotification(`Error starting selective sync: ${error.message}`, 'error');
                }
            }
            
            async function triggerFullSync() {
                if (!confirm('Are you sure you want to start a full system sync? This may take several minutes.')) {
                    return;
                }
                
                try {
                    const response = await fetch('/api/v1/advanced-sync/full', {
                        method: 'POST',
                        headers: {
                            'Content-Type': 'application/json',
                        },
                        body: JSON.stringify({
                            priority: 'high',
                            force_refresh: true
                        })
                    });
                    
                    if (response.ok) {
                        showNotification('Full system sync started successfully!', 'success');
                        refreshSyncStatus();
                        showSyncProgress();
                    } else {
                        const error = await response.json();
                        showNotification(`Error starting full sync: ${error.detail}`, 'error');
                    }
                } catch (error) {
                    showNotification(`Error starting full sync: ${error.message}`, 'error');
                }
            }
            
            async function updateConflictSettings() {
                const conflictStrategy = document.getElementById('conflict-strategy').value;
                const autoResolution = document.getElementById('auto-conflict-resolution').checked;
                
                try {
                    const response = await fetch('/api/v1/advanced-sync/conflict-settings', {
                        method: 'POST',
                        headers: {
                            'Content-Type': 'application/json',
                        },
                        body: JSON.stringify({
                            strategy: conflictStrategy,
                            auto_resolution: autoResolution
                        })
                    });
                    
                    if (response.ok) {
                        showNotification('Conflict resolution settings updated successfully!', 'success');
                    } else {
                        const error = await response.json();
                        showNotification(`Error updating settings: ${error.detail}`, 'error');
                    }
                } catch (error) {
                    showNotification(`Error updating settings: ${error.message}`, 'error');
                }
            }
            
            async function updateDeltaSyncSettings() {
                const deltaSyncEnabled = document.getElementById('delta-sync-enabled').checked;
                const changeSensitivity = document.getElementById('change-sensitivity').value;
                const batchSize = document.getElementById('batch-size').value;
                
                try {
                    const response = await fetch('/api/v1/advanced-sync/delta-settings', {
                        method: 'POST',
                        headers: {
                            'Content-Type': 'application/json',
                        },
                        body: JSON.stringify({
                            enabled: deltaSyncEnabled,
                            sensitivity: changeSensitivity,
                            batch_size: parseInt(batchSize)
                        })
                    });
                    
                    if (response.ok) {
                        showNotification('Delta sync settings updated successfully!', 'success');
                    } else {
                        const error = await response.json();
                        showNotification(`Error updating settings: ${error.detail}`, 'error');
                    }
                } catch (error) {
                    showNotification(`Error updating settings: ${error.message}`, 'error');
                }
            }
            
            async function refreshSyncStatus() {
                try {
                    const response = await fetch('/api/v1/sync-status/');
                    const syncData = await response.json();
                    
                    document.getElementById('active-syncs').textContent = syncData.active_syncs || 0;
                    document.getElementById('queue-size').textContent = syncData.queue_size || 0;
                    document.getElementById('last-sync').textContent = syncData.last_sync || 'Never';
                    document.getElementById('next-sync').textContent = syncData.next_scheduled || 'Not scheduled';
                    
                } catch (error) {
                    console.error('Error refreshing sync status:', error);
                }
            }
            
            async function syncIndividualObject() {
                const objectId = document.getElementById('object-id').value.trim();
                
                if (!objectId) {
                    showNotification('Please enter an object ID', 'warning');
                    return;
                }
                
                try {
                    const response = await fetch('/api/v1/advanced-sync/object', {
                        method: 'POST',
                        headers: {
                            'Content-Type': 'application/json',
                        },
                        body: JSON.stringify({
                            object_id: objectId,
                            priority: 'high'
                        })
                    });
                    
                    if (response.ok) {
                        showNotification(`Sync started for object ${objectId}`, 'success');
                        refreshSyncStatus();
                    } else {
                        const error = await response.json();
                        showNotification(`Error syncing object: ${error.detail}`, 'error');
                    }
                } catch (error) {
                    showNotification(`Error syncing object: ${error.message}`, 'error');
                }
            }
            
            async function syncAllProjects() {
                if (!confirm('Are you sure you want to sync all projects?')) {
                    return;
                }
                
                try {
                    const response = await fetch('/api/v1/advanced-sync/bulk/projects', {
                        method: 'POST',
                        headers: {
                            'Content-Type': 'application/json',
                        },
                        body: JSON.stringify({
                            priority: 'medium',
                            force_refresh: false
                        })
                    });
                    
                    if (response.ok) {
                        showNotification('All projects sync started successfully!', 'success');
                        refreshSyncStatus();
                    } else {
                        const error = await response.json();
                        showNotification(`Error starting projects sync: ${error.detail}`, 'error');
                    }
                } catch (error) {
                    showNotification(`Error starting projects sync: ${error.message}`, 'error');
                }
            }
            
            async function syncAllPhases() {
                try {
                    const response = await fetch('/api/v1/advanced-sync/bulk/phases', {
                        method: 'POST',
                        headers: {
                            'Content-Type': 'application/json',
                        },
                        body: JSON.stringify({
                            priority: 'medium',
                            force_refresh: false
                        })
                    });
                    
                    if (response.ok) {
                        showNotification('All phases sync started successfully!', 'success');
                        refreshSyncStatus();
                    } else {
                        const error = await response.json();
                        showNotification(`Error starting phases sync: ${error.detail}`, 'error');
                    }
                } catch (error) {
                    showNotification(`Error starting phases sync: ${error.message}`, 'error');
                }
            }
            
            async function syncAllElevations() {
                try {
                    const response = await fetch('/api/v1/advanced-sync/bulk/elevations', {
                        method: 'POST',
                        headers: {
                            'Content-Type': 'application/json',
                        },
                        body: JSON.stringify({
                            priority: 'medium',
                            force_refresh: false
                        })
                    });
                    
                    if (response.ok) {
                        showNotification('All elevations sync started successfully!', 'success');
                        refreshSyncStatus();
                    } else {
                        const error = await response.json();
                        showNotification(`Error starting elevations sync: ${error.detail}`, 'error');
                    }
                } catch (error) {
                    showNotification(`Error starting elevations sync: ${error.message}`, 'error');
                }
            }
            
            function showSyncProgress() {
                const progressContainer = document.getElementById('sync-progress-container');
                const progressBar = document.getElementById('sync-progress-bar');
                const progressText = document.getElementById('sync-progress-text');
                const progressDetails = document.getElementById('sync-progress-details');
                
                progressContainer.style.display = 'block';
                
                // Simulate progress
                let progress = 0;
                const interval = setInterval(() => {
                    progress += Math.random() * 10;
                    if (progress >= 100) {
                        progress = 100;
                        clearInterval(interval);
                        setTimeout(() => {
                            progressContainer.style.display = 'none';
                        }, 2000);
                    }
                    
                    progressBar.style.width = progress + '%';
                    progressText.textContent = Math.round(progress) + '%';
                    progressDetails.textContent = `Processing objects... ${Math.round(progress * 2.47)} objects synced`;
                }, 500);
            }
            
            function showSyncDetails(operation) {
                alert(`Details for ${operation}:\n\n• Started: 2 minutes ago\n• Objects processed: 15\n• Success rate: 100%\n• Duration: 2.3 seconds\n• Status: Completed successfully`);
            }
            
            function showNotification(message, type = 'info') {
                // Create notification element
                const notification = document.createElement('div');
                notification.className = `result ${type}`;
                notification.style.position = 'fixed';
                notification.style.top = '20px';
                notification.style.right = '20px';
                notification.style.zIndex = '9999';
                notification.style.minWidth = '300px';
                notification.style.padding = '15px 20px';
                notification.style.borderRadius = '8px';
                notification.style.boxShadow = '0 4px 15px rgba(0,0,0,0.2)';
                notification.textContent = message;
                
                document.body.appendChild(notification);
                
                // Remove after 5 seconds
                setTimeout(() => {
                    if (notification.parentNode) {
                        notification.parentNode.removeChild(notification);
                    }
                }, 5000);
            }
            
            // Auto-refresh dashboard data every 15 minutes
            setInterval(() => {
                if (document.getElementById('dashboard').classList.contains('active')) {
                    updateDashboardMetrics();
                    refreshAlerts();
                }
                if (document.getElementById('sync-management').classList.contains('active')) {
                    refreshSyncStatus();
                }
            }, 900000); // 15 minutes = 900,000 milliseconds
            
            // Tree toggle functionality
            function toggleDirectory(directoryId) {
                const toggle = document.getElementById(`toggle-${directoryId}`);
                const children = document.getElementById(`children-${directoryId}`);
                
                if (children.style.display === 'none') {
                    children.style.display = 'block';
                    toggle.textContent = '▼';
                } else {
                    children.style.display = 'none';
                    toggle.textContent = '▶';
                }
            }
            
            // Initialize dashboard on page load
            document.addEventListener('DOMContentLoaded', function() {
                updateDashboardMetrics();
                refreshAlerts();
                refreshSyncHistory();
                refreshSyncStatus();
            });
        </script>
    </body>
    </html>
    """
    return HTMLResponse(content=html_content)
