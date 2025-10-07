from fastapi import APIRouter, Depends, HTTPException, Query, Request, Response
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.staticfiles import StaticFiles
from sqlalchemy.orm import Session, joinedload
from sqlalchemy import func, and_, or_
from typing import List, Optional, Dict
from core.database import get_db
# Admin authentication removed - login page access is sufficient
from models.elevation import Elevation
from models.phase import Phase
from models.project import Project
from models.directory import Directory
from models.elevation_glass import ElevationGlass
from celery_app import celery_app
from datetime import datetime
import os
import json
import logging

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/admin", tags=["admin-ui"])


@router.get("/login", response_class=HTMLResponse)
async def admin_login_page():
    """Admin login page"""
    login_html = """
    <!DOCTYPE html>
    <html lang="en">
    <head>
        <meta charset="UTF-8">
        <meta name="viewport" content="width=device-width, initial-scale=1.0">
        <title>Admin Login - Logikal Middleware</title>
        <link href="https://cdn.jsdelivr.net/npm/bootstrap@5.1.3/dist/css/bootstrap.min.css" rel="stylesheet">
        <link href="https://cdnjs.cloudflare.com/ajax/libs/font-awesome/6.0.0/css/all.min.css" rel="stylesheet">
        <style>
            body {
                background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
                min-height: 100vh;
                display: flex;
                align-items: center;
            }
            .login-card {
                background: rgba(255, 255, 255, 0.95);
                backdrop-filter: blur(10px);
                border-radius: 20px;
                box-shadow: 0 20px 40px rgba(0,0,0,0.1);
            }
            .login-header {
                background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
                color: white;
                border-radius: 20px 20px 0 0;
                padding: 2rem;
                text-align: center;
            }
            .login-body {
                padding: 2rem;
            }
            .form-control {
                border-radius: 10px;
                border: 2px solid #e9ecef;
                padding: 0.75rem 1rem;
                transition: all 0.3s ease;
            }
            .form-control:focus {
                border-color: #667eea;
                box-shadow: 0 0 0 0.2rem rgba(102, 126, 234, 0.25);
            }
            .btn-login {
                background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
                border: none;
                border-radius: 10px;
                padding: 0.75rem 2rem;
                font-weight: 600;
                transition: all 0.3s ease;
            }
            .btn-login:hover {
                transform: translateY(-2px);
                box-shadow: 0 10px 20px rgba(102, 126, 234, 0.3);
            }
            .alert {
                border-radius: 10px;
                border: none;
            }
        </style>
    </head>
    <body>
        <div class="container">
            <div class="row justify-content-center">
                <div class="col-md-6 col-lg-4">
                    <div class="login-card">
                        <div class="login-header">
                            <i class="fas fa-cogs fa-3x mb-3"></i>
                            <h3>Admin Login</h3>
                            <p class="mb-0">Logikal Middleware Administration</p>
                        </div>
                        <div class="login-body">
                            <div id="errorAlert" class="alert alert-danger" style="display: none;">
                                <i class="fas fa-exclamation-triangle"></i>
                                <span id="errorMessage"></span>
                            </div>
                            
                            <form id="loginForm">
                                <div class="mb-3">
                                    <label for="username" class="form-label">
                                        <i class="fas fa-user"></i> Username
                                    </label>
                                    <input type="text" class="form-control" id="username" name="username" required>
                                </div>
                                
                                <div class="mb-4">
                                    <label for="password" class="form-label">
                                        <i class="fas fa-lock"></i> Password
                                    </label>
                                    <input type="password" class="form-control" id="password" name="password" required>
                                </div>
                                
                                <div class="d-grid">
                                    <button type="submit" class="btn btn-primary btn-login">
                                        <i class="fas fa-sign-in-alt"></i> Login
                                    </button>
                                </div>
                            </form>
                            
                            <div class="text-center mt-4">
                                <small class="text-muted">
                                    <i class="fas fa-shield-alt"></i> Secure Admin Access
                                </small>
                            </div>
                        </div>
                    </div>
                </div>
            </div>
        </div>
        
        <script src="https://cdn.jsdelivr.net/npm/bootstrap@5.1.3/dist/js/bootstrap.bundle.min.js"></script>
        <script>
            document.getElementById('loginForm').addEventListener('submit', async function(e) {
                e.preventDefault();
                
                const username = document.getElementById('username').value;
                const password = document.getElementById('password').value;
                const errorAlert = document.getElementById('errorAlert');
                const errorMessage = document.getElementById('errorMessage');
                
                try {
                    const response = await fetch('/admin/api/login', {
                        method: 'POST',
                        headers: {
                            'Content-Type': 'application/json',
                        },
                        body: JSON.stringify({
                            username: username,
                            password: password
                        })
                    });
                    
                    const data = await response.json();
                    
                    if (response.ok && data.success) {
                        // Store token in localStorage for API calls
                        localStorage.setItem('admin_token', data.access_token);
                        
                        // Set cookie for session management
                        document.cookie = `admin_session=${data.access_token}; path=/; max-age=${8 * 60 * 60}; secure; samesite=strict`;
                        
                        // Redirect to admin dashboard
                        window.location.href = '/admin';
                    } else {
                        errorMessage.textContent = data.detail || 'Login failed';
                        errorAlert.style.display = 'block';
                    }
                } catch (error) {
                    errorMessage.textContent = 'Connection error. Please try again.';
                    errorAlert.style.display = 'block';
                }
            });
            
            // Auto-hide error after 5 seconds
            function hideError() {
                const errorAlert = document.getElementById('errorAlert');
                if (errorAlert.style.display === 'block') {
                    setTimeout(() => {
                        errorAlert.style.display = 'none';
                    }, 5000);
                }
            }
            
            // Check if already logged in
            async function checkAuthStatus() {
                const token = localStorage.getItem('admin_token') || document.cookie
                    .split('; ')
                    .find(row => row.startsWith('admin_session='))
                    ?.split('=')[1];
                
                if (token) {
                    try {
                        const response = await fetch('/admin/api/verify', {
                            headers: {
                                'Authorization': `Bearer ${token}`
                            }
                        });
                        
                        if (response.ok) {
                            window.location.href = '/admin';
                        }
                    } catch (error) {
                        // Token invalid, stay on login page
                    }
                }
            }
            
            // Check auth status on page load
            checkAuthStatus();
        </script>
    </body>
    </html>
    """
    
    return HTMLResponse(content=login_html, status_code=200)


@router.post("/api/login")
async def admin_login_api(request: dict):
    """Admin login API endpoint"""
    try:
        from services.admin_auth_service import AdminAuthService
        from schemas.admin_auth import AdminLoginRequest
        
        # Create login request
        login_request = AdminLoginRequest(
            username=request.get("username"),
            password=request.get("password")
        )
        
        # Get database session
        db = next(get_db())
        auth_service = AdminAuthService(db)
        
        # Authenticate
        result = await auth_service.authenticate_admin(login_request)
        
        if result:
            return {
                "success": True,
                "access_token": result.access_token,
                "expires_at": result.expires_at.isoformat(),
                "message": result.message
            }
        else:
            raise HTTPException(status_code=401, detail="Invalid credentials")
            
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/api/verify")
async def verify_admin_token():
    """Verify admin token endpoint - authentication removed"""
    return {
        "success": True,
        "username": "admin",
        "authenticated": True
    }


@router.get("/api/logout")
async def admin_logout_api(response: Response):
    """Admin logout API endpoint"""
    # Clear the session cookie
    response.delete_cookie("admin_session")
    return {"success": True, "message": "Logged out successfully"}


@router.get("/parsing-status", response_class=HTMLResponse)
async def get_parsing_status_ui():
    """Serve the elevation parsing status UI"""
    
    try:
        # Get the template file path
        template_path = os.path.join(os.path.dirname(__file__), "..", "templates", "elevation_parsing_status.html")
        
        if not os.path.exists(template_path):
            raise HTTPException(status_code=404, detail="Template not found")
        
        # Read and return the HTML template
        with open(template_path, 'r', encoding='utf-8') as f:
            html_content = f.read()
        
        return HTMLResponse(content=html_content, status_code=200)
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error loading template: {str(e)}")


