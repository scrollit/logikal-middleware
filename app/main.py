from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles
from fastapi.responses import HTMLResponse
from core.config import settings
from core.config_production import get_settings as get_production_settings, validate_required_settings
from core.logging import setup_logging, LoggingMiddleware
from core.security_production import setup_security_middleware
from monitoring.prometheus import setup_prometheus_metrics
from monitoring.health import router as health_router
from routers import auth_router, directories_router, projects_router, elevations_router, phases_router, sync_router, client_auth, odoo, sync_status, scheduler, advanced_sync, admin_auth, sync_intervals, forced_sync, client_management
from routers.admin_ui import router as admin_ui_router
import logging
import os

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
app.include_router(admin_auth.router, prefix=settings.API_V1_STR)
app.include_router(sync_intervals.router)
app.include_router(forced_sync.router, prefix=settings.API_V1_STR)
app.include_router(client_management.router)
app.include_router(admin_ui_router)
app.include_router(health_router, prefix=settings.API_V1_STR)

# Setup production middleware (temporarily disabled due to logging issues)
# if production_settings.ENVIRONMENT == "production":
#     setup_security_middleware(app)

# Setup Prometheus metrics (temporarily disabled due to logging issue)
# if production_settings.PROMETHEUS_ENABLED:
#     setup_prometheus_metrics(app)

# Setup logging middleware (temporarily disabled due to structlog issue)
# app.add_middleware(LoggingMiddleware)

@app.get("/")
async def root():
    return {"message": "Logikal Middleware is running!", "version": settings.APP_VERSION}

@app.get("/health")
async def health_check():
    return {"status": "healthy", "version": settings.APP_VERSION}

@app.on_event("startup")
async def startup_event():
    """
    Handle application startup
    """
    logger = logging.getLogger(__name__)
    logger.info("Application starting up...")
    
    # Only run database initialization in production
    if production_settings.ENVIRONMENT == "production":
        try:
            from core.database_init import initialize_database
            logger.info("Initializing production database...")
            success = initialize_database()
            if success:
                logger.info("Database initialization completed")
            else:
                logger.error("Database initialization failed")
        except Exception as e:
            logger.error(f"Database initialization error: {e}")
    
    logger.info("Application startup completed")

@app.on_event("shutdown")
async def shutdown_event():
    """
    Handle application shutdown
    """
    logger = logging.getLogger(__name__)
    logger.info("Application shutting down...")