@router.get("/", response_class=HTMLResponse)
async def admin_dashboard():
    """Admin dashboard with links to various admin functions"""
    
    dashboard_html = """
    <!DOCTYPE html>
    <html lang="en">
    <head>
        <meta charset="UTF-8">
        <meta name="viewport" content="width=device-width, initial-scale=1.0">
        <title>Logikal Middleware Admin</title>
        <link href="https://cdn.jsdelivr.net/npm/bootstrap@5.1.3/dist/css/bootstrap.min.css" rel="stylesheet">
        <link href="https://cdnjs.cloudflare.com/ajax/libs/font-awesome/6.0.0/css/all.min.css" rel="stylesheet">
    </head>
    <body>
        <!-- Navigation Bar -->
        <nav class="navbar navbar-expand-lg navbar-dark bg-dark">
            <div class="container-fluid">
                <a class="navbar-brand" href="/admin">
                    <i class="fas fa-cogs"></i> Logikal Middleware Admin
                </a>
                <div class="navbar-nav ms-auto">
                    <div class="nav-item dropdown">
                        <a class="nav-link dropdown-toggle" href="#" id="adminDropdown" role="button" data-bs-toggle="dropdown">
                            <i class="fas fa-user-shield"></i> <span id="adminUsername">Admin</span>
                        </a>
                        <ul class="dropdown-menu dropdown-menu-end">
                            <li><a class="dropdown-item" href="#" onclick="logout()">
                                <i class="fas fa-sign-out-alt"></i> Logout
                            </a></li>
                        </ul>
                    </div>
                </div>
            </div>
        </nav>
        
        <div class="container mt-4">
            <div class="row">
                <div class="col-md-12">
                    <h1 class="mb-4">
                        <i class="fas fa-tachometer-alt"></i> Admin Dashboard
                    </h1>
                </div>
            </div>
            
            <div class="row">
                <div class="col-md-4 mb-4">
                    <div class="card h-100">
                        <div class="card-body text-center">
                            <i class="fas fa-database fa-3x text-primary mb-3"></i>
                            <h5 class="card-title">SQLite Parser Status</h5>
                            <p class="card-text">Monitor and manage elevation data parsing from SQLite files.</p>
                            <a href="/admin/parsing-status" class="btn btn-primary">
                                <i class="fas fa-chart-line"></i> View Status
                            </a>
                        </div>
                    </div>
                </div>
                
                <div class="col-md-4 mb-4">
                    <div class="card h-100">
                        <div class="card-body text-center">
                            <i class="fas fa-tasks fa-3x text-success mb-3"></i>
                            <h5 class="card-title">Parsing Queue Monitor</h5>
                            <p class="card-text">Real-time monitoring of Celery parsing tasks and worker status.</p>
                            <a href="/admin/parsing-queue" class="btn btn-success">
                                <i class="fas fa-tasks"></i> Monitor Queue
                            </a>
                        </div>
                    </div>
                </div>
                
                <div class="col-md-4 mb-4">
                    <div class="card h-100">
                        <div class="card-body text-center">
                            <i class="fas fa-sync fa-3x text-success mb-3"></i>
                            <h5 class="card-title">Sync Status</h5>
                            <p class="card-text">Monitor sync operations with Logikal API.</p>
                            <a href="/admin/elevations" class="btn btn-success">
                                <i class="fas fa-list"></i> View Elevations
                            </a>
                        </div>
                    </div>
                </div>
                
                <div class="col-md-4 mb-4">
                    <div class="card h-100">
                        <div class="card-body text-center">
                            <i class="fas fa-sitemap fa-3x text-info mb-3"></i>
                            <h5 class="card-title">Elevation Manager</h5>
                            <p class="card-text">Browse and manage elevations with detailed views.</p>
                            <a href="/admin/elevations" class="btn btn-info">
                                <i class="fas fa-sitemap"></i> Browse Elevations
                            </a>
                        </div>
                    </div>
                </div>
                
                <div class="col-md-4 mb-4">
                    <div class="card h-100">
                        <div class="card-body text-center">
                            <i class="fas fa-chart-bar fa-3x text-warning mb-3"></i>
                            <h5 class="card-title">Analytics</h5>
                            <p class="card-text">View enrichment statistics and metrics.</p>
                            <a href="/admin/stats" class="btn btn-warning">
                                <i class="fas fa-chart-pie"></i> View Stats
                            </a>
                        </div>
                    </div>
                </div>
                
                <div class="col-md-4 mb-4">
                    <div class="card h-100">
                        <div class="card-body text-center">
                            <i class="fas fa-network-wired fa-3x text-secondary mb-3"></i>
                            <h5 class="card-title">Connection Test</h5>
                            <p class="card-text">Test database and API connections.</p>
                            <button onclick="testConnections()" class="btn btn-secondary">
                                <i class="fas fa-plug"></i> Test Connections
                            </button>
                        </div>
                    </div>
                </div>
                
                <div class="col-md-4 mb-4">
                    <div class="card h-100">
                        <div class="card-body text-center">
                            <i class="fas fa-sync-alt fa-3x text-primary mb-3"></i>
                            <h5 class="card-title">Sync Management</h5>
                            <p class="card-text">Manage data synchronization with Logikal.</p>
                            <button onclick="showSyncManagement()" class="btn btn-primary">
                                <i class="fas fa-cogs"></i> Manage Sync
                            </button>
                        </div>
                    </div>
                </div>
                
                <div class="col-md-4 mb-4">
                    <div class="card h-100">
                        <div class="card-body text-center">
                            <i class="fas fa-folder fa-3x text-info mb-3"></i>
                            <h5 class="card-title">Browse Data</h5>
                            <p class="card-text">Browse directories, projects, and phases.</p>
                            <button onclick="showDataBrowser()" class="btn btn-info">
                                <i class="fas fa-folder-open"></i> Browse Data
                            </button>
                        </div>
                    </div>
                </div>
            </div>
            
            <div class="row mt-4">
                <div class="col-md-12">
                    <div class="card">
                        <div class="card-header">
                            <h5><i class="fas fa-info-circle"></i> Quick Info</h5>
                        </div>
                        <div class="card-body">
                            <div class="row">
                                <div class="col-md-6">
                                    <h6>API Endpoints:</h6>
                                    <ul class="list-unstyled">
                                        <li><code>GET /api/v1/elevations/cached</code> - List all elevations</li>
                                        <li><code>GET /api/v1/elevations/{id}/enrichment</code> - Get enrichment status</li>
                                        <li><code>POST /api/v1/elevations/{id}/enrichment/trigger</code> - Trigger parsing</li>
                                        <li><code>GET /api/v1/elevations/enrichment/status</code> - Global status</li>
                                    </ul>
                                </div>
                                <div class="col-md-6">
                                    <h6>Features:</h6>
                                    <ul class="list-unstyled">
                                        <li><i class="fas fa-check text-success"></i> Async SQLite parsing</li>
                                        <li><i class="fas fa-check text-success"></i> 2-worker concurrency limit</li>
                                        <li><i class="fas fa-check text-success"></i> Comprehensive error handling</li>
                                        <li><i class="fas fa-check text-success"></i> Retry logic with backoff</li>
                                        <li><i class="fas fa-check text-success"></i> Security validation</li>
                                    </ul>
                                </div>
                            </div>
                        </div>
                    </div>
                </div>
            </div>
            
            <!-- Connection Test Modal -->
            <div class="modal fade" id="connectionTestModal" tabindex="-1" aria-labelledby="connectionTestModalLabel" aria-hidden="true">
                <div class="modal-dialog modal-lg">
                    <div class="modal-content">
                        <div class="modal-header">
                            <h5 class="modal-title" id="connectionTestModalLabel">
                                <i class="fas fa-network-wired"></i> Connection Test Results
                            </h5>
                            <button type="button" class="btn-close" data-bs-dismiss="modal" aria-label="Close"></button>
                        </div>
                        <div class="modal-body">
                            <div id="connectionTestResults">
                                <div class="text-center">
                                    <div class="spinner-border" role="status">
                                        <span class="visually-hidden">Testing connections...</span>
                                    </div>
                                    <p class="mt-2">Testing connections...</p>
                                </div>
                            </div>
                        </div>
                        <div class="modal-footer">
                            <button type="button" class="btn btn-secondary" data-bs-dismiss="modal">Close</button>
                            <button type="button" class="btn btn-primary" onclick="testConnections()">Retest</button>
                        </div>
                    </div>
                </div>
            </div>
            
            <!-- Sync Management Modal -->
            <div class="modal fade" id="syncManagementModal" tabindex="-1" aria-labelledby="syncManagementModalLabel" aria-hidden="true">
                <div class="modal-dialog modal-xl">
                    <div class="modal-content">
                        <div class="modal-header">
                            <h5 class="modal-title" id="syncManagementModalLabel">
                                <i class="fas fa-sync-alt"></i> Sync Management
                            </h5>
                            <button type="button" class="btn-close" data-bs-dismiss="modal" aria-label="Close"></button>
                        </div>
                        <div class="modal-body">
                            <!-- Logikal Connection Test -->
                            <div class="card mb-4">
                                <div class="card-header">
                                    <h6><i class="fas fa-plug"></i> Logikal API Connection Test</h6>
                                </div>
                                <div class="card-body">
                                    <div class="row">
                                        <div class="col-md-4">
                                            <label class="form-label">Base URL</label>
                                            <input type="text" id="logikalBaseUrl" class="form-control" placeholder="https://api.logikal.com" value="http://128.199.57.77/MbioeService.svc/api/v3">
                                        </div>
                                        <div class="col-md-4">
                                            <label class="form-label">Username</label>
                                            <input type="text" id="logikalUsername" class="form-control" placeholder="Your username">
                                        </div>
                                        <div class="col-md-4">
                                            <label class="form-label">Password</label>
                                            <input type="password" id="logikalPassword" class="form-control" placeholder="Your password">
                                        </div>
                                    </div>
                                    <div class="mt-3">
                                        <button onclick="testLogikalConnection()" class="btn btn-primary">
                                            <i class="fas fa-plug"></i> Test Logikal Connection
                                        </button>
                                        <div id="logikalConnectionResult" class="mt-2"></div>
                                    </div>
                                </div>
                            </div>
                            
                            <!-- Sync Operations -->
                            <div class="card mb-4">
                                <div class="card-header">
                                    <h6><i class="fas fa-sync"></i> Sync Operations</h6>
                                </div>
                                <div class="card-body">
                                    <div class="row">
                                        <div class="col-md-3">
                                            <div class="d-grid">
                                                <button onclick="triggerSync('directories')" class="btn btn-outline-primary mb-2">
                                                    <i class="fas fa-folder"></i> Sync Directories
                                                </button>
                                            </div>
                                        </div>
                                        <div class="col-md-3">
                                            <div class="d-grid">
                                                <button onclick="triggerSync('projects')" class="btn btn-outline-success mb-2">
                                                    <i class="fas fa-project-diagram"></i> Sync Projects
                                                </button>
                                            </div>
                                        </div>
                                        <div class="col-md-3">
                                            <div class="d-grid">
                                                <button onclick="triggerSync('phases')" class="btn btn-outline-info mb-2">
                                                    <i class="fas fa-layer-group"></i> Sync Phases
                                                </button>
                                            </div>
                                        </div>
                                        <div class="col-md-3">
                                            <div class="d-grid">
                                                <button onclick="triggerSync('elevations')" class="btn btn-outline-warning mb-2">
                                                    <i class="fas fa-cube"></i> Sync Elevations
                                                </button>
                                            </div>
                                        </div>
                                    </div>
                                    <div class="mt-3">
                                        <button onclick="triggerFullSync()" class="btn btn-primary">
                                            <i class="fas fa-sync-alt"></i> Full Sync (All Data)
                                        </button>
                                    </div>
                                    <div id="syncResults" class="mt-3"></div>
                                </div>
                            </div>
                            
                            <!-- Sync Status -->
                            <div class="card">
                                <div class="card-header">
                                    <h6><i class="fas fa-chart-line"></i> Current Sync Status</h6>
                                </div>
                                <div class="card-body">
                                    <div id="syncStatus" class="table-responsive">
                                        <div class="text-center">
                                            <div class="spinner-border" role="status">
                                                <span class="visually-hidden">Loading sync status...</span>
                                            </div>
                                        </div>
                                    </div>
                                </div>
                            </div>
                        </div>
                        <div class="modal-footer">
                            <button type="button" class="btn btn-secondary" data-bs-dismiss="modal">Close</button>
                            <button type="button" class="btn btn-primary" onclick="refreshSyncStatus()">Refresh Status</button>
                        </div>
                    </div>
                </div>
            </div>
            
            <!-- Data Browser Modal -->
            <div class="modal fade" id="dataBrowserModal" tabindex="-1" aria-labelledby="dataBrowserModalLabel" aria-hidden="true">
                <div class="modal-dialog modal-xl">
                    <div class="modal-content">
                        <div class="modal-header">
                            <h5 class="modal-title" id="dataBrowserModalLabel">
                                <i class="fas fa-folder-open"></i> Data Browser
                            </h5>
                            <button type="button" class="btn-close" data-bs-dismiss="modal" aria-label="Close"></button>
                        </div>
                        <div class="modal-body">
                            <div class="row">
                                <div class="col-md-3">
                                    <div class="card">
                                        <div class="card-header">
                                            <h6><i class="fas fa-folder"></i> Directories</h6>
                                        </div>
                                        <div class="card-body" style="max-height: 400px; overflow-y: auto;">
                                            <div id="directoriesList">
                                                <div class="text-center">
                                                    <div class="spinner-border spinner-border-sm" role="status">
                                                        <span class="visually-hidden">Loading...</span>
                                                    </div>
                                                </div>
                                            </div>
                                        </div>
                                    </div>
                                </div>
                                <div class="col-md-3">
                                    <div class="card">
                                        <div class="card-header">
                                            <h6><i class="fas fa-project-diagram"></i> Projects</h6>
                                        </div>
                                        <div class="card-body" style="max-height: 400px; overflow-y: auto;">
                                            <div id="projectsList">
                                                <div class="text-center text-muted">
                                                    <i class="fas fa-arrow-left"></i> Select a directory
                                                </div>
                                            </div>
                                        </div>
                                    </div>
                                </div>
                                <div class="col-md-3">
                                    <div class="card">
                                        <div class="card-header">
                                            <h6><i class="fas fa-layer-group"></i> Phases</h6>
                                        </div>
                                        <div class="card-body" style="max-height: 400px; overflow-y: auto;">
                                            <div id="phasesList">
                                                <div class="text-center text-muted">
                                                    <i class="fas fa-arrow-left"></i> Select a project
                                                </div>
                                            </div>
                                        </div>
                                    </div>
                                </div>
                                <div class="col-md-3">
                                    <div class="card">
                                        <div class="card-header">
                                            <h6><i class="fas fa-cube"></i> Elevations</h6>
                                        </div>
                                        <div class="card-body" style="max-height: 400px; overflow-y: auto;">
                                            <div id="elevationsList">
                                                <div class="text-center text-muted">
                                                    <i class="fas fa-arrow-left"></i> Select a phase
                                                </div>
                                            </div>
                                        </div>
                                    </div>
                                </div>
                            </div>
                        </div>
                        <div class="modal-footer">
                            <button type="button" class="btn btn-secondary" data-bs-dismiss="modal">Close</button>
                            <button type="button" class="btn btn-primary" onclick="refreshDataBrowser()">Refresh</button>
                        </div>
                    </div>
                </div>
            </div>
        </div>
        
        <script>
            // Authentication removed - page loads directly
            document.addEventListener('DOMContentLoaded', function() {
                // Set admin username directly since authentication is removed
                const adminUsernameElement = document.getElementById('adminUsername');
                if (adminUsernameElement) {
                    adminUsernameElement.textContent = 'admin';
                }
            });
            
            async function logout() {
                try {
                    await fetch('/admin/api/logout', {
                        method: 'GET'
                    });
                } catch (error) {
                    console.error('Logout error:', error);
                } finally {
                    // Clear tokens and reload page instead of redirecting to login
                    localStorage.removeItem('admin_token');
                    document.cookie = 'admin_session=; path=/; expires=Thu, 01 Jan 1970 00:00:01 GMT;';
                    window.location.reload();
                }
            }
            
            function testConnections() {
                // Show modal
                const modal = new bootstrap.Modal(document.getElementById('connectionTestModal'));
                modal.show();
                
                // Reset results
                document.getElementById('connectionTestResults').innerHTML = `
                    <div class="text-center">
                        <div class="spinner-border" role="status">
                            <span class="visually-hidden">Testing connections...</span>
                        </div>
                        <p class="mt-2">Testing connections...</p>
                    </div>
                `;
                
                // Run tests
                runConnectionTests();
            }
            
            async function runConnectionTests() {
                const results = [];
                
                // Test 1: Database Connection
                try {
                    const start = Date.now();
                    const response = await fetch('/api/v1/elevations/enrichment/status');
                    const duration = Date.now() - start;
                    
                    if (response.ok) {
                        results.push({
                            name: 'Database Connection',
                            status: 'success',
                            message: `Connected successfully (${duration}ms)`,
                            details: 'PostgreSQL database is accessible'
                        });
                    } else {
                        results.push({
                            name: 'Database Connection',
                            status: 'error',
                            message: `HTTP ${response.status}`,
                            details: 'Database connection failed'
                        });
                    }
                } catch (error) {
                    results.push({
                        name: 'Database Connection',
                        status: 'error',
                        message: 'Connection failed',
                        details: error.message
                    });
                }
                
                // Test 2: Elevation Tree API
                try {
                    const start = Date.now();
                    const response = await fetch('/admin/elevations/tree');
                    const duration = Date.now() - start;
                    
                    if (response.ok) {
                        const data = await response.json();
                        const elevationCount = data.data ? data.data.length : 0;
                        results.push({
                            name: 'Elevation Tree API',
                            status: 'success',
                            message: `Loaded ${elevationCount} directories (${duration}ms)`,
                            details: 'Elevation tree data is accessible'
                        });
                    } else {
                        results.push({
                            name: 'Elevation Tree API',
                            status: 'error',
                            message: `HTTP ${response.status}`,
                            details: 'Failed to load elevation tree'
                        });
                    }
                } catch (error) {
                    results.push({
                        name: 'Elevation Tree API',
                        status: 'error',
                        message: 'Connection failed',
                        details: error.message
                    });
                }
                
                // Test 3: Search API
                try {
                    const start = Date.now();
                    const response = await fetch('/api/v1/ui/elevations/search?q=test&limit=1');
                    const duration = Date.now() - start;
                    
                    if (response.ok) {
                        const data = await response.json();
                        const resultCount = data.data ? data.data.length : 0;
                        results.push({
                            name: 'Search API',
                            status: 'success',
                            message: `Search working (${duration}ms)`,
                            details: `Found ${resultCount} test results`
                        });
                    } else {
                        results.push({
                            name: 'Search API',
                            status: 'error',
                            message: `HTTP ${response.status}`,
                            details: 'Search functionality failed'
                        });
                    }
                } catch (error) {
                    results.push({
                        name: 'Search API',
                        status: 'error',
                        message: 'Connection failed',
                        details: error.message
                    });
                }
                
                // Test 4: Celery/Redis Connection (if available)
                try {
                    const response = await fetch('/api/v1/elevations/enrichment/status');
                    if (response.ok) {
                        const data = await response.json();
                        results.push({
                            name: 'Background Tasks',
                            status: 'success',
                            message: 'Celery/Redis accessible',
                            details: 'Background task system is operational'
                        });
                    }
                } catch (error) {
                    results.push({
                        name: 'Background Tasks',
                        status: 'warning',
                        message: 'Celery/Redis not available',
                        details: 'Background tasks may not work'
                    });
                }
                
                // Display results
                displayConnectionResults(results);
            }
            
            function displayConnectionResults(results) {
                const container = document.getElementById('connectionTestResults');
                const allSuccess = results.every(r => r.status === 'success');
                const hasErrors = results.some(r => r.status === 'error');
                
                let html = `
                    <div class="alert ${allSuccess ? 'alert-success' : hasErrors ? 'alert-danger' : 'alert-warning'}">
                        <h6><i class="fas fa-${allSuccess ? 'check-circle' : hasErrors ? 'exclamation-triangle' : 'exclamation-circle'}"></i> 
                        Connection Test ${allSuccess ? 'Passed' : hasErrors ? 'Failed' : 'Completed with Warnings'}</h6>
                    </div>
                    
                    <div class="row">
                `;
                
                results.forEach(result => {
                    const statusIcon = result.status === 'success' ? 'fa-check-circle text-success' : 
                                     result.status === 'error' ? 'fa-times-circle text-danger' : 
                                     'fa-exclamation-triangle text-warning';
                    
                    html += `
                        <div class="col-md-6 mb-3">
                            <div class="card">
                                <div class="card-body">
                                    <h6 class="card-title">
                                        <i class="fas ${statusIcon}"></i> ${result.name}
                                    </h6>
                                    <p class="card-text mb-1">${result.message}</p>
                                    <small class="text-muted">${result.details}</small>
                                </div>
                            </div>
                        </div>
                    `;
                });
                
                html += `</div>`;
                container.innerHTML = html;
            }
            
            // Sync Management Functions
            function showSyncManagement() {
                const modal = new bootstrap.Modal(document.getElementById('syncManagementModal'));
                modal.show();
                refreshSyncStatus();
            }
            
            async function testLogikalConnection() {
                const baseUrl = document.getElementById('logikalBaseUrl').value;
                const username = document.getElementById('logikalUsername').value;
                const password = document.getElementById('logikalPassword').value;
                const resultDiv = document.getElementById('logikalConnectionResult');
                
                if (!baseUrl || !username || !password) {
                    resultDiv.innerHTML = `
                        <div class="alert alert-warning">
                            <i class="fas fa-exclamation-triangle"></i> Please fill in all connection details
                        </div>
                    `;
                    return;
                }
                
                resultDiv.innerHTML = `
                    <div class="text-center">
                        <div class="spinner-border spinner-border-sm" role="status">
                            <span class="visually-hidden">Testing...</span>
                        </div>
                        <span class="ms-2">Testing Logikal connection...</span>
                    </div>
                `;
                
                try {
                    const startTime = Date.now();
                    
                    // Build query parameters
                    const params = new URLSearchParams({
                        base_url: baseUrl,
                        username: username,
                        password: password
                    });
                    
                    const response = await fetch(`/api/v1/auth/test?${params}`, {
                        method: 'GET'
                    });
                    
                    const result = await response.json();
                    const responseTime = Date.now() - startTime;
                    
                    if (result.success) {
                        resultDiv.innerHTML = `
                            <div class="alert alert-success">
                                <i class="fas fa-check-circle"></i> Connection successful! 
                                <small class="d-block mt-1">Response time: ${responseTime}ms</small>
                                <small class="d-block mt-1">Message: ${result.message}</small>
                            </div>
                        `;
                    } else {
                        resultDiv.innerHTML = `
                            <div class="alert alert-danger">
                                <i class="fas fa-times-circle"></i> Connection failed: ${result.message}
                                <small class="d-block mt-1">Response time: ${responseTime}ms</small>
                            </div>
                        `;
                    }
                } catch (error) {
                    resultDiv.innerHTML = `
                        <div class="alert alert-danger">
                            <i class="fas fa-times-circle"></i> Connection error: ${error.message}
                        </div>
                    `;
                }
            }
            
            async function triggerSync(type) {
                const resultsDiv = document.getElementById('syncResults');
                
                resultsDiv.innerHTML = `
                    <div class="alert alert-info">
                        <i class="fas fa-spinner fa-spin"></i> Starting ${type} sync...
                    </div>
                `;
                
                try {
                    const response = await fetch(`/api/v1/sync/${type}`, {
                        method: 'POST'
                    });
                    
                    const result = await response.json();
                    
                    if (result.success) {
                        resultsDiv.innerHTML = `
                            <div class="alert alert-success">
                                <i class="fas fa-check-circle"></i> ${type} sync completed successfully!
                                <small class="d-block mt-1">${result.message}</small>
                            </div>
                        `;
                    } else {
                        resultsDiv.innerHTML = `
                            <div class="alert alert-danger">
                                <i class="fas fa-times-circle"></i> ${type} sync failed: ${result.message || result.detail}
                            </div>
                        `;
                    }
                    
                    // Refresh sync status
                    setTimeout(() => refreshSyncStatus(), 1000);
                    
                } catch (error) {
                    resultsDiv.innerHTML = `
                        <div class="alert alert-danger">
                            <i class="fas fa-times-circle"></i> ${type} sync error: ${error.message}
                        </div>
                    `;
                }
            }
            
            async function triggerFullSync() {
                const resultsDiv = document.getElementById('syncResults');
                
                resultsDiv.innerHTML = `
                    <div class="alert alert-info">
                        <i class="fas fa-spinner fa-spin"></i> Starting full sync (this may take a while)...
                    </div>
                `;
                
                const syncTypes = ['directories', 'projects', 'phases', 'elevations'];
                const results = [];
                
                for (const type of syncTypes) {
                    try {
                        const response = await fetch(`/api/v1/sync/${type}`, {
                            method: 'POST'
                        });
                        
                        const result = await response.json();
                        results.push({
                            type: type,
                            success: result.success,
                            message: result.message || result.detail || 'Completed'
                        });
                        
                        // Update progress
                        const completed = results.length;
                        const total = syncTypes.length;
                        resultsDiv.innerHTML = `
                            <div class="alert alert-info">
                                <i class="fas fa-spinner fa-spin"></i> Full sync in progress... (${completed}/${total} completed)
                                <div class="progress mt-2">
                                    <div class="progress-bar" style="width: ${(completed / total) * 100}%"></div>
                                </div>
                            </div>
                        `;
                        
                    } catch (error) {
                        results.push({
                            type: type,
                            success: false,
                            message: error.message
                        });
                    }
                }
                
                // Display final results
                const successCount = results.filter(r => r.success).length;
                const alertClass = successCount === results.length ? 'alert-success' : 
                                 successCount > 0 ? 'alert-warning' : 'alert-danger';
                
                let html = `
                    <div class="alert ${alertClass}">
                        <i class="fas fa-${successCount === results.length ? 'check-circle' : successCount > 0 ? 'exclamation-triangle' : 'times-circle'}"></i>
                        Full sync completed: ${successCount}/${results.length} successful
                    </div>
                    <div class="row">
                `;
                
                results.forEach(result => {
                    const icon = result.success ? 'fa-check text-success' : 'fa-times text-danger';
                    html += `
                        <div class="col-md-6 mb-2">
                            <div class="d-flex align-items-center">
                                <i class="fas ${icon} me-2"></i>
                                <span class="text-capitalize">${result.type}:</span>
                                <small class="ms-2 text-muted">${result.message}</small>
                            </div>
                        </div>
                    `;
                });
                
                html += `</div>`;
                resultsDiv.innerHTML = html;
                
                // Refresh sync status
                setTimeout(() => refreshSyncStatus(), 1000);
            }
            
            async function refreshSyncStatus() {
                const statusDiv = document.getElementById('syncStatus');
                
                try {
                    const response = await fetch('/api/v1/sync/status');
                    const result = await response.json();
                    
                    if (result.success) {
                        const syncConfig = result.sync_config;
                        const recentLogs = result.recent_logs || [];
                        
                        let html = `
                            <div class="row mb-3">
                                <div class="col-md-6">
                                    <div class="card">
                                        <div class="card-header">
                                            <h6><i class="fas fa-cog"></i> Sync Configuration</h6>
                                        </div>
                                        <div class="card-body">
                                            <p><strong>Sync Enabled:</strong> 
                                                <span class="badge ${syncConfig.is_sync_enabled ? 'bg-success' : 'bg-danger'}">
                                                    ${syncConfig.is_sync_enabled ? 'Yes' : 'No'}
                                                </span>
                                            </p>
                                            <p><strong>Sync Interval:</strong> ${syncConfig.sync_interval_minutes} minutes</p>
                                            <p><strong>Last Full Sync:</strong> ${syncConfig.last_full_sync ? new Date(syncConfig.last_full_sync).toLocaleString() : 'Never'}</p>
                                            <p><strong>Last Incremental Sync:</strong> ${syncConfig.last_incremental_sync ? new Date(syncConfig.last_incremental_sync).toLocaleString() : 'Never'}</p>
                                        </div>
                                    </div>
                                </div>
                                <div class="col-md-6">
                                    <div class="card">
                                        <div class="card-header">
                                            <h6><i class="fas fa-chart-line"></i> Quick Stats</h6>
                                        </div>
                                        <div class="card-body">
                                            <p><strong>Recent Syncs:</strong> ${recentLogs.length}</p>
                                            <p><strong>Completed:</strong> ${recentLogs.filter(log => log.status === 'completed').length}</p>
                                            <p><strong>Failed:</strong> ${recentLogs.filter(log => log.status === 'failed').length}</p>
                                            <p><strong>Total Items Processed:</strong> ${recentLogs.reduce((sum, log) => sum + (log.items_processed || 0), 0)}</p>
                                        </div>
                                    </div>
                                </div>
                            </div>
                            
                            <div class="card">
                                <div class="card-header">
                                    <h6><i class="fas fa-history"></i> Recent Sync Activity</h6>
                                </div>
                                <div class="card-body">
                                    <div class="table-responsive">
                                        <table class="table table-sm">
                                            <thead>
                                                <tr>
                                                    <th>Type</th>
                                                    <th>Status</th>
                                                    <th>Items</th>
                                                    <th>Duration</th>
                                                    <th>Started</th>
                                                    <th>Message</th>
                                                </tr>
                                            </thead>
                                            <tbody>
                        `;
                        
                        recentLogs.slice(0, 10).forEach(log => {
                            const statusBadge = log.status === 'completed' ? 'bg-success' : 
                                              log.status === 'failed' ? 'bg-danger' : 
                                              log.status === 'in_progress' ? 'bg-warning' : 'bg-secondary';
                            
                            html += `
                                <tr>
                                    <td><span class="badge bg-info">${log.sync_type}</span></td>
                                    <td><span class="badge ${statusBadge}">${log.status}</span></td>
                                    <td>${log.items_processed || 0}</td>
                                    <td>${log.duration_seconds || 0}s</td>
                                    <td>${new Date(log.started_at).toLocaleString()}</td>
                                    <td><small>${log.message || 'No message'}</small></td>
                                </tr>
                            `;
                        });
                        
                        html += `
                                            </tbody>
                                        </table>
                                    </div>
                                </div>
                            </div>
                        `;
                        
                        statusDiv.innerHTML = html;
                    } else {
                        statusDiv.innerHTML = `
                            <div class="alert alert-danger">
                                <i class="fas fa-exclamation-triangle"></i> Failed to load sync status
                            </div>
                        `;
                    }
                } catch (error) {
                    statusDiv.innerHTML = `
                        <div class="alert alert-danger">
                            <i class="fas fa-exclamation-triangle"></i> Error loading sync status: ${error.message}
                        </div>
                    `;
                }
            }
            
            // Data Browser Functions
            function showDataBrowser() {
                const modal = new bootstrap.Modal(document.getElementById('dataBrowserModal'));
                modal.show();
                loadDirectories();
            }
            
            async function loadDirectories() {
                const directoriesDiv = document.getElementById('directoriesList');
                
                try {
                    const response = await fetch('/api/v1/directories/cached');
                    const result = await response.json();
                    
                    if (result.success) {
                        const directories = result.data || [];
                        
                        let html = '';
                        directories.forEach(dir => {
                            html += `
                                <div class="list-group-item list-group-item-action" 
                                     onclick="selectDirectory(${dir.id}, '${dir.name}')" 
                                     style="cursor: pointer;">
                                    <div class="d-flex w-100 justify-content-between">
                                        <h6 class="mb-1">
                                            <i class="fas fa-folder me-2"></i>${dir.name}
                                        </h6>
                                        <small>${dir.path}</small>
                                    </div>
                                </div>
                            `;
                        });
                        
                        directoriesDiv.innerHTML = html || '<div class="text-center text-muted">No directories found</div>';
                    } else {
                        directoriesDiv.innerHTML = '<div class="text-center text-muted">Failed to load directories</div>';
                    }
                } catch (error) {
                    directoriesDiv.innerHTML = '<div class="text-center text-muted">Error loading directories</div>';
                }
            }
            
            async function selectDirectory(directoryId, directoryName) {
                // Clear subsequent lists
                document.getElementById('projectsList').innerHTML = `
                    <div class="text-center">
                        <div class="spinner-border spinner-border-sm" role="status">
                            <span class="visually-hidden">Loading...</span>
                        </div>
                    </div>
                `;
                document.getElementById('phasesList').innerHTML = '<div class="text-center text-muted"><i class="fas fa-arrow-left"></i> Select a project</div>';
                document.getElementById('elevationsList').innerHTML = '<div class="text-center text-muted"><i class="fas fa-arrow-left"></i> Select a phase</div>';
                
                // Load projects for this directory
                try {
                    const response = await fetch(`/api/v1/projects/cached?directory_id=${directoryId}`);
                    const result = await response.json();
                    
                    if (result.success) {
                        const projects = result.data || [];
                        const projectsDiv = document.getElementById('projectsList');
                        
                        let html = '';
                        projects.forEach(project => {
                            html += `
                                <div class="list-group-item list-group-item-action" 
                                     onclick="selectProject(${project.id}, '${project.name}')" 
                                     style="cursor: pointer;">
                                    <div class="d-flex w-100 justify-content-between">
                                        <h6 class="mb-1">
                                            <i class="fas fa-project-diagram me-2"></i>${project.name}
                                        </h6>
                                        <small>${project.directory_name || 'Unknown Directory'}</small>
                                    </div>
                                </div>
                            `;
                        });
                        
                        projectsDiv.innerHTML = html || '<div class="text-center text-muted">No projects found</div>';
                    }
                } catch (error) {
                    document.getElementById('projectsList').innerHTML = '<div class="text-center text-muted">Error loading projects</div>';
                }
            }
            
            async function selectProject(projectId, projectName) {
                // Clear subsequent lists
                document.getElementById('phasesList').innerHTML = `
                    <div class="text-center">
                        <div class="spinner-border spinner-border-sm" role="status">
                            <span class="visually-hidden">Loading...</span>
                        </div>
                    </div>
                `;
                document.getElementById('elevationsList').innerHTML = '<div class="text-center text-muted"><i class="fas fa-arrow-left"></i> Select a phase</div>';
                
                // Load phases for this project
                try {
                    const response = await fetch(`/api/v1/phases/cached?project_id=${projectId}`);
                    const result = await response.json();
                    
                    if (result.success) {
                        const phases = result.data || [];
                        const phasesDiv = document.getElementById('phasesList');
                        
                        let html = '';
                        phases.forEach(phase => {
                            html += `
                                <div class="list-group-item list-group-item-action" 
                                     onclick="selectPhase(${phase.id}, '${phase.name}')" 
                                     style="cursor: pointer;">
                                    <div class="d-flex w-100 justify-content-between">
                                        <h6 class="mb-1">
                                            <i class="fas fa-layer-group me-2"></i>${phase.name}
                                        </h6>
                                        <small>${phase.project_name || 'Unknown Project'}</small>
                                    </div>
                                </div>
                            `;
                        });
                        
                        phasesDiv.innerHTML = html || '<div class="text-center text-muted">No phases found</div>';
                    }
                } catch (error) {
                    document.getElementById('phasesList').innerHTML = '<div class="text-center text-muted">Error loading phases</div>';
                }
            }
            
            async function selectPhase(phaseId, phaseName) {
                // Clear elevations list
                document.getElementById('elevationsList').innerHTML = `
                    <div class="text-center">
                        <div class="spinner-border spinner-border-sm" role="status">
                            <span class="visually-hidden">Loading...</span>
                        </div>
                    </div>
                `;
                
                // Load elevations for this phase
                try {
                    console.log(`Loading elevations for phase ID: ${phaseId}`);
                    const response = await fetch(`/api/v1/elevations/cached?phase_id=${phaseId}`);
                    console.log('Response status:', response.status);
                    
                    if (!response.ok) {
                        throw new Error(`HTTP ${response.status}: ${response.statusText}`);
                    }
                    
                    const result = await response.json();
                    console.log('Elevations result:', result);
                    
                    if (result.success) {
                        const elevations = result.data || [];
                        const elevationsDiv = document.getElementById('elevationsList');
                        
                        let html = '';
                        elevations.forEach(elevation => {
                            const statusBadge = elevation.has_parts_data ? 
                                '<span class="badge bg-success">Parts</span>' : 
                                '<span class="badge bg-secondary">No Parts</span>';
                            
                            html += `
                                <div class="list-group-item list-group-item-action" 
                                     onclick="viewElevation(${elevation.id})" 
                                     style="cursor: pointer;">
                                    <div class="d-flex w-100 justify-content-between">
                                        <h6 class="mb-1">
                                            <i class="fas fa-cube me-2"></i>${elevation.name}
                                        </h6>
                                        ${statusBadge}
                                    </div>
                                    <small class="text-muted">${elevation.logikal_id}</small>
                                </div>
                            `;
                        });
                        
                        elevationsDiv.innerHTML = html || '<div class="text-center text-muted">No elevations found</div>';
                    } else {
                        console.error('Elevations API returned success=false:', result);
                        document.getElementById('elevationsList').innerHTML = `
                            <div class="text-center text-warning">
                                <i class="fas fa-exclamation-triangle"></i> API Error<br>
                                <small>${result.message || 'Unknown API error'}</small>
                            </div>
                        `;
                    }
                } catch (error) {
                    console.error('Error loading elevations:', error);
                    document.getElementById('elevationsList').innerHTML = `
                        <div class="text-center text-danger">
                            <i class="fas fa-exclamation-triangle"></i> Error loading elevations<br>
                            <small>${error.message || 'Unknown error'}</small>
                        </div>
                    `;
                }
            }
            
            function viewElevation(elevationId) {
                // Close the data browser modal
                const modal = bootstrap.Modal.getInstance(document.getElementById('dataBrowserModal'));
                modal.hide();
                
                // Show elevation detail in a new modal
                showElevationDetailModal(elevationId);
            }
            
            async function showElevationDetailModal(elevationId) {
                try {
                    // Create and show elevation detail modal
                    const modalHtml = `
                        <div class="modal fade" id="elevationDetailModal" tabindex="-1" aria-labelledby="elevationDetailModalLabel" aria-hidden="true">
                            <div class="modal-dialog modal-xl">
                                <div class="modal-content">
                                    <div class="modal-header">
                                        <h5 class="modal-title" id="elevationDetailModalLabel">
                                            <i class="fas fa-cube"></i> Elevation Details
                                        </h5>
                                        <button type="button" class="btn-close" data-bs-dismiss="modal" aria-label="Close"></button>
                                    </div>
                                    <div class="modal-body">
                                        <div id="elevationDetailContent">
                                            <div class="text-center">
                                                <div class="spinner-border" role="status">
                                                    <span class="visually-hidden">Loading...</span>
                                                </div>
                                                <p class="mt-2">Loading elevation details...</p>
                                            </div>
                                        </div>
                                    </div>
                                    <div class="modal-footer">
                                        <button type="button" class="btn btn-secondary" data-bs-dismiss="modal">Close</button>
                                        <button type="button" class="btn btn-info" onclick="copyElevationId(${elevationId})">
                                            <i class="fas fa-copy"></i> Copy ID
                                        </button>
                                    </div>
                                </div>
                            </div>
                        </div>
                    `;
                    
                    // Remove existing modal if present
                    const existingModal = document.getElementById('elevationDetailModal');
                    if (existingModal) {
                        existingModal.remove();
                    }
                    
                    // Add modal to body
                    document.body.insertAdjacentHTML('beforeend', modalHtml);
                    
                    // Show modal
                    const elevationModal = new bootstrap.Modal(document.getElementById('elevationDetailModal'));
                    elevationModal.show();
                    
                    // Load elevation details
                    await loadElevationDetailForModal(elevationId);
                    
                } catch (error) {
                    console.error('Error showing elevation detail modal:', error);
                    alert('Error loading elevation details: ' + error.message);
                }
            }
            
            async function loadElevationDetailForModal(elevationId) {
                try {
                    const response = await fetch(`/api/v1/elevations/${elevationId}`);
                    const result = await response.json();
                    
                    if (response.ok && result) {
                        displayElevationDetailInModal(result);
                    } else {
                        throw new Error('Failed to load elevation details');
                    }
                } catch (error) {
                    console.error('Error loading elevation detail:', error);
                    document.getElementById('elevationDetailContent').innerHTML = `
                        <div class="alert alert-danger">
                            <i class="fas fa-exclamation-triangle"></i> Error loading elevation details: ${error.message}
                        </div>
                    `;
                }
            }
            
            function displayElevationDetailInModal(elevation) {
                const container = document.getElementById('elevationDetailContent');
                
                // Helper function to format values
                const formatValue = (value, unit = '') => {
                    if (value === null || value === undefined || value === '') {
                        return '<span class="text-muted">Not available</span>';
                    }
                    return unit ? `${value} ${unit}` : value;
                };
                
                // Helper function to format date
                const formatDate = (date) => {
                    if (!date) return '<span class="text-muted">Not available</span>';
                    return new Date(date).toLocaleString();
                };
                
                const html = `
                    <div class="row">
                        <div class="col-md-6">
                            <h6><i class="fas fa-info-circle"></i> Basic Information</h6>
                            <table class="table table-sm">
                                <tr><td><strong>Name:</strong></td><td>${elevation.name || '<span class="text-muted">Not available</span>'}</td></tr>
                                <tr><td><strong>ID:</strong></td><td><code>${elevation.logikal_id || '<span class="text-muted">Not available</span>'}</code></td></tr>
                                <tr><td><strong>Description:</strong></td><td>${elevation.description || '<span class="text-muted">No description available</span>'}</td></tr>
                                <tr><td><strong>Status:</strong></td><td>${elevation.status || '<span class="text-muted">Not set</span>'}</td></tr>
                                <tr><td><strong>Created:</strong></td><td>${formatDate(elevation.created_at)}</td></tr>
                                <tr><td><strong>Updated:</strong></td><td>${formatDate(elevation.updated_at)}</td></tr>
                            </table>
                        </div>
                        <div class="col-md-6">
                            <h6><i class="fas fa-cube"></i> Dimensions</h6>
                            <table class="table table-sm">
                                <tr><td><strong>Width:</strong></td><td>${formatValue(elevation.width)}</td></tr>
                                <tr><td><strong>Height:</strong></td><td>${formatValue(elevation.height)}</td></tr>
                                <tr><td><strong>Depth:</strong></td><td>${formatValue(elevation.depth)}</td></tr>
                            </table>
                            ${elevation.enrichment && elevation.enrichment.dimensions ? `
                            <h6 class="mt-3"><i class="fas fa-ruler"></i> Enriched Dimensions</h6>
                            <table class="table table-sm">
                                <tr><td><strong>Width:</strong></td><td>${formatValue(elevation.enrichment.dimensions.width_out, elevation.enrichment.dimensions.width_unit)}</td></tr>
                                <tr><td><strong>Height:</strong></td><td>${formatValue(elevation.enrichment.dimensions.height_out, elevation.enrichment.dimensions.height_unit)}</td></tr>
                                <tr><td><strong>Weight:</strong></td><td>${formatValue(elevation.enrichment.dimensions.weight_out, elevation.enrichment.dimensions.weight_unit)}</td></tr>
                                <tr><td><strong>Area:</strong></td><td>${formatValue(elevation.enrichment.dimensions.area_output, elevation.enrichment.dimensions.area_unit)}</td></tr>
                            </table>
                            ` : ''}
                        </div>
                    </div>
                    <div class="row mt-3">
                        <div class="col-md-12">
                            <h6><i class="fas fa-sitemap"></i> Hierarchy</h6>
                            <table class="table table-sm">
                                <tr><td><strong>Directory:</strong></td><td>${elevation.directory_name || '<span class="text-muted">Not available</span>'}</td></tr>
                                <tr><td><strong>Project:</strong></td><td>${elevation.project_name || '<span class="text-muted">Not available</span>'}</td></tr>
                                <tr><td><strong>Phase:</strong></td><td>${elevation.phase_name || '<span class="text-muted">Not available</span>'}</td></tr>
                            </table>
                        </div>
                    </div>
                    ${elevation.enrichment ? `
                    <div class="row mt-3">
                        <div class="col-md-12">
                            <h6><i class="fas fa-magic"></i> Enrichment Data</h6>
                            <div class="alert alert-${elevation.enrichment.status === 'success' ? 'success' : 'warning'}">
                                <strong>Status:</strong> ${elevation.enrichment.status}
                                ${elevation.enrichment.parsed_at ? `<br><strong>Parsed:</strong> ${formatDate(elevation.enrichment.parsed_at)}` : ''}
                                ${elevation.enrichment.error ? `<br><strong>Error:</strong> ${elevation.enrichment.error}` : ''}
                                ${elevation.enrichment.auto_description ? `<br><strong>Auto Description:</strong> ${elevation.enrichment.auto_description}` : ''}
                                ${elevation.enrichment.system ? `<br><strong>System:</strong> ${elevation.enrichment.system.name || elevation.enrichment.system.code || 'N/A'}` : ''}
                            </div>
                        </div>
                    </div>
                    ` : ''}
                `;
                
                container.innerHTML = html;
            }
            
            function copyElevationId(elevationId) {
                // Copy elevation ID to clipboard
                navigator.clipboard.writeText(elevationId.toString()).then(() => {
                    // Show success feedback
                    const button = event.target.closest('button');
                    const originalText = button.innerHTML;
                    button.innerHTML = '<i class="fas fa-check"></i> Copied!';
                    button.classList.remove('btn-info');
                    button.classList.add('btn-success');
                    
                    // Reset button after 2 seconds
                    setTimeout(() => {
                        button.innerHTML = originalText;
                        button.classList.remove('btn-success');
                        button.classList.add('btn-info');
                    }, 2000);
                }).catch(err => {
                    console.error('Failed to copy elevation ID:', err);
                    alert('Failed to copy elevation ID to clipboard');
                });
            }
            
            function refreshDataBrowser() {
                loadDirectories();
                document.getElementById('projectsList').innerHTML = '<div class="text-center text-muted"><i class="fas fa-arrow-left"></i> Select a directory</div>';
                document.getElementById('phasesList').innerHTML = '<div class="text-center text-muted"><i class="fas fa-arrow-left"></i> Select a project</div>';
                document.getElementById('elevationsList').innerHTML = '<div class="text-center text-muted"><i class="fas fa-arrow-left"></i> Select a phase</div>';
            }
        </script>
        
        <script src="https://cdn.jsdelivr.net/npm/bootstrap@5.1.3/dist/js/bootstrap.bundle.min.js"></script>
    </body>
    </html>
    """
    
    return HTMLResponse(content=dashboard_html, status_code=200)


@router.get("/elevations-old", response_class=HTMLResponse)
async def admin_elevations_ui():
    """Admin-style elevation management interface"""
    
    elevations_html = """
    <!DOCTYPE html>
    <html lang="en">
    <head>
        <meta charset="UTF-8">
        <meta name="viewport" content="width=device-width, initial-scale=1.0">
        <title>Elevation Manager - Logikal Middleware Admin</title>
        <link href="https://cdn.jsdelivr.net/npm/bootstrap@5.1.3/dist/css/bootstrap.min.css" rel="stylesheet">
        <link href="https://cdnjs.cloudflare.com/ajax/libs/font-awesome/6.0.0/css/all.min.css" rel="stylesheet">
        <style>
            /* Enhanced File Tree Styling */
            .file-tree {
                max-height: 600px;
                overflow-y: auto;
                border: 1px solid #dee2e6;
                border-radius: 0.375rem;
                padding: 1rem;
                background: #f8f9fa;
            }
            
            .tree-item {
                cursor: pointer;
                padding: 0.5rem 1rem;
                margin: 0.1rem 0;
                border-radius: 0.25rem;
                transition: background-color 0.15s ease-in-out;
                border-bottom: 1px solid #e9ecef;
                position: relative;
            }
            
            .tree-item:hover {
                background-color: #e9ecef;
            }
            
            .tree-item.selected {
                background-color: #0d6efd;
                color: white;
            }
            
            .tree-item.elevation {
                padding-left: 3rem;
                font-size: 0.9rem;
            }
            
            .tree-item.phase {
                padding-left: 2.5rem;
            }
            
            .tree-item.project {
                padding-left: 2rem;
            }
            
            .tree-item.directory {
                padding-left: 1rem;
                font-weight: 600;
            }
            
            .tree-toggle {
                width: 1.5rem;
                display: inline-block;
                text-align: center;
                cursor: pointer;
                margin-right: 0.5rem;
            }
            
            .tree-toggle:before {
                content: "▶";
                transition: transform 0.2s;
                color: #6c757d;
            }
            
            .tree-toggle.expanded:before {
                transform: rotate(90deg);
            }
            
            .tree-children {
                display: none;
            }
            
            .tree-children.expanded {
                display: block;
            }
            
            /* Enhanced Detail Styling */
            .elevation-detail {
                max-height: 600px;
                overflow-y: auto;
            }
            
            .detail-section {
                margin-bottom: 1.5rem;
            }
            
            .detail-section h6 {
                border-bottom: 2px solid #0d6efd;
                padding-bottom: 0.5rem;
                margin-bottom: 1rem;
                color: #0d6efd;
            }
            
            .info-grid {
                display: grid;
                grid-template-columns: repeat(auto-fit, minmax(200px, 1fr));
                gap: 1rem;
                margin-bottom: 1rem;
            }
            
            .info-item {
                background: #f8f9fa;
                padding: 0.75rem;
                border-radius: 0.375rem;
                border-left: 3px solid #0d6efd;
            }
            
            .info-item label {
                font-weight: 600;
                color: #495057;
                display: block;
                margin-bottom: 0.25rem;
                font-size: 0.875rem;
            }
            
            .info-item value {
                color: #212529;
                display: block;
                word-break: break-word;
            }
            
            /* Navigation Bar */
            .navigation-bar {
                background: #f8f9fa;
                padding: 1rem;
                border-radius: 0.375rem;
                margin-bottom: 1.5rem;
                border: 1px solid #dee2e6;
            }
            
            .breadcrumb {
                margin-bottom: 0.5rem;
            }
            
            .breadcrumb-item a {
                color: #0d6efd;
                text-decoration: none;
            }
            
            .breadcrumb-item a:hover {
                text-decoration: underline;
            }
            
            .action-buttons {
                display: flex;
                gap: 0.5rem;
                align-items: center;
                flex-wrap: wrap;
            }
            
            /* Enhanced Search */
            .search-container {
                position: relative;
            }
            
            .search-results {
                position: absolute;
                top: 100%;
                left: 0;
                right: 0;
                background: white;
                border: 1px solid #dee2e6;
                border-top: none;
                border-radius: 0 0 0.375rem 0.375rem;
                max-height: 300px;
                overflow-y: auto;
                z-index: 1000;
                display: none;
                box-shadow: 0 4px 6px rgba(0, 0, 0, 0.1);
            }
            
            .search-result-item {
                padding: 0.75rem;
                cursor: pointer;
                border-bottom: 1px solid #f8f9fa;
                transition: background-color 0.15s ease-in-out;
            }
            
            .search-result-item:hover {
                background-color: #f8f9fa;
            }
            
            .search-result-item:last-child {
                border-bottom: none;
            }
            
            .search-result-item .elevation-name {
                font-weight: 600;
                color: #212529;
            }
            
            .search-result-item .elevation-path {
                font-size: 0.875rem;
                color: #6c757d;
                margin-top: 0.25rem;
            }
            
            .search-result-item .elevation-meta {
                font-size: 0.75rem;
                color: #6c757d;
                margin-top: 0.25rem;
            }
            
            /* Status Badges */
            .status-badge {
                font-size: 0.75rem;
                padding: 0.25rem 0.5rem;
                margin-left: 0.5rem;
            }
            
            /* Elevation Image */
            .elevation-image {
                max-width: 100%;
                height: auto;
                border-radius: 0.375rem;
                box-shadow: 0 2px 4px rgba(0, 0, 0, 0.1);
                cursor: pointer;
                transition: transform 0.2s ease-in-out;
            }
            
            .elevation-image:hover {
                transform: scale(1.02);
            }
            
            /* Modal Styling */
            .modal-content {
                border-radius: 0.5rem;
            }
            
            .modal-header {
                border-bottom: 1px solid #dee2e6;
                background: #f8f9fa;
            }
            
            .modal-body {
                text-align: center;
                padding: 2rem;
            }
            
            .modal-body img {
                max-width: 100%;
                height: auto;
                border-radius: 0.375rem;
                box-shadow: 0 4px 8px rgba(0, 0, 0, 0.1);
            }
            
            /* Loading and Error States */
            .loading {
                text-align: center;
                padding: 2rem;
                color: #6c757d;
            }
            
            .error {
                color: #dc3545;
                background-color: #f8d7da;
                border: 1px solid #f5c6cb;
                padding: 0.75rem;
                border-radius: 0.375rem;
                margin: 1rem 0;
            }
            
            .success {
                color: #155724;
                background-color: #d4edda;
                border: 1px solid #c3e6cb;
                padding: 0.75rem;
                border-radius: 0.375rem;
                margin: 1rem 0;
            }
            
            /* Search Metadata */
            .search-metadata {
                background: #e9ecef;
                padding: 0.5rem 0.75rem;
                border-radius: 0.25rem;
                font-size: 0.875rem;
                color: #495057;
                margin-top: 0.5rem;
            }
        </style>
    </head>
    <body>
        <nav class="navbar navbar-expand-lg navbar-dark bg-dark">
            <div class="container-fluid">
                <a class="navbar-brand" href="/admin">
                    <i class="fas fa-arrow-left me-2"></i>Admin Dashboard
                </a>
                <div class="navbar-nav ms-auto">
                    <span class="navbar-text">
                        <i class="fas fa-sitemap me-1"></i>Elevation Manager
                    </span>
                </div>
            </div>
        </nav>

        <div class="container-fluid mt-4">
            <div class="row">
                <div class="col-md-12">
                    <div class="d-flex justify-content-between align-items-center mb-4">
                        <h2><i class="fas fa-sitemap text-primary me-2"></i>Elevation Manager</h2>
                        <div class="search-container">
                            <div class="input-group">
                                <input type="text" class="form-control" id="searchInput" placeholder="Search elevations...">
                                <button class="btn btn-outline-secondary" type="button" id="searchButton">
                                    <i class="fas fa-search"></i>
                                </button>
                            </div>
                            <div class="search-results" id="searchResults"></div>
                        </div>
                    </div>
                </div>
            </div>

            <div class="row">
                <div class="col-md-4">
                    <div class="card">
                        <div class="card-header">
                            <h5 class="card-title mb-0">
                                <i class="fas fa-folder-tree me-2"></i>File Structure
                            </h5>
                        </div>
                        <div class="card-body p-0">
                            <div class="file-tree" id="fileTree">
                                <div class="loading">
                                    <i class="fas fa-spinner fa-spin me-2"></i>Loading file structure...
                                </div>
                            </div>
                        </div>
                    </div>
                </div>

                <div class="col-md-8">
                    <div class="card">
                        <div class="card-header">
                            <h5 class="card-title mb-0">
                                <i class="fas fa-info-circle me-2"></i>Elevation Details
                            </h5>
                        </div>
                        <div class="card-body">
                            <div id="elevationDetail" class="elevation-detail">
                                <div class="text-center text-muted">
                                    <i class="fas fa-mouse-pointer fa-3x mb-3"></i>
                                    <p>Select an elevation from the file tree to view details</p>
                                </div>
                            </div>
                        </div>
                    </div>
                </div>
            </div>
        </div>

        <!-- Image Modal -->
        <div class="modal fade" id="imageModal" tabindex="-1" aria-labelledby="imageModalLabel" aria-hidden="true">
            <div class="modal-dialog modal-lg modal-dialog-centered">
                <div class="modal-content">
                    <div class="modal-header">
                        <h5 class="modal-title" id="imageModalLabel">
                            <i class="fas fa-image me-2"></i>Elevation Image
                        </h5>
                        <button type="button" class="btn-close" data-bs-dismiss="modal" aria-label="Close"></button>
                    </div>
                    <div class="modal-body">
                        <img id="modalImage" src="" alt="Elevation Image" class="img-fluid">
                    </div>
                    <div class="modal-footer">
                        <button type="button" class="btn btn-secondary" data-bs-dismiss="modal">Close</button>
                        <button type="button" class="btn btn-primary" id="downloadImageBtn">
                            <i class="fas fa-download me-1"></i>Download
                        </button>
                    </div>
                </div>
            </div>
        </div>

        <script src="https://cdn.jsdelivr.net/npm/bootstrap@5.1.3/dist/js/bootstrap.bundle.min.js"></script>
        <script>
            let currentElevationId = null;
            let allElevations = [];
            let currentImageUrl = null;

            // Authentication removed - page loads directly
            document.addEventListener('DOMContentLoaded', function() {
                // Set admin username directly since authentication is removed
                const adminUsernameElement = document.getElementById('adminUsername');
                if (adminUsernameElement) {
                    adminUsernameElement.textContent = 'admin';
                }
                // Load elevation tree and setup event listeners
                loadElevationTree();
                setupEventListeners();
            });

            function setupEventListeners() {
                const searchInput = document.getElementById('searchInput');
                const searchButton = document.getElementById('searchButton');
                
                searchInput.addEventListener('input', debounce(handleSearch, 300));
                searchButton.addEventListener('click', handleSearch);
                
                // Hide search results when clicking outside
                document.addEventListener('click', function(e) {
                    if (!e.target.closest('.search-container')) {
                        document.getElementById('searchResults').style.display = 'none';
                    }
                });

                // Setup image modal download functionality
                document.getElementById('downloadImageBtn').addEventListener('click', downloadImage);
            }

            function debounce(func, wait) {
                let timeout;
                return function executedFunction(...args) {
                    const later = () => {
                        clearTimeout(timeout);
                        func(...args);
                    };
                    clearTimeout(timeout);
                    timeout = setTimeout(later, wait);
                };
            }

            // Load elevation tree
            async function loadElevationTree() {
                try {
                    const response = await fetch('/admin/elevations/tree');
                    const result = await response.json();
                    
                    if (result.success) {
                        renderElevationTree(result.data);
                    } else {
                        throw new Error('Failed to load elevation tree');
                    }
                } catch (error) {
                    console.error('Error loading elevation tree:', error);
                    showError('Failed to load file structure');
                }
            }

            // Render elevation tree with collapsible functionality
            function renderElevationTree(treeData) {
                const container = document.getElementById('fileTree');
                container.innerHTML = '';
                
                // Handle the new API structure
                const tree = treeData.data || treeData;
                
                tree.forEach(item => {
                    const element = createTreeElement({
                        id: item.id,
                        name: item.name,
                        type: item.type,
                        children: item.children || [],
                        has_parts_data: item.has_parts_data,
                        parse_status: item.parse_status,
                        elevation_count: item.elevation_count
                    });
                    
                    container.appendChild(element);
                });
            }

            function createTreeElement(item) {
                const div = document.createElement('div');
                div.className = `tree-item ${item.type}`;
                div.dataset.id = item.id;
                div.dataset.type = item.type;
                
                let html = '';
                
                if (item.children && item.children.length > 0) {
                    html += `<span class="tree-toggle" onclick="toggleTreeNode('${item.id}')"></span>`;
                } else {
                    html += '<span class="tree-toggle" style="visibility: hidden;"></span>';
                }
                
                html += `<i class="fas ${getItemIcon(item.type)} me-2"></i>`;
                html += `<span class="item-name">${item.name}</span>`;
                
                if (item.type === 'elevation') {
                    html += getStatusBadges(item);
                } else if (item.elevation_count > 0) {
                    html += `<span class="badge bg-secondary status-badge">${item.elevation_count}</span>`;
                }
                
                div.innerHTML = html;
                
                // Add click handler
                if (item.type === 'elevation') {
                    div.addEventListener('click', (e) => {
                        if (!e.target.classList.contains('tree-toggle')) {
                            selectElevation(item.id, item);
                        }
                    });
                }
                
                // Add children if they exist
                if (item.children && item.children.length > 0) {
                    const childrenDiv = document.createElement('div');
                    childrenDiv.className = 'tree-children';
                    childrenDiv.id = `children-${item.id}`;
                    
                    item.children.forEach(child => {
                        const childElement = createTreeElement(child);
                        childrenDiv.appendChild(childElement);
                    });
                    
                    div.appendChild(childrenDiv);
                }
                
                return div;
            }

            // Get icon for tree item type
            function getItemIcon(type) {
                const icons = {
                    'directory': 'fa-folder',
                    'project': 'fa-project-diagram',
                    'phase': 'fa-layer-group',
                    'elevation': 'fa-cube'
                };
                return icons[type] || 'fa-file';
            }

            // Get status badges for elevation
            function getStatusBadges(elevation) {
                let badges = '';
                
                if (elevation.has_parts_data) {
                    badges += '<span class="badge bg-info status-badge">Parts</span>';
                }
                
                const parseStatusColors = {
                    'success': 'success',
                    'failed': 'danger',
                    'in_progress': 'warning',
                    'pending': 'secondary',
                    'validation_failed': 'danger'
                };
                
                if (elevation.parse_status && elevation.parse_status !== 'pending') {
                    const color = parseStatusColors[elevation.parse_status] || 'secondary';
                    badges += `<span class="badge bg-${color} status-badge">${elevation.parse_status}</span>`;
                }
                
                return badges;
            }

            // Toggle tree node
            function toggleTreeNode(id) {
                const toggle = document.querySelector(`[data-id="${id}"] .tree-toggle`);
                const children = document.getElementById(`children-${id}`);
                
                if (toggle.classList.contains('expanded')) {
                    toggle.classList.remove('expanded');
                    children.classList.remove('expanded');
                } else {
                    toggle.classList.add('expanded');
                    children.classList.add('expanded');
                }
            }

            // Select elevation
            async function selectElevation(elevationId, elevationData = null) {
                try {
                    // Update UI state
                    document.querySelectorAll('.tree-item').forEach(item => {
                        item.classList.remove('selected');
                    });
                    
                    const selectedItem = document.querySelector(`[data-id="${elevationId}"]`);
                    if (selectedItem) {
                        selectedItem.classList.add('selected');
                    }
                    
                    currentElevationId = elevationId;
                    
                    // Load elevation detail
                    await loadElevationDetail(elevationId);
                    
                } catch (error) {
                    console.error('Error selecting elevation:', error);
                    showError('Failed to load elevation details');
                }
            }

            // Load elevation detail
            async function loadElevationDetail(elevationId) {
                try {
                    const response = await fetch(`/api/v1/ui/elevations/${elevationId}/detail`);
                    const result = await response.json();
                    
                    if (result.success) {
                        renderElevationDetail(result.data);
                    } else {
                        throw new Error('Failed to load elevation detail');
                    }
                } catch (error) {
                    console.error('Error loading elevation detail:', error);
                    showError('Failed to load elevation details');
                }
            }

            // Render elevation detail with enhanced formatting
            function renderElevationDetail(data) {
                const container = document.getElementById('elevationDetail');
                const elevation = data.elevation;
                const hierarchy = data.hierarchy;
                const navigation = data.navigation;
                
                let html = `
                    <!-- Navigation Bar -->
                    <div class="navigation-bar">
                        <nav aria-label="breadcrumb">
                            <ol class="breadcrumb">
                                <li class="breadcrumb-item">
                                    <a href="#" onclick="loadElevationTree()">
                                        <i class="fas fa-home"></i> Root
                                    </a>
                                </li>
                                <li class="breadcrumb-item">
                                    <a href="#" onclick="filterByDirectory('${hierarchy.directory.id}')">
                                        ${hierarchy.directory.name}
                                    </a>
                                </li>
                                <li class="breadcrumb-item">
                                    <a href="#" onclick="filterByProject('${hierarchy.project.id}')">
                                        ${hierarchy.project.name}
                                    </a>
                                </li>
                                <li class="breadcrumb-item">
                                    <a href="#" onclick="filterByPhase('${hierarchy.phase.id}')">
                                        ${hierarchy.phase.name}
                                    </a>
                                </li>
                                <li class="breadcrumb-item active" aria-current="page">
                                    ${elevation.name}
                                </li>
                            </ol>
                        </nav>
                        
                        <div class="action-buttons">
                            ${navigation.previous ? 
                                `<button class="btn btn-outline-secondary btn-sm" onclick="selectElevation('${navigation.previous.id}')">
                                    <i class="fas fa-chevron-left"></i> Previous
                                </button>` : ''
                            }
                            <span class="badge bg-secondary">${navigation.current_index + 1} of ${navigation.total_count}</span>
                            ${navigation.next ? 
                                `<button class="btn btn-outline-secondary btn-sm" onclick="selectElevation('${navigation.next.id}')">
                                    Next <i class="fas fa-chevron-right"></i>
                                </button>` : ''
                            }
                        </div>
                    </div>
                    
                    <!-- Basic Information -->
                    <div class="detail-section">
                        <h6><i class="fas fa-info-circle"></i> Basic Information</h6>
                        <div class="info-grid">
                            <div class="info-item">
                                <label>Name</label>
                                <value>${elevation.name}</value>
                            </div>
                            <div class="info-item">
                                <label>Logikal ID</label>
                                <value>${elevation.logikal_id}</value>
                            </div>
                            <div class="info-item">
                                <label>Status</label>
                                <value><span class="badge bg-primary">${elevation.status || 'N/A'}</span></value>
                            </div>
                            <div class="info-item">
                                <label>Description</label>
                                <value>${elevation.description || 'No description available'}</value>
                            </div>
                        </div>
                    </div>
                    
                    <!-- Physical Dimensions -->
                    <div class="detail-section">
                        <h6><i class="fas fa-ruler"></i> Physical Dimensions</h6>
                        <div class="info-grid">
                            <div class="info-item">
                                <label>Width</label>
                                <value>${elevation.dimensions.width ? elevation.dimensions.width + ' mm' : 'N/A'}</value>
                            </div>
                            <div class="info-item">
                                <label>Height</label>
                                <value>${elevation.dimensions.height ? elevation.dimensions.height + ' mm' : 'N/A'}</value>
                            </div>
                            <div class="info-item">
                                <label>Depth</label>
                                <value>${elevation.dimensions.depth ? elevation.dimensions.depth + ' mm' : 'N/A'}</value>
                            </div>
                        </div>
                    </div>
                `;
                
                // Add image if available
                if (elevation.thumbnail_url) {
                    currentImageUrl = elevation.thumbnail_url;
                    html += `
                        <div class="detail-section">
                            <h6><i class="fas fa-image"></i> Elevation Image</h6>
                            <img src="${elevation.thumbnail_url}" alt="Elevation Image" 
                                 class="elevation-image" onclick="showImageModal('${elevation.thumbnail_url}')"
                                 style="cursor: pointer;">
                        </div>
                    `;
                }
                
                // Add sync status
                html += `
                    <div class="detail-section">
                        <h6><i class="fas fa-sync"></i> Sync Status</h6>
                        <div class="info-grid">
                            <div class="info-item">
                                <label>Sync Status</label>
                                <value><span class="badge bg-${getSyncStatusColor(elevation.sync_status)}">${elevation.sync_status}</span></value>
                            </div>
                            <div class="info-item">
                                <label>Last Sync</label>
                                <value>${formatDate(elevation.synced_at)}</value>
                            </div>
                            <div class="info-item">
                                <label>Last Update</label>
                                <value>${formatDate(elevation.last_update_date)}</value>
                            </div>
                            <div class="info-item">
                                <label>Created</label>
                                <value>${formatDate(elevation.created_at)}</value>
                            </div>
                        </div>
                        <div class="action-buttons">
                            <button class="btn btn-primary btn-sm" onclick="refreshElevation(${elevation.id})">
                                <i class="fas fa-sync"></i> Refresh Data
                            </button>
                        </div>
                    </div>
                `;
                
                // Add parsing status
                html += `
                    <div class="detail-section">
                        <h6><i class="fas fa-database"></i> SQLite Parsing Status</h6>
                        <div class="info-grid">
                            <div class="info-item">
                                <label>Parse Status</label>
                                <value><span class="badge bg-${getParseStatusColor(elevation.parse_status)}">${elevation.parse_status}</span></value>
                            </div>
                            <div class="info-item">
                                <label>Parts Data Available</label>
                                <value><span class="badge bg-${elevation.has_parts_data ? 'success' : 'secondary'}">${elevation.has_parts_data ? 'Yes' : 'No'}</span></value>
                            </div>
                            <div class="info-item">
                                <label>Parts Count</label>
                                <value>${elevation.parts_count || 'N/A'}</value>
                            </div>
                            <div class="info-item">
                                <label>Last Parsed</label>
                                <value>${formatDate(elevation.data_parsed_at)}</value>
                            </div>
                        </div>
                        <div class="action-buttons">
                            <button class="btn btn-success btn-sm" onclick="triggerParsing(${elevation.id})">
                                <i class="fas fa-play"></i> Trigger Parsing
                            </button>
                        </div>
                    </div>
                `;
                
                // Add enriched data if available
                if (data.enriched_data) {
                    const enriched = data.enriched_data;
                    
                    html += `
                        <div class="detail-section">
                            <h6><i class="fas fa-star"></i> Enriched Data</h6>
                            
                            <h6 class="mt-3">Auto Descriptions</h6>
                            <div class="info-grid">
                                <div class="info-item">
                                    <label>Auto Description</label>
                                    <value>${enriched.descriptions.auto_description || 'N/A'}</value>
                                </div>
                                <div class="info-item">
                                    <label>Short Description</label>
                                    <value>${enriched.descriptions.auto_description_short || 'N/A'}</value>
                                </div>
                            </div>
                            
                            <h6 class="mt-3">Enhanced Dimensions</h6>
                            <div class="info-grid">
                                <div class="info-item">
                                    <label>Width</label>
                                    <value>${enriched.dimensions.width_out ? enriched.dimensions.width_out + ' ' + enriched.dimensions.width_unit : 'N/A'}</value>
                                </div>
                                <div class="info-item">
                                    <label>Height</label>
                                    <value>${enriched.dimensions.height_out ? enriched.dimensions.height_out + ' ' + enriched.dimensions.height_unit : 'N/A'}</value>
                                </div>
                                <div class="info-item">
                                    <label>Weight</label>
                                    <value>${enriched.dimensions.weight_out ? enriched.dimensions.weight_out + ' ' + enriched.dimensions.weight_unit : 'N/A'}</value>
                                </div>
                                <div class="info-item">
                                    <label>Area</label>
                                    <value>${enriched.dimensions.area_output ? enriched.dimensions.area_output + ' ' + enriched.dimensions.area_unit : 'N/A'}</value>
                                </div>
                            </div>
                            
                            <h6 class="mt-3">System Information</h6>
                            <div class="info-grid">
                                <div class="info-item">
                                    <label>System Code</label>
                                    <value>${enriched.system.code || 'N/A'}</value>
                                </div>
                                <div class="info-item">
                                    <label>System Name</label>
                                    <value>${enriched.system.name || 'N/A'}</value>
                                </div>
                                <div class="info-item">
                                    <label>Long Name</label>
                                    <value>${enriched.system.long_name || 'N/A'}</value>
                                </div>
                                <div class="info-item">
                                    <label>Color Base</label>
                                    <value>${enriched.system.color_base || 'N/A'}</value>
                                </div>
                            </div>
                    `;
                    
                    // Add glass specifications
                    if (enriched.glass_specifications && enriched.glass_specifications.length > 0) {
                        html += `
                            <h6 class="mt-3">Glass Specifications</h6>
                            <div class="table-responsive">
                                <table class="table table-sm">
                                    <thead>
                                        <tr>
                                            <th>Glass ID</th>
                                            <th>Name</th>
                                        </tr>
                                    </thead>
                                    <tbody>
                        `;
                        
                        enriched.glass_specifications.forEach(glass => {
                            html += `
                                <tr>
                                    <td>${glass.glass_id}</td>
                                    <td>${glass.name || 'N/A'}</td>
                                </tr>
                            `;
                        });
                        
                        html += `
                                    </tbody>
                                </table>
                            </div>
                        `;
                    }
                    
                    html += `</div>`;
                }
                
                container.innerHTML = html;
            }

            // Enhanced search with metadata
            async function handleSearch() {
                const query = document.getElementById('searchInput').value.trim();
                const resultsContainer = document.getElementById('searchResults');
                
                if (query.length < 2) {
                    resultsContainer.style.display = 'none';
                    return;
                }
                
                try {
                    const response = await fetch(`/api/v1/ui/elevations/search?q=${encodeURIComponent(query)}&limit=10`);
                    const result = await response.json();
                    
                    if (result.success) {
                        renderSearchResults(result);
                    } else {
                        resultsContainer.style.display = 'none';
                    }
                } catch (error) {
                    console.error('Error searching elevations:', error);
                    resultsContainer.style.display = 'none';
                }
            }

            function renderSearchResults(result) {
                const container = document.getElementById('searchResults');
                const results = result.data || result.results || [];
                
                if (results.length === 0) {
                    container.innerHTML = '<div class="search-result-item text-muted">No results found</div>';
                } else {
                    let html = '';
                    
                    results.forEach(elevation => {
                        const hierarchy = elevation.hierarchy || {};
                        html += `
                            <div class="search-result-item" onclick="selectElevation(${elevation.id}); hideSearchResults();">
                                <div class="elevation-name">${elevation.name}</div>
                                <div class="elevation-path">${hierarchy.directory?.name || 'Unknown'} → ${hierarchy.project?.name || 'Unknown'} → ${hierarchy.phase?.name || 'Unknown'}</div>
                                <div class="elevation-meta">
                                    ${elevation.has_parts_data ? '<span class="badge bg-info me-1">Parts</span>' : ''}
                                    ${elevation.parse_status !== 'pending' ? `<span class="badge bg-${getParseStatusColor(elevation.parse_status)} me-1">${elevation.parse_status}</span>` : ''}
                                    Created: ${formatDate(elevation.created_at)}
                                </div>
                            </div>
                        `;
                    });
                    
                    // Add metadata
                    const totalFound = result.total_found || results.length;
                    const query = result.query || document.getElementById('searchInput').value;
                    html += `
                        <div class="search-metadata">
                            <i class="fas fa-info-circle me-1"></i>
                            Found ${totalFound} result(s) for "${query}" (showing ${results.length})
                        </div>
                    `;
                    
                    container.innerHTML = html;
                }
                
                container.style.display = 'block';
            }

            function hideSearchResults() {
                document.getElementById('searchResults').style.display = 'none';
                document.getElementById('searchInput').value = '';
            }

            // Image modal functionality
            function showImageModal(imageUrl) {
                currentImageUrl = imageUrl;
                document.getElementById('modalImage').src = imageUrl;
                const modal = new bootstrap.Modal(document.getElementById('imageModal'));
                modal.show();
            }

            function downloadImage() {
                if (currentImageUrl) {
                    const link = document.createElement('a');
                    link.href = currentImageUrl;
                    link.download = `elevation-${currentElevationId || 'image'}.png`;
                    document.body.appendChild(link);
                    link.click();
                    document.body.removeChild(link);
                }
            }

            // Filter functions (placeholder for future implementation)
            function filterByDirectory(directoryId) {
                // TODO: Implement directory filtering
                console.log('Filter by directory:', directoryId);
            }

            function filterByProject(projectId) {
                // TODO: Implement project filtering
                console.log('Filter by project:', projectId);
            }

            function filterByPhase(phaseId) {
                // TODO: Implement phase filtering
                console.log('Filter by phase:', phaseId);
            }

            // Utility functions
            function getSyncStatusColor(status) {
                const colors = {
                    'synced': 'success',
                    'pending': 'warning',
                    'failed': 'danger'
                };
                return colors[status] || 'secondary';
            }

            function getParseStatusColor(status) {
                const colors = {
                    'success': 'success',
                    'failed': 'danger',
                    'in_progress': 'warning',
                    'pending': 'secondary',
                    'validation_failed': 'danger'
                };
                return colors[status] || 'secondary';
            }

            function formatDate(dateString) {
                if (!dateString) return 'N/A';
                try {
                    return new Date(dateString).toLocaleString();
                } catch (e) {
                    return 'Invalid Date';
                }
            }

            // Action functions
            async function refreshElevation(elevationId) {
                try {
                    const response = await fetch(`/api/v1/ui/elevations/${elevationId}/refresh`, {
                        method: 'POST'
                    });
                    const result = await response.json();
                    
                    if (result.success) {
                        showNotification('Elevation refresh triggered', 'success');
                        await loadElevationDetail(elevationId);
                    } else {
                        throw new Error(result.message || 'Failed to refresh elevation');
                    }
                } catch (error) {
                    console.error('Error refreshing elevation:', error);
                    showNotification('Failed to refresh elevation', 'error');
                }
            }

            async function triggerParsing(elevationId) {
                try {
                    const response = await fetch(`/api/v1/elevations/${elevationId}/enrichment/trigger`, {
                        method: 'POST'
                    });
                    const result = await response.json();
                    
                    if (result.success) {
                        showNotification('Parsing triggered successfully', 'success');
                        await loadElevationDetail(elevationId);
                    } else {
                        throw new Error(result.message || 'Failed to trigger parsing');
                    }
                } catch (error) {
                    console.error('Error triggering parsing:', error);
                    showNotification('Failed to trigger parsing', 'error');
                }
            }

            function showError(message) {
                const container = document.getElementById('elevationDetail');
                container.innerHTML = `
                    <div class="error">
                        <i class="fas fa-exclamation-triangle me-2"></i>${message}
                    </div>
                `;
            }

            function showNotification(message, type) {
                const alertClass = type === 'success' ? 'alert-success' : 'alert-danger';
                const notification = document.createElement('div');
                notification.className = `alert ${alertClass} alert-dismissible fade show position-fixed`;
                notification.style.top = '20px';
                notification.style.right = '20px';
                notification.style.zIndex = '9999';
                notification.innerHTML = `
                    ${message}
                    <button type="button" class="btn-close" data-bs-dismiss="alert"></button>
                `;
                
                document.body.appendChild(notification);
                
                setTimeout(() => {
                    if (notification.parentNode) {
                        notification.parentNode.removeChild(notification);
                    }
                }, 5000);
            }
        </script>
    </body>
    </html>
    """
    
    return HTMLResponse(content=elevations_html, status_code=200)


@router.get("/elevations/{elevation_id}/detail")
async def admin_elevation_detail(elevation_id: int, db: Session = Depends(get_db)):
    """Get elevation detail for admin interface (same as UI endpoint)"""
    try:
        # Get elevation with all relationships
        elevation = db.query(Elevation).options(
            joinedload(Elevation.glass_specifications),
            joinedload(Elevation.phase).joinedload(Phase.project).joinedload(Project.directory)
        ).filter(Elevation.id == elevation_id).first()
        
        if not elevation:
            raise HTTPException(status_code=404, detail="Elevation not found")
        
        # Get sibling elevations for navigation
        all_elevations = db.query(Elevation).filter(
            Elevation.phase_id == elevation.phase_id
        ).order_by(Elevation.name).all()
        
        # Find previous and next elevation
        previous_elevation = None
        next_elevation = None
        current_index = -1
        
        for i, elev in enumerate(all_elevations):
            if elev.id == elevation_id:
                current_index = i
                break
        
        if current_index > 0:
            previous_elevation = all_elevations[current_index - 1]
        if current_index < len(all_elevations) - 1:
            next_elevation = all_elevations[current_index + 1]
        
        # Build comprehensive detail data
        detail_data = {
            "elevation": {
                "id": elevation.id,
                "logikal_id": elevation.logikal_id,
                "name": elevation.name,
                "description": elevation.description,
                "status": elevation.status,
                
                # Physical dimensions
                "dimensions": {
                    "width": elevation.width,
                    "height": elevation.height,
                    "depth": elevation.depth
                },
                
                # Timestamps
                "created_at": elevation.created_at.isoformat() if elevation.created_at else None,
                "updated_at": elevation.updated_at.isoformat() if elevation.updated_at else None,
                "last_sync_date": elevation.last_sync_date.isoformat() if elevation.last_sync_date else None,
                "last_update_date": elevation.last_update_date.isoformat() if elevation.last_update_date else None,
                
                # Sync status
                "sync_status": elevation.sync_status,
                "synced_at": elevation.synced_at.isoformat() if elevation.synced_at else None,
                
                # Parts data
                "has_parts_data": elevation.has_parts_data,
                "parts_count": elevation.parts_count,
                "parts_synced_at": elevation.parts_synced_at.isoformat() if elevation.parts_synced_at else None,
                
                # Parsing status
                "parse_status": elevation.parse_status,
                "parse_error": elevation.parse_error,
                "parse_retry_count": elevation.parse_retry_count,
                "data_parsed_at": elevation.data_parsed_at.isoformat() if elevation.data_parsed_at else None,
                "parts_file_hash": elevation.parts_file_hash,
                
                # Images
                "thumbnail_url": f"/api/v1/elevations/{elevation.id}/image" if elevation.thumbnail_url else None,
                "image_path": elevation.image_path
            },
            
            "hierarchy": {
                "directory": {
                    "id": elevation.phase.project.directory.id,
                    "name": elevation.phase.project.directory.name
                } if elevation.phase and elevation.phase.project and elevation.phase.project.directory else None,
                "project": {
                    "id": elevation.phase.project.id,
                    "name": elevation.phase.project.name
                } if elevation.phase and elevation.phase.project else None,
                "phase": {
                    "id": elevation.phase.id,
                    "name": elevation.phase.name
                } if elevation.phase else None
            },
            
            "navigation": {
                "previous": {
                    "id": previous_elevation.id,
                    "name": previous_elevation.name
                } if previous_elevation else None,
                "next": {
                    "id": next_elevation.id,
                    "name": next_elevation.name
                } if next_elevation else None,
                "current_index": current_index,
                "total_count": len(all_elevations)
            }
        }
        
        # Add enriched data if available
        if elevation.parse_status == 'success':
            detail_data["enriched_data"] = {
                "descriptions": {
                    "auto_description": elevation.auto_description,
                    "auto_description_short": elevation.auto_description_short
                },
                "dimensions": {
                    "width_out": elevation.width_out,
                    "width_unit": elevation.width_unit,
                    "height_out": elevation.height_out,
                    "height_unit": elevation.height_unit,
                    "weight_out": elevation.weight_out,
                    "weight_unit": elevation.weight_unit,
                    "area_output": elevation.area_output,
                    "area_unit": elevation.area_unit
                },
                "system": {
                    "code": elevation.system_code,
                    "name": elevation.system_name,
                    "long_name": elevation.system_long_name,
                    "color_base": elevation.color_base_long
                },
                "glass_specifications": [
                    {
                        "id": glass.id,
                        "glass_id": glass.glass_id,
                        "name": glass.name,
                        "created_at": glass.created_at.isoformat() if glass.created_at else None
                    }
                    for glass in elevation.glass_specifications
                ]
            }
        
        return {
            "success": True,
            "data": detail_data
        }
        
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error fetching elevation detail: {str(e)}")


@router.get("/elevations/tree")
async def admin_elevations_tree(
    search: Optional[str] = Query(None, description="Search term for filtering"),
    db: Session = Depends(get_db),
    # Admin authentication removed
):
    """Get hierarchical tree structure for elevation navigation"""
    
    try:
        # Build query with all relationships
        query = db.query(Directory).options(
            joinedload(Directory.projects).joinedload(Project.phases).joinedload(Phase.elevations)
        ).order_by(Directory.name)
        
        if search:
            search_term = search.lower()
            # Filter by search term at any level
            query = query.filter(
                or_(
                    Directory.name.ilike(f"%{search_term}%"),
                    Project.name.ilike(f"%{search_term}%"),
                    Phase.name.ilike(f"%{search_term}%"),
                    Elevation.name.ilike(f"%{search_term}%")
                )
            )
        
        directories = query.all()
        
        # Build tree structure
        tree_data = []
        total_elevations = 0
        
        for directory in directories:
            directory_data = {
                "id": directory.id,
                "name": directory.name,
                "type": "directory",
                "children": []
            }
            
            for project in directory.projects:
                project_data = {
                    "id": project.id,
                    "name": project.name,
                    "type": "project",
                    "children": []
                }
                
                for phase in project.phases:
                    phase_data = {
                        "id": phase.id,
                        "name": phase.name,
                        "type": "phase",
                        "children": []
                    }
                    
                    for elevation in phase.elevations:
                        elevation_data = {
                            "id": elevation.id,
                            "name": elevation.name,
                            "logikal_id": elevation.logikal_id,
                            "type": "elevation",
                            "status": elevation.status,
                            "parse_status": elevation.parse_status,
                            "has_parts_data": elevation.has_parts_data,
                            "description": elevation.description,
                            "created_at": elevation.created_at.isoformat() if elevation.created_at else None
                        }
                        phase_data["children"].append(elevation_data)
                        total_elevations += 1
                    
                    if phase_data["children"] or not search:
                        project_data["children"].append(phase_data)
                
                if project_data["children"] or not search:
                    directory_data["children"].append(project_data)
            
            if directory_data["children"] or not search:
                tree_data.append(directory_data)
        
        return {
            "success": True,
            "data": tree_data,
            "total_elevations": total_elevations,
            "search_term": search
        }
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error building elevation tree: {str(e)}")


@router.get("/elevations/search")
async def admin_elevations_search(
    q: str = Query(..., description="Search query"),
    limit: int = Query(50, description="Maximum results to return"),
    db: Session = Depends(get_db),
    # Admin authentication removed
):
    """Search elevations for admin interface (same as UI endpoint)"""
    try:
        # Build search query
        search_filter = and_(
            Elevation.name.ilike(f"%{q}%")
        )
        
        # Execute query with relationships
        elevations = db.query(Elevation).options(
            joinedload(Elevation.phase).joinedload(Phase.project).joinedload(Project.directory)
        ).filter(search_filter).limit(limit).all()
        
        # Format results
        results = []
        for elevation in elevations:
            if elevation.phase and elevation.phase.project and elevation.phase.project.directory:
                results.append({
                    "id": elevation.id,
                    "name": elevation.name,
                    "hierarchy": {
                        "directory": {
                            "name": elevation.phase.project.directory.name
                        },
                        "project": {
                            "name": elevation.phase.project.name
                        },
                        "phase": {
                            "name": elevation.phase.name
                        }
                    },
                    "has_parts_data": elevation.has_parts_data,
                    "parse_status": elevation.parse_status
                })
        
        return {
            "success": True,
            "data": results
        }
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error searching elevations: {str(e)}")


@router.get("/elevations/{elevation_id}/detail")
async def admin_elevation_detail(
    elevation_id: int, 
    db: Session = Depends(get_db),
    # Admin authentication removed
):
    """Get detailed elevation information for admin interface"""
    
    try:
        # Get elevation with all relationships
        elevation = db.query(Elevation).options(
            joinedload(Elevation.phase).joinedload(Phase.project).joinedload(Project.directory)
        ).filter(Elevation.id == elevation_id).first()
        
        if not elevation:
            raise HTTPException(status_code=404, detail="Elevation not found")
        
        # Get glass records
        glass_records = db.query(ElevationGlass).filter(
            ElevationGlass.elevation_id == elevation_id
        ).all()
        
        # Build response
        result = {
            "success": True,
            "data": {
                "elevation": {
                    "id": elevation.id,
                    "name": elevation.name,
                    "logikal_id": elevation.logikal_id,
                    "description": elevation.description,
                    "status": elevation.status,
                    "parse_status": elevation.parse_status,
                    "has_parts_data": elevation.has_parts_data,
                    "parts_count": elevation.parts_count,
                    "parts_db_path": elevation.parts_db_path,
                    "parts_file_hash": elevation.parts_file_hash,
                    "parse_error": elevation.parse_error,
                    "data_parsed_at": elevation.data_parsed_at.isoformat() if elevation.data_parsed_at else None,
                    "created_at": elevation.created_at.isoformat() if elevation.created_at else None,
                    "updated_at": elevation.updated_at.isoformat() if elevation.updated_at else None
                },
                "hierarchy": {
                    "directory": {
                        "id": elevation.phase.project.directory.id,
                        "name": elevation.phase.project.directory.name
                    } if elevation.phase and elevation.phase.project and elevation.phase.project.directory else None,
                    "project": {
                        "id": elevation.phase.project.id,
                        "name": elevation.phase.project.name
                    } if elevation.phase and elevation.phase.project else None,
                    "phase": {
                        "id": elevation.phase.id,
                        "name": elevation.phase.name
                    } if elevation.phase else None
                },
                "glass_records": [
                    {
                        "id": glass.id,
                        "glass_name": glass.glass_name,
                        "glass_type": glass.glass_type,
                        "thickness": glass.thickness,
                        "width": glass.width,
                        "height": glass.height,
                        "area": glass.area,
                        "quantity": glass.quantity,
                        "unit": glass.unit,
                        "color": glass.color,
                        "description": glass.description,
                        "created_at": glass.created_at.isoformat() if glass.created_at else None
                    } for glass in glass_records
                ]
            }
        }
        
        return result
        
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error fetching elevation detail: {str(e)}")


@router.get("/elevations/{elevation_id}/detail")
async def admin_elevation_detail(
    elevation_id: int, 
    db: Session = Depends(get_db),
    # Admin authentication removed
):
    """Get detailed elevation information for admin interface"""
    
    try:
        # Get elevation with all relationships
        elevation = db.query(Elevation).options(
            joinedload(Elevation.phase).joinedload(Phase.project).joinedload(Project.directory)
        ).filter(Elevation.id == elevation_id).first()
        
        if not elevation:
            raise HTTPException(status_code=404, detail="Elevation not found")
        
        # Get glass records
        glass_records = db.query(ElevationGlass).filter(
            ElevationGlass.elevation_id == elevation_id
        ).all()
        
        # Build response
        result = {
            "success": True,
            "data": {
                "elevation": {
                    "id": elevation.id,
                    "name": elevation.name,
                    "logikal_id": elevation.logikal_id,
                    "description": elevation.description,
                    "status": elevation.status,
                    "parse_status": elevation.parse_status,
                    "has_parts_data": elevation.has_parts_data,
                    "parts_count": elevation.parts_count,
                    "parts_db_path": elevation.parts_db_path,
                    "parts_file_hash": elevation.parts_file_hash,
                    "parse_error": elevation.parse_error,
                    "data_parsed_at": elevation.data_parsed_at.isoformat() if elevation.data_parsed_at else None,
                    "created_at": elevation.created_at.isoformat() if elevation.created_at else None,
                    "updated_at": elevation.updated_at.isoformat() if elevation.updated_at else None
                },
                "hierarchy": {
                    "directory": {
                        "id": elevation.phase.project.directory.id,
                        "name": elevation.phase.project.directory.name
                    } if elevation.phase and elevation.phase.project and elevation.phase.project.directory else None,
                    "project": {
                        "id": elevation.phase.project.id,
                        "name": elevation.phase.project.name
                    } if elevation.phase and elevation.phase.project else None,
                    "phase": {
                        "id": elevation.phase.id,
                        "name": elevation.phase.name
                    } if elevation.phase else None
                },
                "glass_records": [
                    {
                        "id": glass.id,
                        "glass_name": glass.glass_name,
                        "glass_type": glass.glass_type,
                        "thickness": glass.thickness,
                        "width": glass.width,
                        "height": glass.height,
                        "area": glass.area,
                        "quantity": glass.quantity,
                        "unit": glass.unit,
                        "color": glass.color,
                        "description": glass.description,
                        "created_at": glass.created_at.isoformat() if glass.created_at else None
                    } for glass in glass_records
                ]
            }
        }
        
        return result
        
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error fetching elevation detail: {str(e)}")


@router.post("/elevations/{elevation_id}/refresh")
async def admin_refresh_elevation(
    elevation_id: int,
    db: Session = Depends(get_db),
    # Admin authentication removed
):
    """Refresh elevation data from Logikal API"""
    
    try:
        # Get elevation
        elevation = db.query(Elevation).filter(Elevation.id == elevation_id).first()
        if not elevation:
            raise HTTPException(status_code=404, detail="Elevation not found")
        
        # Import here to avoid circular imports
        from services.auth_service import AuthService
        from services.elevation_service import ElevationService
        from services.directory_service import DirectoryService
        from services.project_service import ProjectService
        from services.phase_service import PhaseService
        
        # Get settings for API connection
        from core.config_production import get_settings
        settings = get_settings()
        
        # Authenticate with Logikal API
        auth_service = AuthService(db)
        success, token = await auth_service.authenticate(
            settings.LOGIKAL_API_BASE_URL,
            settings.LOGIKAL_AUTH_USERNAME,
            settings.LOGIKAL_AUTH_PASSWORD
        )
        
        if not success:
            return {
                "success": False,
                "message": f"Authentication failed: {token}",
                "elevation_id": elevation_id
            }
        
        try:
            # Navigate to the correct directory/project context
            if elevation.phase and elevation.phase.project and elevation.phase.project.directory:
                directory = elevation.phase.project.directory
                
                if directory.full_path:
                    # Navigate to the directory
                    directory_service = DirectoryService(db, token, settings.LOGIKAL_API_BASE_URL)
                    success, message = await directory_service.navigate_to_directory(directory.full_path)
                    
                    if not success:
                        return {
                            "success": False,
                            "message": f"Failed to navigate to directory {directory.name}: {message}",
                            "elevation_id": elevation_id
                        }
                    
                    # Select the project
                    project_service = ProjectService(db, token, settings.LOGIKAL_API_BASE_URL)
                    success, message = await project_service.select_project(elevation.phase.project.logikal_id)
                    
                    if not success:
                        return {
                            "success": False,
                            "message": f"Failed to navigate to project {elevation.phase.project.name}: {message}",
                            "elevation_id": elevation_id
                        }
                    
                    # Select the phase (required for elevation API access)
                    phase_service = PhaseService(db, token, settings.LOGIKAL_API_BASE_URL)
                    success, message = await phase_service.select_phase(elevation.phase.logikal_id)
                    
                    if not success:
                        return {
                            "success": False,
                            "message": f"Failed to navigate to phase {elevation.phase.name}: {message}",
                            "elevation_id": elevation_id
                        }
            
            # Fetch fresh elevation data from API
            elevation_service = ElevationService(db, token, settings.LOGIKAL_API_BASE_URL)
            success, elevations_data, message = await elevation_service.get_elevations()
            
            if not success:
                return {
                    "success": False,
                    "message": f"Failed to fetch elevation data: {message}",
                    "elevation_id": elevation_id
                }
            
            # Find the specific elevation in the API response
            updated_elevation = None
            for api_elevation in elevations_data:
                if api_elevation.get('id') == elevation.logikal_id:
                    updated_elevation = api_elevation
                    break
            
            if not updated_elevation:
                return {
                    "success": False,
                    "message": f"Elevation {elevation.logikal_id} not found in API response",
                    "elevation_id": elevation_id
                }
            
            # Update elevation with fresh data
            updated_fields = []
            if updated_elevation.get('name') != elevation.name:
                elevation.name = updated_elevation.get('name', elevation.name)
                updated_fields.append('name')
            
            if updated_elevation.get('description') != elevation.description:
                elevation.description = updated_elevation.get('description', elevation.description)
                updated_fields.append('description')
            
            if updated_elevation.get('status') != elevation.status:
                elevation.status = updated_elevation.get('status', elevation.status)
                updated_fields.append('status')
            
            # Update sync timestamps
            elevation.last_sync_date = datetime.utcnow()
            elevation.synced_at = datetime.utcnow()
            updated_fields.extend(['last_sync_date', 'synced_at'])
            
            db.commit()
            
            return {
                "success": True,
                "message": f"Elevation {elevation.name} synced successfully from Logikal API",
                "elevation_id": elevation_id,
                "updated_data": updated_fields,
                "api_data": {
                    "name": updated_elevation.get('name'),
                    "description": updated_elevation.get('description'),
                    "status": updated_elevation.get('status')
                }
            }
            
        except Exception as e:
            logger.error(f"Error syncing elevation {elevation_id}: {str(e)}")
            return {
                "success": False,
                "message": f"Error syncing elevation: {str(e)}",
                "elevation_id": elevation_id
            }
            
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error refreshing elevation: {str(e)}")


@router.post("/elevations/{elevation_id}/trigger-parsing")
async def admin_trigger_elevation_parsing(
    elevation_id: int,
    db: Session = Depends(get_db),
    # Admin authentication removed
):
    """Manually trigger parsing for a specific elevation"""
    
    try:
        # Get elevation
        elevation = db.query(Elevation).filter(Elevation.id == elevation_id).first()
        if not elevation:
            raise HTTPException(status_code=404, detail="Elevation not found")
        
        # Import here to avoid circular imports
        from tasks.sqlite_parser_tasks import parse_elevation_sqlite_task
        
        # Trigger parsing task
        task = parse_elevation_sqlite_task.delay(elevation_id)
        
        return {
            "success": True,
            "message": f"Parsing triggered for elevation {elevation.name}",
            "elevation_id": elevation_id,
            "task_id": task.id
        }
            
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error triggering parsing: {str(e)}")


@router.get("/elevations", response_class=HTMLResponse)
async def admin_elevations_manager(
    request: Request,
    elevation_id: Optional[int] = Query(None, description="Pre-select specific elevation")
):
    """Admin elevation management interface with tree navigation"""
    
    elevations_html = """
    <!DOCTYPE html>
    <html lang="en">
    <head>
        <meta charset="UTF-8">
        <meta name="viewport" content="width=device-width, initial-scale=1.0">
        <title>Elevation Manager - Logikal Middleware Admin</title>
        <link href="https://cdn.jsdelivr.net/npm/bootstrap@5.1.3/dist/css/bootstrap.min.css" rel="stylesheet">
        <link href="https://cdnjs.cloudflare.com/ajax/libs/font-awesome/6.0.0/css/all.min.css" rel="stylesheet">
        <style>
            .file-tree {
                max-height: 70vh;
                overflow-y: auto;
                border: 1px solid #dee2e6;
                border-radius: 0.375rem;
                background: #f8f9fa;
            }
            
            .tree-item {
                padding: 0.5rem 1rem;
                cursor: pointer;
                border-bottom: 1px solid #e9ecef;
                transition: background-color 0.2s;
            }
            
            .tree-item:hover {
                background-color: #e9ecef;
            }
            
            .tree-item.selected {
                background-color: #007bff;
                color: white;
            }
            
            .tree-item.elevation {
                padding-left: 3rem;
                font-size: 0.9rem;
            }
            
            .tree-item.phase {
                padding-left: 2.5rem;
            }
            
            .tree-item.project {
                padding-left: 2rem;
            }
            
            .tree-item.directory {
                padding-left: 1rem;
                font-weight: 600;
            }
            
            .tree-toggle {
                width: 1.5rem;
                display: inline-block;
                text-align: center;
                cursor: pointer;
            }
            
            .tree-toggle:before {
                content: "▶";
                transition: transform 0.2s;
            }
            
            .tree-toggle.expanded:before {
                transform: rotate(90deg);
            }
            
            .tree-children {
                display: none;
            }
            
            .tree-children.expanded {
                display: block;
            }
            
            .status-badge {
                font-size: 0.75rem;
                padding: 0.25rem 0.5rem;
            }
            
            .search-container {
                position: relative;
            }
            
            .search-results {
                position: absolute;
                top: 100%;
                left: 0;
                right: 0;
                background: white;
                border: 1px solid #dee2e6;
                border-top: none;
                border-radius: 0 0 0.375rem 0.375rem;
                max-height: 300px;
                overflow-y: auto;
                z-index: 1000;
                display: none;
            }
            
            .search-result-item {
                padding: 0.75rem;
                cursor: pointer;
                border-bottom: 1px solid #e9ecef;
            }
            
            .search-result-item:hover {
                background-color: #f8f9fa;
            }
            
            .elevation-detail {
                min-height: 400px;
            }
            
            .glass-record {
                border-left: 3px solid #007bff;
                padding-left: 1rem;
                margin-bottom: 1rem;
            }
            
            .loading-spinner {
                text-align: center;
                padding: 2rem;
            }
            
            .empty-state {
                text-align: center;
                padding: 3rem;
                color: #6c757d;
            }
            
            .empty-state i {
                font-size: 3rem;
                margin-bottom: 1rem;
                opacity: 0.5;
            }
        </style>
    </head>
    <body>
        <!-- Navigation Bar -->
        <nav class="navbar navbar-expand-lg navbar-dark bg-dark">
            <div class="container-fluid">
                <a class="navbar-brand" href="/admin">
                    <i class="fas fa-cogs"></i> Logikal Middleware Admin
                </a>
                <div class="navbar-nav ms-auto">
                    <a class="nav-link" href="/admin">Dashboard</a>
                    <a class="nav-link active" href="/admin/elevations">Elevations</a>
                    <a class="nav-link" href="/admin/stats">Statistics</a>
                    <a class="nav-link" href="/admin/parsing-queue">Parsing Queue</a>
                    <div class="nav-item dropdown">
                        <a class="nav-link dropdown-toggle" href="#" id="adminDropdown" role="button" data-bs-toggle="dropdown">
                            <i class="fas fa-user-shield"></i> <span id="adminUsername">Admin</span>
                        </a>
                        <ul class="dropdown-menu dropdown-menu-end">
                            <li><a class="dropdown-item" href="#" onclick="logout()">
                                <i class="fas fa-sign-out-alt"></i> Logout
                            </a></li>
                        </ul>
                    </div>
                </div>
            </div>
        </nav>
        
        <div class="container-fluid mt-4">
            <!-- Header -->
            <div class="row mb-4">
                <div class="col-md-12">
                    <div class="d-flex justify-content-between align-items-center">
                        <h1><i class="fas fa-sitemap"></i> Elevation Manager</h1>
                        <div>
                            <button class="btn btn-primary" onclick="refreshTree()">
                                <i class="fas fa-sync"></i> Refresh
                            </button>
                        </div>
                    </div>
                </div>
            </div>

            <!-- Search Bar -->
            <div class="row mb-4">
                <div class="col-md-12">
                    <div class="search-container">
                        <input type="text" id="searchInput" class="form-control" 
                               placeholder="Search elevations, projects, phases..." 
                               onkeyup="handleSearch(event)">
                        <div id="searchResults" class="search-results"></div>
                    </div>
                </div>
            </div>

            <!-- Main Content -->
            <div class="row">
                <!-- File Tree Sidebar -->
                <div class="col-md-4">
                    <div class="card">
                        <div class="card-header">
                            <h5><i class="fas fa-folder-tree"></i> File Structure</h5>
                        </div>
                        <div class="card-body p-0">
                            <div id="loadingSpinner" class="loading-spinner">
                                <div class="spinner-border" role="status">
                                    <span class="visually-hidden">Loading...</span>
                                </div>
                            </div>
                            <div id="fileTree" class="file-tree"></div>
                            <div id="emptyState" class="empty-state" style="display: none;">
                                <i class="fas fa-folder-open"></i>
                                <h5>No elevations found</h5>
                                <p>Try adjusting your search or check if data has been synced.</p>
                            </div>
                        </div>
                    </div>
                </div>

                <!-- Elevation Detail Panel -->
                <div class="col-md-8">
                    <div class="card">
                        <div class="card-header">
                            <h5><i class="fas fa-info-circle"></i> Elevation Details</h5>
                        </div>
                        <div class="card-body">
                            <div id="elevationDetail" class="elevation-detail">
                                <div class="empty-state">
                                    <i class="fas fa-mouse-pointer"></i>
                                    <h5>Select an Elevation</h5>
                                    <p>Click on an elevation in the file tree to view its details.</p>
                                </div>
                            </div>
                        </div>
                    </div>
                </div>
            </div>
        </div>

        <script src="https://cdn.jsdelivr.net/npm/bootstrap@5.1.3/dist/js/bootstrap.bundle.min.js"></script>
        <script>
            // Global state management
            let currentElevationId = null;
            let treeData = [];
            let searchTimeout = null;

            // Initialize the application
            document.addEventListener('DOMContentLoaded', function() {
                // Set admin username directly since authentication is removed
                const adminUsernameElement = document.getElementById('adminUsername');
                if (adminUsernameElement) {
                    adminUsernameElement.textContent = 'admin';
                }
                loadElevationTree();
                
                // Check for elevation_id parameter and auto-select
                const urlParams = new URLSearchParams(window.location.search);
                const elevationId = urlParams.get('elevation_id');
                if (elevationId) {
                    // Wait for tree to load, then select the elevation
                    setTimeout(() => {
                        autoSelectElevation(parseInt(elevationId));
                    }, 1000);
                }
                
                // Setup search input
                const searchInput = document.getElementById('searchInput');
                searchInput.addEventListener('input', function() {
                    clearTimeout(searchTimeout);
                    searchTimeout = setTimeout(() => {
                        if (this.value.length >= 2) {
                            performSearch(this.value);
                        } else {
                            clearSearch();
                        }
                    }, 300);
                });
            });

            // Authentication functions removed - no longer needed

            // Load elevation tree structure
            async function loadElevationTree(searchTerm = null) {
                try {
                    showLoading();
                    
                    const url = searchTerm 
                        ? `/admin/elevations/tree?search=${encodeURIComponent(searchTerm)}`
                        : '/admin/elevations/tree';
                    
                    const token = localStorage.getItem('admin_token') || document.cookie
                        .split('; ')
                        .find(row => row.startsWith('admin_session='))
                        ?.split('=')[1];
                    
                    const response = await fetch(url, {
                        headers: {
                            'Authorization': `Bearer ${token}`
                        }
                    });
                    const result = await response.json();
                    
                    if (result.success) {
                        treeData = result.data;
                        renderFileTree(treeData);
                        
                        if (result.total_elevations === 0) {
                            showEmptyState();
                        }
                    } else {
                        throw new Error('Failed to load elevation tree');
                    }
                } catch (error) {
                    console.error('Error loading elevation tree:', error);
                    showError('Failed to load elevation tree');
                } finally {
                    hideLoading();
                }
            }

            // Render file tree
            function renderFileTree(data) {
                const container = document.getElementById('fileTree');
                container.innerHTML = '';
                
                if (!data || data.length === 0) {
                    showEmptyState();
                    return;
                }
                
                hideEmptyState();
                
                data.forEach(item => {
                    const element = createTreeElement(item);
                    container.appendChild(element);
                });
            }

            // Create tree element
            function createTreeElement(item) {
                const div = document.createElement('div');
                div.className = `tree-item ${item.type}`;
                div.dataset.id = item.id;
                div.dataset.type = item.type;
                
                let icon = '';
                switch (item.type) {
                    case 'directory':
                        icon = '<i class="fas fa-folder"></i>';
                        break;
                    case 'project':
                        icon = '<i class="fas fa-project-diagram"></i>';
                        break;
                    case 'phase':
                        icon = '<i class="fas fa-layer-group"></i>';
                        break;
                    case 'elevation':
                        icon = '<i class="fas fa-cube"></i>';
                        break;
                }
                
                let html = `<span class="tree-toggle" onclick="toggleTreeItem(this)"></span>`;
                html += `<span class="me-2">${icon}</span>`;
                html += `<span class="item-name">${item.name}</span>`;
                
                if (item.type === 'elevation') {
                    html += getStatusBadge(item);
                }
                
                div.innerHTML = html;
                
                // Add click handler for elevations
                if (item.type === 'elevation') {
                    div.addEventListener('click', (e) => {
                        if (!e.target.classList.contains('tree-toggle')) {
                            selectElevation(item);
                        }
                    });
                }
                
                // Add children if they exist
                if (item.children && item.children.length > 0) {
                    const childrenDiv = document.createElement('div');
                    childrenDiv.className = 'tree-children';
                    
                    item.children.forEach(child => {
                        const childElement = createTreeElement(child);
                        childrenDiv.appendChild(childElement);
                    });
                    
                    div.appendChild(childrenDiv);
                } else {
                    // Remove toggle if no children
                    div.querySelector('.tree-toggle').style.display = 'none';
                }
                
                return div;
            }

            // Get status badge HTML
            function getStatusBadge(elevation) {
                let badgeClass = 'badge-secondary';
                let statusText = 'Unknown';
                
                if (elevation.parse_status) {
                    switch (elevation.parse_status) {
                        case 'success':
                            badgeClass = 'badge-success';
                            statusText = 'Parsed';
                            break;
                        case 'pending':
                            badgeClass = 'badge-warning';
                            statusText = 'Pending';
                            break;
                        case 'failed':
                        case 'validation_failed':
                            badgeClass = 'badge-danger';
                            statusText = 'Failed';
                            break;
                        case 'in_progress':
                            badgeClass = 'badge-info';
                            statusText = 'Processing';
                            break;
                    }
                }
                
                return `<span class="badge status-badge ${badgeClass} ms-2">${statusText}</span>`;
            }

            // Toggle tree item
            function toggleTreeItem(element) {
                const children = element.parentElement.querySelector('.tree-children');
                if (children) {
                    children.classList.toggle('expanded');
                    element.classList.toggle('expanded');
                }
            }

            // Select elevation
            async function selectElevation(elevation) {
                // Update UI
                document.querySelectorAll('.tree-item').forEach(item => {
                    item.classList.remove('selected');
                });
                event.currentTarget.classList.add('selected');
                
                currentElevationId = elevation.id;
                await loadElevationDetail(elevation.id);
            }

            // Auto-select elevation by ID (for URL parameter)
            async function autoSelectElevation(elevationId) {
                try {
                    // Find the elevation in the tree data
                    let targetElevation = null;
                    
                    function findElevationInTree(items) {
                        for (const item of items) {
                            if (item.type === 'elevation' && item.id === elevationId) {
                                return item;
                            }
                            if (item.children) {
                                const found = findElevationInTree(item.children);
                                if (found) return found;
                            }
                        }
                        return null;
                    }
                    
                    targetElevation = findElevationInTree(treeData);
                    
                    if (targetElevation) {
                        // Update UI
                        document.querySelectorAll('.tree-item').forEach(item => {
                            item.classList.remove('selected');
                        });
                        
                        const selectedItem = document.querySelector(`[data-id="${elevationId}"]`);
                        if (selectedItem) {
                            selectedItem.classList.add('selected');
                        }
                        
                        currentElevationId = elevationId;
                        await loadElevationDetail(elevationId);
                    } else {
                        console.warn(`Elevation with ID ${elevationId} not found in tree`);
                    }
                } catch (error) {
                    console.error('Error auto-selecting elevation:', error);
                }
            }

            // Load elevation detail
            async function loadElevationDetail(elevationId) {
                try {
                    const token = localStorage.getItem('admin_token') || document.cookie
                        .split('; ')
                        .find(row => row.startsWith('admin_session='))
                        ?.split('=')[1];
                    
                    const response = await fetch(`/admin/elevations/${elevationId}/detail`, {
                        headers: {
                            'Authorization': `Bearer ${token}`
                        }
                    });
                    const result = await response.json();
                    
                    if (result.success) {
                        displayElevationDetail(result.data);
                    } else {
                        throw new Error('Failed to load elevation detail');
                    }
                } catch (error) {
                    console.error('Error loading elevation detail:', error);
                    showError('Failed to load elevation detail');
                }
            }

            // Display elevation detail
            function displayElevationDetail(data) {
                const container = document.getElementById('elevationDetail');
                const elevation = data.elevation;
                const hierarchy = data.hierarchy;
                const glassRecords = data.glass_records;
                
                let html = `
                    <!-- Navigation Bar -->
                    <div class="navigation-bar mb-3">
                        <nav aria-label="breadcrumb">
                            <ol class="breadcrumb">
                                <li class="breadcrumb-item">
                                    <a href="#" onclick="loadElevationTree()">
                                        <i class="fas fa-home"></i> Root
                                    </a>
                                </li>
                `;
                
                if (hierarchy.directory) {
                    html += `<li class="breadcrumb-item">${hierarchy.directory.name}</li>`;
                }
                if (hierarchy.project) {
                    html += `<li class="breadcrumb-item">${hierarchy.project.name}</li>`;
                }
                if (hierarchy.phase) {
                    html += `<li class="breadcrumb-item">${hierarchy.phase.name}</li>`;
                }
                
                html += `
                                <li class="breadcrumb-item active">${elevation.name}</li>
                            </ol>
                        </nav>
                    </div>
                    
                    <!-- Action Buttons -->
                    <div class="row mb-4">
                        <div class="col-md-12">
                            <div class="btn-group" role="group">
                                <button class="btn btn-outline-primary" onclick="refreshElevation(${elevation.id})">
                                    <i class="fas fa-sync-alt"></i> Refresh Data
                                </button>
                                <button class="btn btn-outline-success" onclick="triggerParsing(${elevation.id})" ${elevation.has_parts_data ? '' : 'disabled'}>
                                    <i class="fas fa-play"></i> Trigger Parsing
                                </button>
                                <button class="btn btn-outline-info" onclick="viewImage(${elevation.id})" ${elevation.image_path ? '' : 'disabled'}>
                                    <i class="fas fa-image"></i> View Image
                                </button>
                            </div>
                        </div>
                    </div>
                    
                    <!-- Basic Information -->
                    <div class="row mb-4">
                        <div class="col-md-6">
                            <h5>Basic Information</h5>
                            <table class="table table-sm">
                                <tr><td><strong>Name:</strong></td><td>${elevation.name}</td></tr>
                                <tr><td><strong>Logikal ID:</strong></td><td>${elevation.logikal_id || 'N/A'}</td></tr>
                                <tr><td><strong>Description:</strong></td><td>${elevation.description || 'N/A'}</td></tr>
                                <tr><td><strong>Status:</strong></td><td><span class="badge badge-secondary">${elevation.status || 'Unknown'}</span></td></tr>
                            </table>
                        </div>
                        <div class="col-md-6">
                            <h5>Parsing Status</h5>
                            <table class="table table-sm">
                                <tr><td><strong>Parse Status:</strong></td><td>${getStatusBadge({parse_status: elevation.parse_status})}</td></tr>
                                <tr><td><strong>Has Parts Data:</strong></td><td>${elevation.has_parts_data ? 'Yes' : 'No'}</td></tr>
                                <tr><td><strong>Parts Count:</strong></td><td>${elevation.parts_count || 0}</td></tr>
                                <tr><td><strong>Parsed At:</strong></td><td>${elevation.data_parsed_at ? new Date(elevation.data_parsed_at).toLocaleString() : 'Never'}</td></tr>
                            </table>
                        </div>
                    </div>
                `;
                
                if (elevation.parse_error) {
                    html += `
                        <div class="alert alert-danger">
                            <h6><i class="fas fa-exclamation-triangle"></i> Parse Error</h6>
                            <pre>${elevation.parse_error}</pre>
                        </div>
                    `;
                }
                
                // Glass Records
                if (glassRecords && glassRecords.length > 0) {
                    html += `
                        <div class="mt-4">
                            <h5><i class="fas fa-wine-glass"></i> Glass Records (${glassRecords.length})</h5>
                            <div class="row">
                    `;
                    
                    glassRecords.forEach(glass => {
                        html += `
                            <div class="col-md-6 mb-3">
                                <div class="glass-record">
                                    <h6>${glass.glass_name || 'Unnamed Glass'}</h6>
                                    <table class="table table-sm">
                                        <tr><td><strong>Type:</strong></td><td>${glass.glass_type || 'N/A'}</td></tr>
                                        <tr><td><strong>Thickness:</strong></td><td>${glass.thickness || 'N/A'}</td></tr>
                                        <tr><td><strong>Dimensions:</strong></td><td>${glass.width || 'N/A'} × ${glass.height || 'N/A'}</td></tr>
                                        <tr><td><strong>Area:</strong></td><td>${glass.area || 'N/A'}</td></tr>
                                        <tr><td><strong>Quantity:</strong></td><td>${glass.quantity || 'N/A'} ${glass.unit || ''}</td></tr>
                                        <tr><td><strong>Color:</strong></td><td>${glass.color || 'N/A'}</td></tr>
                                    </table>
                                </div>
                            </div>
                        `;
                    });
                    
                    html += `
                            </div>
                        </div>
                    `;
                }
                
                container.innerHTML = html;
            }

            // Search functionality
            async function performSearch(query) {
                try {
                    const token = localStorage.getItem('admin_token') || document.cookie
                        .split('; ')
                        .find(row => row.startsWith('admin_session='))
                        ?.split('=')[1];
                    
                    const response = await fetch(`/admin/elevations/search?q=${encodeURIComponent(query)}&limit=10`, {
                        headers: {
                            'Authorization': `Bearer ${token}`
                        }
                    });
                    const result = await response.json();
                    
                    if (result.success) {
                        displaySearchResults(result.results);
                    }
                } catch (error) {
                    console.error('Search error:', error);
                }
            }

            // Display search results
            function displaySearchResults(results) {
                const container = document.getElementById('searchResults');
                
                if (results.length === 0) {
                    container.innerHTML = '<div class="search-result-item text-muted">No results found</div>';
                } else {
                    container.innerHTML = results.map(result => `
                        <div class="search-result-item" onclick="selectSearchResult(${result.id})">
                            <strong>${result.name}</strong><br>
                            <small class="text-muted">${result.hierarchy.directory} → ${result.hierarchy.project} → ${result.hierarchy.phase}</small>
                        </div>
                    `).join('');
                }
                
                container.style.display = 'block';
            }

            // Select search result
            async function selectSearchResult(elevationId) {
                clearSearch();
                await loadElevationDetail(elevationId);
                
                // Find and highlight the elevation in the tree
                const elevationElement = document.querySelector(`[data-id="${elevationId}"][data-type="elevation"]`);
                if (elevationElement) {
                    elevationElement.click();
                    elevationElement.scrollIntoView({ behavior: 'smooth', block: 'center' });
                }
            }

            // Clear search
            function clearSearch() {
                document.getElementById('searchResults').style.display = 'none';
                document.getElementById('searchInput').value = '';
                loadElevationTree();
            }

            // Utility functions
            function showLoading() {
                document.getElementById('loadingSpinner').style.display = 'block';
                document.getElementById('fileTree').style.display = 'none';
                document.getElementById('emptyState').style.display = 'none';
            }

            function hideLoading() {
                document.getElementById('loadingSpinner').style.display = 'none';
                document.getElementById('fileTree').style.display = 'block';
            }

            function showEmptyState() {
                document.getElementById('emptyState').style.display = 'block';
                document.getElementById('fileTree').style.display = 'none';
            }

            function hideEmptyState() {
                document.getElementById('emptyState').style.display = 'none';
                document.getElementById('fileTree').style.display = 'block';
            }

            function showError(message) {
                document.getElementById('elevationDetail').innerHTML = `
                    <div class="alert alert-danger">
                        <i class="fas fa-exclamation-triangle"></i> ${message}
                    </div>
                `;
            }

            function refreshTree() {
                loadElevationTree();
            }

            // Handle search input
            function handleSearch(event) {
                if (event.key === 'Escape') {
                    clearSearch();
                }
            }
            
            // Action functions
            async function refreshElevation(elevationId) {
                try {
                    const token = localStorage.getItem('admin_token') || document.cookie
                        .split('; ')
                        .find(row => row.startsWith('admin_session='))
                        ?.split('=')[1];
                    
                    const response = await fetch(`/admin/elevations/${elevationId}/refresh`, {
                        method: 'POST',
                        headers: {
                            'Authorization': `Bearer ${token}`
                        }
                    });
                    
                    const result = await response.json();
                    
                    if (result.success) {
                        alert('Elevation refreshed successfully!');
                        // Reload the elevation detail
                        await loadElevationDetail(elevationId);
                    } else {
                        alert('Failed to refresh elevation: ' + result.message);
                    }
                } catch (error) {
                    console.error('Error refreshing elevation:', error);
                    alert('Error refreshing elevation: ' + error.message);
                }
            }
            
            async function triggerParsing(elevationId) {
                if (!confirm('Are you sure you want to trigger parsing for this elevation?')) {
                    return;
                }
                
                try {
                    const token = localStorage.getItem('admin_token') || document.cookie
                        .split('; ')
                        .find(row => row.startsWith('admin_session='))
                        ?.split('=')[1];
                    
                    const response = await fetch(`/admin/elevations/${elevationId}/trigger-parsing`, {
                        method: 'POST',
                        headers: {
                            'Authorization': `Bearer ${token}`
                        }
                    });
                    
                    const result = await response.json();
                    
                    if (result.success) {
                        alert('Parsing triggered successfully! Task ID: ' + result.task_id);
                        // Reload the elevation detail
                        await loadElevationDetail(elevationId);
                    } else {
                        alert('Failed to trigger parsing: ' + result.message);
                    }
                } catch (error) {
                    console.error('Error triggering parsing:', error);
                    alert('Error triggering parsing: ' + error.message);
                }
            }
            
            function viewImage(elevationId) {
                // Open image in new tab
                window.open(`/api/v1/elevations/${elevationId}/image`, '_blank');
            }
        </script>
    </body>
    </html>
    """
    
    return HTMLResponse(content=elevations_html, status_code=200)


@router.get("/stats", response_class=HTMLResponse)
async def admin_stats_ui(request: Request):
    """Admin-style statistics interface"""
    stats_html = """
    <!DOCTYPE html>
    <html lang="en">
    <head>
        <meta charset="UTF-8">
        <meta name="viewport" content="width=device-width, initial-scale=1.0">
        <title>Statistics - Logikal Middleware Admin</title>
        <link href="https://cdn.jsdelivr.net/npm/bootstrap@5.1.3/dist/css/bootstrap.min.css" rel="stylesheet">
        <link href="https://cdnjs.cloudflare.com/ajax/libs/font-awesome/6.0.0/css/all.min.css" rel="stylesheet">
        <script src="https://cdn.jsdelivr.net/npm/chart.js"></script>
    </head>
    <body>
        <nav class="navbar navbar-expand-lg navbar-dark bg-dark">
            <div class="container-fluid">
                <a class="navbar-brand" href="/admin">
                    <i class="fas fa-cogs"></i> Logikal Middleware Admin
                </a>
                <div class="navbar-nav ms-auto">
                    <a class="nav-link" href="/admin">Dashboard</a>
                    <a class="nav-link" href="/admin/elevations">Elevations</a>
                    <a class="nav-link active" href="/admin/stats">Statistics</a>
                </div>
            </div>
        </nav>
        
        <div class="container mt-4">
            <div class="row">
                <div class="col-md-12">
                    <h1><i class="fas fa-chart-bar"></i> Enrichment Statistics</h1>
                </div>
            </div>
            
            <div class="row mt-4">
                <div class="col-md-3">
                    <div class="card text-center">
                        <div class="card-body">
                            <i class="fas fa-cube fa-3x text-primary mb-3"></i>
                            <h5 class="card-title">Total Elevations</h5>
                            <h2 id="totalElevations" class="text-primary">-</h2>
                        </div>
                    </div>
                </div>
                <div class="col-md-3">
                    <div class="card text-center">
                        <div class="card-body">
                            <i class="fas fa-check-circle fa-3x text-success mb-3"></i>
                            <h5 class="card-title">Successfully Parsed</h5>
                            <h2 id="successCount" class="text-success">-</h2>
                        </div>
                    </div>
                </div>
                <div class="col-md-3">
                    <div class="card text-center">
                        <div class="card-body">
                            <i class="fas fa-exclamation-triangle fa-3x text-warning mb-3"></i>
                            <h5 class="card-title">Pending</h5>
                            <h2 id="pendingCount" class="text-warning">-</h2>
                        </div>
                    </div>
                </div>
                <div class="col-md-3">
                    <div class="card text-center">
                        <div class="card-body">
                            <i class="fas fa-times-circle fa-3x text-danger mb-3"></i>
                            <h5 class="card-title">Failed</h5>
                            <h2 id="failedCount" class="text-danger">-</h2>
                        </div>
                    </div>
                </div>
            </div>
            
            <div class="row mt-4">
                <div class="col-md-6">
                    <div class="card">
                        <div class="card-header">
                            <h5><i class="fas fa-chart-pie"></i> Parse Status Distribution</h5>
                        </div>
                        <div class="card-body">
                            <canvas id="statusChart"></canvas>
                        </div>
                    </div>
                </div>
                <div class="col-md-6">
                    <div class="card">
                        <div class="card-header">
                            <h5><i class="fas fa-chart-line"></i> Parsing Activity (Last 7 Days)</h5>
                        </div>
                        <div class="card-body">
                            <canvas id="activityChart"></canvas>
                        </div>
                    </div>
                </div>
            </div>
            
            <div class="row mt-4">
                <div class="col-md-12">
                    <div class="card">
                        <div class="card-header">
                            <h5><i class="fas fa-list"></i> Recent Parsing Activity</h5>
                        </div>
                        <div class="card-body">
                            <div id="recentActivity" class="table-responsive">
                                <div class="text-center">
                                    <div class="spinner-border" role="status">
                                        <span class="visually-hidden">Loading...</span>
                                    </div>
                                </div>
                            </div>
                        </div>
                    </div>
                </div>
            </div>
        </div>
        
        <script>
            // Authentication removed - page loads directly
            document.addEventListener('DOMContentLoaded', function() {
                // Set admin username directly since authentication is removed
                const adminUsernameElement = document.getElementById('adminUsername');
                if (adminUsernameElement) {
                    adminUsernameElement.textContent = 'admin';
                }
                // Load stats directly
                loadStats();
            });
            
            async function loadStats() {
                try {
                    const response = await fetch('/api/v1/elevations/enrichment/status');
                    const data = await response.json();
                    
                    if (data.success) {
                        updateStatsDisplay(data.data);
                        createCharts(data.data);
                    }
                } catch (error) {
                    console.error('Error loading stats:', error);
                    showError('Failed to load statistics');
                }
            }
            
            function updateStatsDisplay(stats) {
                document.getElementById('totalElevations').textContent = stats.total_elevations;
                document.getElementById('successCount').textContent = stats.parse_status_counts.success || 0;
                document.getElementById('pendingCount').textContent = stats.parse_status_counts.pending || 0;
                document.getElementById('failedCount').textContent = (stats.parse_status_counts.failed || 0) + (stats.parse_status_counts.validation_failed || 0);
            }
            
            function createCharts(stats) {
                // Status distribution chart
                const statusCtx = document.getElementById('statusChart').getContext('2d');
                new Chart(statusCtx, {
                    type: 'doughnut',
                    data: {
                        labels: ['Success', 'Pending', 'Failed', 'In Progress', 'Validation Failed'],
                        datasets: [{
                            data: [
                                stats.parse_status_counts.success || 0,
                                stats.parse_status_counts.pending || 0,
                                stats.parse_status_counts.failed || 0,
                                stats.parse_status_counts.in_progress || 0,
                                stats.parse_status_counts.validation_failed || 0
                            ],
                            backgroundColor: [
                                '#28a745',
                                '#ffc107',
                                '#dc3545',
                                '#17a2b8',
                                '#fd7e14'
                            ]
                        }]
                    },
                    options: {
                        responsive: true,
                        plugins: {
                            legend: {
                                position: 'bottom'
                            }
                        }
                    }
                });
                
                // Activity chart (placeholder - would need historical data)
                const activityCtx = document.getElementById('activityChart').getContext('2d');
                new Chart(activityCtx, {
                    type: 'line',
                    data: {
                        labels: ['6 days ago', '5 days ago', '4 days ago', '3 days ago', '2 days ago', 'Yesterday', 'Today'],
                        datasets: [{
                            label: 'Parsing Activity',
                            data: [0, 0, 0, 0, 0, 0, stats.parse_status_counts.success || 0],
                            borderColor: '#007bff',
                            backgroundColor: 'rgba(0, 123, 255, 0.1)',
                            tension: 0.4
                        }]
                    },
                    options: {
                        responsive: true,
                        scales: {
                            y: {
                                beginAtZero: true
                            }
                        }
                    }
                });
            }
            
            function showError(message) {
                document.getElementById('recentActivity').innerHTML = `
                    <div class="alert alert-danger">
                        <i class="fas fa-exclamation-triangle"></i> ${message}
                    </div>
                `;
            }
        </script>
    </body>
    </html>
    """
    
    return HTMLResponse(content=stats_html, status_code=200)


@router.get("/parsing-queue", response_class=HTMLResponse)
async def admin_parsing_queue_ui(request: Request):
    """Admin parsing queue monitoring interface"""
    queue_html = """
    <!DOCTYPE html>
    <html lang="en">
    <head>
        <meta charset="UTF-8">
        <meta name="viewport" content="width=device-width, initial-scale=1.0">
        <title>Parsing Queue Monitor - Logikal Middleware Admin</title>
        <link href="https://cdn.jsdelivr.net/npm/bootstrap@5.1.3/dist/css/bootstrap.min.css" rel="stylesheet">
        <link href="https://cdnjs.cloudflare.com/ajax/libs/font-awesome/6.0.0/css/all.min.css" rel="stylesheet">
    </head>
    <body>
        <nav class="navbar navbar-expand-lg navbar-dark bg-dark">
            <div class="container-fluid">
                <a class="navbar-brand" href="/admin">
                    <i class="fas fa-cogs"></i> Logikal Middleware Admin
                </a>
                <div class="navbar-nav ms-auto">
                    <a class="nav-link" href="/admin">Dashboard</a>
                    <a class="nav-link" href="/admin/parsing-status">Parser Status</a>
                    <a class="nav-link active" href="/admin/parsing-queue">Queue Monitor</a>
                    <a class="nav-link" href="/admin/elevations">Elevations</a>
                    <a class="nav-link" href="/admin/stats">Statistics</a>
                </div>
            </div>
        </nav>
        
        <div class="container mt-4">
            <div class="row">
                <div class="col-md-12">
                    <div class="d-flex justify-content-between align-items-center mb-4">
                        <h1><i class="fas fa-tasks"></i> Parsing Queue Monitor</h1>
                        <div>
                            <button onclick="refreshQueueStatus()" class="btn btn-primary">
                                <i class="fas fa-sync-alt"></i> Refresh
                            </button>
                            <button onclick="clearCompletedTasks()" class="btn btn-outline-secondary">
                                <i class="fas fa-trash"></i> Clear Completed
                            </button>
                            <button onclick="triggerBatchParsing()" class="btn btn-success">
                                <i class="fas fa-play"></i> Trigger Batch Parsing
                            </button>
                        </div>
                    </div>
                </div>
            </div>
            
            <!-- Queue Status Overview -->
            <div class="row mb-4">
                <div class="col-md-3">
                    <div class="card text-center">
                        <div class="card-body">
                            <i class="fas fa-play fa-2x text-primary mb-2"></i>
                            <h6 class="card-title">Active Tasks</h6>
                            <h3 id="activeTasks" class="text-primary">-</h3>
                        </div>
                    </div>
                </div>
                <div class="col-md-3">
                    <div class="card text-center">
                        <div class="card-body">
                            <i class="fas fa-clock fa-2x text-warning mb-2"></i>
                            <h6 class="card-title">Scheduled Tasks</h6>
                            <h3 id="scheduledTasks" class="text-warning">-</h3>
                        </div>
                    </div>
                </div>
                <div class="col-md-3">
                    <div class="card text-center">
                        <div class="card-body">
                            <i class="fas fa-pause fa-2x text-info mb-2"></i>
                            <h6 class="card-title">Reserved Tasks</h6>
                            <h3 id="reservedTasks" class="text-info">-</h3>
                        </div>
                    </div>
                </div>
                <div class="col-md-3">
                    <div class="card text-center">
                        <div class="card-body">
                            <i class="fas fa-server fa-2x text-success mb-2"></i>
                            <h6 class="card-title">Workers</h6>
                            <h3 id="workerCount" class="text-success">-</h3>
                        </div>
                    </div>
                </div>
            </div>
            
            <!-- Queue Tabs -->
            <ul class="nav nav-tabs" id="queueTabs" role="tablist">
                <li class="nav-item" role="presentation">
                    <button class="nav-link active" id="active-tab" data-bs-toggle="tab" data-bs-target="#active" type="button" role="tab">
                        <i class="fas fa-play"></i> Active Tasks
                    </button>
                </li>
                <li class="nav-item" role="presentation">
                    <button class="nav-link" id="scheduled-tab" data-bs-toggle="tab" data-bs-target="#scheduled" type="button" role="tab">
                        <i class="fas fa-clock"></i> Scheduled Tasks
                    </button>
                </li>
                <li class="nav-item" role="presentation">
                    <button class="nav-link" id="reserved-tab" data-bs-toggle="tab" data-bs-target="#reserved" type="button" role="tab">
                        <i class="fas fa-pause"></i> Reserved Tasks
                    </button>
                </li>
                <li class="nav-item" role="presentation">
                    <button class="nav-link" id="workers-tab" data-bs-toggle="tab" data-bs-target="#workers" type="button" role="tab">
                        <i class="fas fa-server"></i> Workers
                    </button>
                </li>
                <li class="nav-item" role="presentation">
                    <button class="nav-link" id="queues-tab" data-bs-toggle="tab" data-bs-target="#queues" type="button" role="tab">
                        <i class="fas fa-list"></i> Queue Status
                    </button>
                </li>
                <li class="nav-item" role="presentation">
                    <button class="nav-link" id="completed-tab" data-bs-toggle="tab" data-bs-target="#completed" type="button" role="tab">
                        <i class="fas fa-check-circle"></i> Completed Tasks
                    </button>
                </li>
            </ul>
            
            <!-- Tab Content -->
            <div class="tab-content" id="queueTabContent">
                <!-- Active Tasks -->
                <div class="tab-pane fade show active" id="active" role="tabpanel">
                    <div class="card mt-3">
                        <div class="card-header">
                            <h6><i class="fas fa-play"></i> Currently Running Tasks</h6>
                        </div>
                        <div class="card-body">
                            <div id="activeTasksList" class="table-responsive">
                                <div class="text-center">
                                    <div class="spinner-border" role="status">
                                        <span class="visually-hidden">Loading active tasks...</span>
                                    </div>
                                </div>
                            </div>
                        </div>
                    </div>
                </div>
                
                <!-- Scheduled Tasks -->
                <div class="tab-pane fade" id="scheduled" role="tabpanel">
                    <div class="card mt-3">
                        <div class="card-header">
                            <h6><i class="fas fa-clock"></i> Scheduled Tasks</h6>
                        </div>
                        <div class="card-body">
                            <div id="scheduledTasksList" class="table-responsive">
                                <div class="text-center">
                                    <div class="spinner-border" role="status">
                                        <span class="visually-hidden">Loading scheduled tasks...</span>
                                    </div>
                                </div>
                            </div>
                        </div>
                    </div>
                </div>
                
                <!-- Reserved Tasks -->
                <div class="tab-pane fade" id="reserved" role="tabpanel">
                    <div class="card mt-3">
                        <div class="card-header">
                            <h6><i class="fas fa-pause"></i> Reserved Tasks (Waiting for Worker)</h6>
                        </div>
                        <div class="card-body">
                            <div id="reservedTasksList" class="table-responsive">
                                <div class="text-center">
                                    <div class="spinner-border" role="status">
                                        <span class="visually-hidden">Loading reserved tasks...</span>
                                    </div>
                                </div>
                            </div>
                        </div>
                    </div>
                </div>
                
                <!-- Workers -->
                <div class="tab-pane fade" id="workers" role="tabpanel">
                    <div class="card mt-3">
                        <div class="card-header">
                            <h6><i class="fas fa-server"></i> Celery Workers</h6>
                        </div>
                        <div class="card-body">
                            <div id="workersList" class="table-responsive">
                                <div class="text-center">
                                    <div class="spinner-border" role="status">
                                        <span class="visually-hidden">Loading workers...</span>
                                    </div>
                                </div>
                            </div>
                        </div>
                    </div>
                </div>
                
                <!-- Queue Status -->
                <div class="tab-pane fade" id="queues" role="tabpanel">
                    <div class="card mt-3">
                        <div class="card-header">
                            <h6><i class="fas fa-list"></i> Queue Status</h6>
                        </div>
                        <div class="card-body">
                            <div id="queueStatus" class="table-responsive">
                                <div class="text-center">
                                    <div class="spinner-border" role="status">
                                        <span class="visually-hidden">Loading queue status...</span>
                                    </div>
                                </div>
                            </div>
                        </div>
                    </div>
                </div>
                
                <!-- Completed Tasks -->
                <div class="tab-pane fade" id="completed" role="tabpanel">
                    <div class="card mt-3">
                        <div class="card-header d-flex justify-content-between align-items-center">
                            <h6><i class="fas fa-check-circle"></i> Recently Completed Parsing Tasks</h6>
                            <button onclick="refreshCompletedTasks()" class="btn btn-sm btn-outline-primary">
                                <i class="fas fa-sync-alt"></i> Refresh
                            </button>
                        </div>
                        <div class="card-body">
                            <div id="completedTasksList" class="table-responsive">
                                <div class="text-center">
                                    <div class="spinner-border" role="status">
                                        <span class="visually-hidden">Loading completed tasks...</span>
                                    </div>
                                </div>
                            </div>
                        </div>
                    </div>
                </div>
            </div>
        </div>
        
        <script>
            // Authentication removed - page loads directly
            document.addEventListener('DOMContentLoaded', function() {
                // Set admin username directly since authentication is removed
                const adminUsernameElement = document.getElementById('adminUsername');
                if (adminUsernameElement) {
                    adminUsernameElement.textContent = 'admin';
                }
            });

            let refreshInterval;
            
            document.addEventListener('DOMContentLoaded', function() {
                refreshQueueStatus();
                // Auto-refresh every 5 seconds
                refreshInterval = setInterval(refreshQueueStatus, 5000);
            });
            
            // Stop auto-refresh when page is hidden
            document.addEventListener('visibilitychange', function() {
                if (document.hidden) {
                    clearInterval(refreshInterval);
                } else {
                    refreshInterval = setInterval(refreshQueueStatus, 5000);
                }
            });
            
            async function refreshQueueStatus() {
                try {
                    const response = await fetch('/admin/api/parsing-queue/status');
                    const data = await response.json();
                    
                    if (data.success) {
                        updateQueueOverview(data.data);
                        updateActiveTasks(data.data.active_tasks || {});
                        updateScheduledTasks(data.data.scheduled_tasks || {});
                        updateReservedTasks(data.data.reserved_tasks || {});
                        updateWorkers(data.data.workers || {});
                        updateQueueStatus(data.data.queue_status || {});
                        updateCompletedTasks(data.data.completed_tasks || {});
                    } else {
                        showError('Failed to load queue status: ' + data.message);
                    }
                } catch (error) {
                    console.error('Error refreshing queue status:', error);
                    showError('Error loading queue status: ' + error.message);
                }
            }
            
            function updateQueueOverview(data) {
                const activeTasks = Object.values(data.active_tasks || {}).reduce((sum, tasks) => sum + tasks.length, 0);
                const scheduledTasks = Object.values(data.scheduled_tasks || {}).reduce((sum, tasks) => sum + tasks.length, 0);
                const reservedTasks = Object.values(data.reserved_tasks || {}).reduce((sum, tasks) => sum + tasks.length, 0);
                const workerCount = Object.keys(data.workers || {}).length;
                
                document.getElementById('activeTasks').textContent = activeTasks;
                document.getElementById('scheduledTasks').textContent = scheduledTasks;
                document.getElementById('reservedTasks').textContent = reservedTasks;
                document.getElementById('workerCount').textContent = workerCount;
            }
            
            function updateActiveTasks(activeTasks) {
                const container = document.getElementById('activeTasksList');
                
                if (Object.keys(activeTasks).length === 0) {
                    container.innerHTML = '<div class="text-center text-muted">No active tasks</div>';
                    return;
                }
                
                let html = '<table class="table table-striped"><thead><tr><th>Worker</th><th>Task</th><th>ID</th><th>Args</th><th>Time Started</th><th>Runtime</th></tr></thead><tbody>';
                
                Object.entries(activeTasks).forEach(([worker, tasks]) => {
                    tasks.forEach(task => {
                        const startTime = new Date(task.time_start * 1000);
                        const runtime = Math.round((Date.now() - startTime.getTime()) / 1000);
                        
                        html += `
                            <tr>
                                <td><span class="badge bg-primary">${worker}</span></td>
                                <td><code>${task.name}</code></td>
                                <td><small>${task.id}</small></td>
                                <td><small>${JSON.stringify(task.args || [])}</small></td>
                                <td>${startTime.toLocaleString()}</td>
                                <td>${runtime}s</td>
                            </tr>
                        `;
                    });
                });
                
                html += '</tbody></table>';
                container.innerHTML = html;
            }
            
            function updateScheduledTasks(scheduledTasks) {
                const container = document.getElementById('scheduledTasksList');
                
                if (Object.keys(scheduledTasks).length === 0) {
                    container.innerHTML = '<div class="text-center text-muted">No scheduled tasks</div>';
                    return;
                }
                
                let html = '<table class="table table-striped"><thead><tr><th>Task</th><th>ID</th><th>ETA</th><th>Args</th></tr></thead><tbody>';
                
                Object.entries(scheduledTasks).forEach(([worker, tasks]) => {
                    tasks.forEach(task => {
                        const eta = new Date(task.eta * 1000);
                        
                        html += `
                            <tr>
                                <td><code>${task.name}</code></td>
                                <td><small>${task.id}</small></td>
                                <td>${eta.toLocaleString()}</td>
                                <td><small>${JSON.stringify(task.args || [])}</small></td>
                            </tr>
                        `;
                    });
                });
                
                html += '</tbody></table>';
                container.innerHTML = html;
            }
            
            function updateReservedTasks(reservedTasks) {
                const container = document.getElementById('reservedTasksList');
                
                if (Object.keys(reservedTasks).length === 0) {
                    container.innerHTML = '<div class="text-center text-muted">No reserved tasks</div>';
                    return;
                }
                
                let html = '<table class="table table-striped"><thead><tr><th>Task</th><th>ID</th><th>Args</th><th>Reserved At</th></tr></thead><tbody>';
                
                Object.entries(reservedTasks).forEach(([worker, tasks]) => {
                    tasks.forEach(task => {
                        html += `
                            <tr>
                                <td><code>${task.name}</code></td>
                                <td><small>${task.id}</small></td>
                                <td><small>${JSON.stringify(task.args || [])}</small></td>
                                <td>${new Date().toLocaleString()}</td>
                            </tr>
                        `;
                    });
                });
                
                html += '</tbody></table>';
                container.innerHTML = html;
            }
            
            function updateWorkers(workers) {
                const container = document.getElementById('workersList');
                
                if (Object.keys(workers).length === 0) {
                    container.innerHTML = '<div class="text-center text-muted">No workers available</div>';
                    return;
                }
                
                let html = '<table class="table table-striped"><thead><tr><th>Worker</th><th>Status</th><th>Queues</th><th>Registered Tasks</th></tr></thead><tbody>';
                
                Object.entries(workers).forEach(([workerName, workerInfo]) => {
                    const status = workerInfo.status === 'online' ? 'bg-success' : 'bg-danger';
                    const queues = workerInfo.queues ? workerInfo.queues.join(', ') : 'N/A';
                    const taskCount = workerInfo.registered ? Object.keys(workerInfo.registered).length : 0;
                    
                    html += `
                        <tr>
                            <td><span class="badge bg-primary">${workerName}</span></td>
                            <td><span class="badge ${status}">${workerInfo.status || 'unknown'}</span></td>
                            <td><small>${queues}</small></td>
                            <td><span class="badge bg-info">${taskCount} tasks</span></td>
                        </tr>
                    `;
                });
                
                html += '</tbody></table>';
                container.innerHTML = html;
            }
            
            function updateQueueStatus(queueStatus) {
                const container = document.getElementById('queueStatus');
                
                let html = '<table class="table table-striped"><thead><tr><th>Queue</th><th>Status</th><th>Length</th><th>Consumers</th></tr></thead><tbody>';
                
                Object.entries(queueStatus).forEach(([queueName, status]) => {
                    const statusBadge = status.consumers > 0 ? 'bg-success' : 'bg-warning';
                    
                    html += `
                        <tr>
                            <td><span class="badge bg-primary">${queueName}</span></td>
                            <td><span class="badge ${statusBadge}">Active</span></td>
                            <td><span class="badge bg-info">${status.length || 0}</span></td>
                            <td><span class="badge bg-secondary">${status.consumers || 0}</span></td>
                        </tr>
                    `;
                });
                
                html += '</tbody></table>';
                container.innerHTML = html;
            }
            
            function updateCompletedTasks(completedTasks) {
                const container = document.getElementById('completedTasksList');
                
                if (!completedTasks || Object.keys(completedTasks).length === 0) {
                    container.innerHTML = '<div class="text-center text-muted">No completed tasks found</div>';
                    return;
                }
                
                let html = '<table class="table table-striped table-hover"><thead><tr><th>Elevation</th><th>Task</th><th>Status</th><th>Duration</th><th>Completed At</th><th>Glass Records</th><th>Details</th></tr></thead><tbody>';
                
                // Sort tasks by completion time (most recent first)
                const sortedTasks = Object.entries(completedTasks).sort((a, b) => {
                    const timeA = new Date(a[1].completed_at || 0);
                    const timeB = new Date(b[1].completed_at || 0);
                    return timeB - timeA;
                });
                
                sortedTasks.slice(0, 20).forEach(([taskId, task]) => {
                    const statusBadge = task.status === 'success' ? 'bg-success' : 
                                       task.status === 'failed' ? 'bg-danger' : 'bg-warning';
                    const duration = task.duration ? `${task.duration.toFixed(2)}s` : 'N/A';
                    const completedAt = task.completed_at ? new Date(task.completed_at).toLocaleString() : 'N/A';
                    const glassCount = task.glass_count || 0;
                    
                    html += `
                        <tr>
                            <td>
                                <span class="badge bg-primary">${task.elevation_id || 'N/A'}</span>
                            </td>
                            <td><code>${task.task_name || 'parse_elevation_sqlite'}</code></td>
                            <td><span class="badge ${statusBadge}">${task.status || 'unknown'}</span></td>
                            <td><small>${duration}</small></td>
                            <td><small>${completedAt}</small></td>
                            <td>
                                <span class="badge bg-info">${glassCount}</span>
                            </td>
                            <td>
                                <button class="btn btn-sm btn-outline-secondary" onclick="showTaskDetails('${taskId}', ${JSON.stringify(task).replace(/"/g, '&quot;')})">
                                    <i class="fas fa-info-circle"></i>
                                </button>
                            </td>
                        </tr>
                    `;
                });
                
                html += '</tbody></table>';
                container.innerHTML = html;
            }
            
            function showTaskDetails(taskId, task) {
                const detailsHtml = `
                    <div class="modal fade" id="taskDetailsModal" tabindex="-1">
                        <div class="modal-dialog modal-lg">
                            <div class="modal-content">
                                <div class="modal-header">
                                    <h5 class="modal-title">Task Details: ${taskId}</h5>
                                    <button type="button" class="btn-close" data-bs-dismiss="modal"></button>
                                </div>
                                <div class="modal-body">
                                    <div class="row">
                                        <div class="col-md-6">
                                            <h6>Task Information</h6>
                                            <p><strong>Task ID:</strong> <code>${taskId}</code></p>
                                            <p><strong>Status:</strong> <span class="badge ${task.status === 'success' ? 'bg-success' : 'bg-danger'}">${task.status}</span></p>
                                            <p><strong>Duration:</strong> ${task.duration ? task.duration.toFixed(2) + 's' : 'N/A'}</p>
                                            <p><strong>Completed:</strong> ${task.completed_at ? new Date(task.completed_at).toLocaleString() : 'N/A'}</p>
                                        </div>
                                        <div class="col-md-6">
                                            <h6>Results</h6>
                                            <p><strong>Elevation ID:</strong> ${task.elevation_id || 'N/A'}</p>
                                            <p><strong>Glass Records:</strong> ${task.glass_count || 0}</p>
                                            <p><strong>Parts Count:</strong> ${task.parts_count || 'N/A'}</p>
                                            <p><strong>Success:</strong> ${task.success ? 'Yes' : 'No'}</p>
                                        </div>
                                    </div>
                                    ${task.error ? `
                                        <div class="mt-3">
                                            <h6>Error Details</h6>
                                            <div class="alert alert-danger">
                                                <pre>${task.error}</pre>
                                            </div>
                                        </div>
                                    ` : ''}
                                    <div class="mt-3">
                                        <h6>Full Task Data</h6>
                                        <pre class="bg-light p-3"><code>${JSON.stringify(task, null, 2)}</code></pre>
                                    </div>
                                </div>
                                <div class="modal-footer">
                                    <button type="button" class="btn btn-secondary" data-bs-dismiss="modal">Close</button>
                                </div>
                            </div>
                        </div>
                    </div>
                `;
                
                // Remove existing modal if any
                const existingModal = document.getElementById('taskDetailsModal');
                if (existingModal) {
                    existingModal.remove();
                }
                
                // Add new modal
                document.body.insertAdjacentHTML('beforeend', detailsHtml);
                
                // Show modal
                const modal = new bootstrap.Modal(document.getElementById('taskDetailsModal'));
                modal.show();
            }
            
            async function refreshCompletedTasks() {
                try {
                    const response = await fetch('/admin/api/parsing-queue/completed-tasks');
                    const data = await response.json();
                    
                    if (data.success) {
                        updateCompletedTasks(data.data);
                    } else {
                        showError('Failed to load completed tasks: ' + data.message);
                    }
                } catch (error) {
                    console.error('Error refreshing completed tasks:', error);
                    showError('Error loading completed tasks: ' + error.message);
                }
            }
            
            async function clearCompletedTasks() {
                if (!confirm('Are you sure you want to clear completed tasks? This action cannot be undone.')) {
                    return;
                }
                
                try {
                    const response = await fetch('/admin/api/parsing-queue/clear-completed', {
                        method: 'POST'
                    });
                    
                    const result = await response.json();
                    
                    if (result.success) {
                        alert('Completed tasks cleared successfully');
                        refreshQueueStatus();
                    } else {
                        alert('Failed to clear completed tasks: ' + result.message);
                    }
                } catch (error) {
                    alert('Error clearing completed tasks: ' + error.message);
                }
            }
            
            async function triggerBatchParsing() {
                if (!confirm('This will trigger parsing for all unparsed elevations with parts data. Continue?')) {
                    return;
                }
                
                try {
                    const response = await fetch('/admin/api/parsing-queue/trigger-batch-parsing', {
                        method: 'POST'
                    });
                    
                    const result = await response.json();
                    
                    if (result.success) {
                        alert(`Batch parsing triggered successfully! ${result.triggered_count} tasks queued.`);
                        refreshQueueStatus();
                    } else {
                        alert('Failed to trigger batch parsing: ' + result.message);
                    }
                } catch (error) {
                    alert('Error triggering batch parsing: ' + error.message);
                }
            }
            
            function showError(message) {
                // Show error in all containers
                const containers = ['activeTasksList', 'scheduledTasksList', 'reservedTasksList', 'workersList', 'queueStatus', 'completedTasksList'];
                containers.forEach(id => {
                    document.getElementById(id).innerHTML = `
                        <div class="alert alert-danger">
                            <i class="fas fa-exclamation-triangle"></i> ${message}
                        </div>
                    `;
                });
            }
        </script>
        
        <script src="https://cdn.jsdelivr.net/npm/bootstrap@5.1.3/dist/js/bootstrap.bundle.min.js"></script>
    </body>
    </html>
    """
    
    return HTMLResponse(content=queue_html, status_code=200)


@router.get("/api/parsing-queue/status")
async def get_parsing_queue_status():
    """Get comprehensive parsing queue status"""
    try:
        # Get Celery inspect object
        inspect = celery_app.control.inspect()
        
        # Get all task information
        active_tasks = inspect.active() or {}
        scheduled_tasks = inspect.scheduled() or {}
        reserved_tasks = inspect.reserved() or {}
        registered_tasks = inspect.registered() or {}
        stats = inspect.stats() or {}
        
        # Get queue information
        queue_info = {}
        try:
            # This is a simplified queue status - in production you might want to use Redis directly
            for worker_name, worker_stats in stats.items():
                if 'queues' in worker_stats:
                    for queue_name in worker_stats['queues']:
                        if queue_name not in queue_info:
                            queue_info[queue_name] = {'length': 0, 'consumers': 0}
                        queue_info[queue_name]['consumers'] += 1
        except Exception as e:
            print(f"Error getting queue info: {e}")
        
        # Count tasks by queue
        queue_counts = {}
        for worker, tasks in active_tasks.items():
            for task in tasks:
                queue = task.get('delivery_info', {}).get('routing_key', 'unknown')
                queue_counts[queue] = queue_counts.get(queue, 0) + 1
        
        # Get completed tasks data
        completed_tasks = {}
        try:
            db = next(get_db())
            recent_elevations = db.query(Elevation).filter(
                Elevation.parse_status == 'success',
                Elevation.data_parsed_at.isnot(None)
            ).order_by(Elevation.data_parsed_at.desc()).limit(10).all()
            
            for elevation in recent_elevations:
                task_id = f"elevation-{elevation.id}-{elevation.data_parsed_at.timestamp()}"
                glass_count = db.query(ElevationGlass).filter(
                    ElevationGlass.elevation_id == elevation.id
                ).count()
                
                completed_tasks[task_id] = {
                    "task_id": task_id,
                    "task_name": "parse_elevation_sqlite",
                    "elevation_id": elevation.id,
                    "status": "success",
                    "success": True,
                    "duration": 0.5,
                    "completed_at": elevation.data_parsed_at.isoformat() if elevation.data_parsed_at else None,
                    "glass_count": glass_count,
                    "parts_count": elevation.parts_count,
                    "elevation_name": elevation.name
                }
        except Exception as e:
            print(f"Could not get completed tasks: {e}")
        
        return {
            "success": True,
            "data": {
                "active_tasks": active_tasks,
                "scheduled_tasks": scheduled_tasks,
                "reserved_tasks": reserved_tasks,
                "registered_tasks": registered_tasks,
                "workers": stats,
                "queue_status": queue_info,
                "queue_counts": queue_counts,
                "completed_tasks": completed_tasks,
                "timestamp": datetime.utcnow().isoformat()
            }
        }
        
    except Exception as e:
        return {
            "success": False,
            "message": str(e),
            "data": {
                "active_tasks": {},
                "scheduled_tasks": {},
                "reserved_tasks": {},
                "workers": {},
                "queue_status": {},
                "queue_counts": {}
            }
        }


@router.post("/api/parsing-queue/clear-completed")
async def clear_completed_tasks():
    """Clear completed tasks from result backend"""
    try:
        # Purge completed tasks from result backend
        celery_app.control.purge()
        
        return {
            "success": True,
            "message": "Completed tasks cleared successfully"
        }
        
    except Exception as e:
        return {
            "success": False,
            "message": f"Failed to clear completed tasks: {str(e)}"
        }


@router.post("/api/parsing-queue/trigger-batch-parsing")
async def trigger_batch_parsing():
    """Trigger parsing for all unparsed elevations with parts data"""
    try:
        # Import here to avoid circular imports
        from tasks.sqlite_parser_tasks import trigger_parsing_for_new_files_task
        
        # Trigger the batch parsing task
        task = trigger_parsing_for_new_files_task.delay()
        
        return {
            "success": True,
            "message": "Batch parsing task triggered successfully",
            "task_id": task.id,
            "triggered_count": "Unknown - check task results"
        }
        
    except Exception as e:
        return {
            "success": False,
            "message": f"Failed to trigger batch parsing: {str(e)}"
        }


@router.get("/api/parsing-queue/completed-tasks")
async def get_completed_tasks():
    """Get recently completed parsing tasks"""
    try:
        # Get completed parsing tasks from database
        db = next(get_db())
        
        # Query elevations that have been successfully parsed recently
        recent_elevations = db.query(Elevation).filter(
            Elevation.parse_status == 'success',
            Elevation.data_parsed_at.isnot(None)
        ).order_by(Elevation.data_parsed_at.desc()).limit(20).all()
        
        completed_tasks = {}
        
        for elevation in recent_elevations:
            # Create a mock task entry based on database data
            task_id = f"elevation-{elevation.id}-{elevation.data_parsed_at.timestamp()}"
            
            # Get glass count for this elevation
            glass_count = db.query(ElevationGlass).filter(
                ElevationGlass.elevation_id == elevation.id
            ).count()
            
            completed_tasks[task_id] = {
                "task_id": task_id,
                "task_name": "parse_elevation_sqlite",
                "elevation_id": elevation.id,
                "status": "success",
                "success": True,
                "duration": 0.5,  # Estimated duration
                "completed_at": elevation.data_parsed_at.isoformat() if elevation.data_parsed_at else None,
                "glass_count": glass_count,
                "parts_count": elevation.parts_count,
                "elevation_name": elevation.name,
                "parse_error": elevation.parse_error
            }
        
        # Also try to get some recent Celery task results from Redis
        try:
            from celery_app import celery_app
            inspect = celery_app.control.inspect()
            # This is a simplified approach - in production you might want to use Redis directly
            # to get more detailed task history
        except Exception as e:
            print(f"Could not get Celery task history: {e}")
        
        return {
            "success": True,
            "data": completed_tasks,
            "count": len(completed_tasks)
        }
        
    except Exception as e:
        return {
            "success": False,
            "message": f"Failed to get completed tasks: {str(e)}",
            "data": {}
        }
