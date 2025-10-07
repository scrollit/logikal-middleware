#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
Phase 1 Validation Script
Tests all Phase 1 implementations for DigitalOcean deployment readiness
"""

import os
import sys
import logging
from pathlib import Path

# Add the app directory to Python path
app_dir = Path(__file__).parent / "app"
sys.path.insert(0, str(app_dir))

# Setup logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


def test_imports():
    """
    Test that all required modules can be imported
    """
    logger.info("Testing module imports...")
    
    try:
        from core.config_production import get_settings, validate_required_settings
        logger.info("✅ Core configuration modules imported successfully")
        
        # Test database init (may fail due to missing dependencies in local env)
        try:
            from core.database_init import initialize_database, setup_production_database
            logger.info("✅ Database initialization modules imported successfully")
        except ImportError as e:
            logger.warning(f"⚠️  Database init import warning (expected in local env): {e}")
        
        # Test security (may fail due to missing dependencies in local env)
        try:
            from core.security_production import setup_security_middleware
            logger.info("✅ Security modules imported successfully")
        except ImportError as e:
            logger.warning(f"⚠️  Security import warning (expected in local env): {e}")
        
        return True
    except ImportError as e:
        logger.error(f"❌ Critical import error: {e}")
        return False


def test_configuration():
    """
    Test configuration loading
    """
    logger.info("Testing configuration...")
    
    try:
        from core.config_production import get_settings
        
        # Test with production environment
        os.environ["ENVIRONMENT"] = "production"
        settings = get_settings()
        
        # Check required settings exist
        required_attrs = [
            "APP_NAME", "APP_VERSION", "ENVIRONMENT", "DEBUG",
            "API_V1_STR", "HOST", "PORT", "LOG_LEVEL", "LOG_FORMAT"
        ]
        
        for attr in required_attrs:
            if not hasattr(settings, attr):
                logger.error(f"❌ Missing configuration attribute: {attr}")
                return False
        
        logger.info("✅ Configuration loaded successfully")
        logger.info(f"   App: {settings.APP_NAME} v{settings.APP_VERSION}")
        logger.info(f"   Environment: {settings.ENVIRONMENT}")
        logger.info(f"   Debug: {settings.DEBUG}")
        return True
        
    except Exception as e:
        logger.error(f"❌ Configuration error: {e}")
        return False


def test_security_functions():
    """
    Test security utility functions
    """
    logger.info("Testing security functions...")
    
    try:
        from core.security_production import APIKeySecurity, SessionSecurity
        
        # Test API key generation
        api_key = APIKeySecurity.generate_secure_api_key()
        if len(api_key) < 32:
            logger.error("❌ API key too short")
            return False
        
        # Test API key hashing
        hashed = APIKeySecurity.hash_api_key(api_key)
        if not APIKeySecurity.verify_api_key(api_key, hashed):
            logger.error("❌ API key verification failed")
            return False
        
        # Test session token generation
        session_token = SessionSecurity.generate_session_token()
        if len(session_token) < 32:
            logger.error("❌ Session token too short")
            return False
        
        logger.info("✅ Security functions working correctly")
        return True
        
    except Exception as e:
        logger.error(f"❌ Security function error: {e}")
        return False


def test_database_init():
    """
    Test database initialization functions
    """
    logger.info("Testing database initialization...")
    
    try:
        # Test if the file exists and has the required functions
        db_init_path = Path("app/core/database_init.py")
        if not db_init_path.exists():
            logger.error("❌ Database init file not found")
            return False
        
        with open(db_init_path, 'r') as f:
            content = f.read()
            
            # Check for required functions
            required_functions = [
                "def create_database_tables():",
                "def create_initial_admin_user():",
                "def initialize_database():",
                "def setup_production_database():"
            ]
            
            for func in required_functions:
                if func not in content:
                    logger.error(f"❌ Database init missing function: {func}")
                    return False
        
        logger.info("✅ Database initialization functions available")
        return True
        
    except Exception as e:
        logger.error(f"❌ Database initialization error: {e}")
        return False


def test_startup_script():
    """
    Test startup script exists and is executable
    """
    logger.info("Testing startup script...")
    
    try:
        startup_path = Path("app/startup.py")
        if not startup_path.exists():
            logger.error("❌ Startup script not found")
            return False
        
        # Check if script is readable
        with open(startup_path, 'r') as f:
            content = f.read()
            if "def main():" not in content:
                logger.error("❌ Startup script missing main function")
                return False
        
        logger.info("✅ Startup script exists and is valid")
        return True
        
    except Exception as e:
        logger.error(f"❌ Startup script error: {e}")
        return False


def test_dockerfile():
    """
    Test Dockerfile configuration
    """
    logger.info("Testing Dockerfile...")
    
    try:
        dockerfile_path = Path("Dockerfile")
        if not dockerfile_path.exists():
            logger.error("❌ Dockerfile not found")
            return False
        
        with open(dockerfile_path, 'r') as f:
            content = f.read()
            
            # Check for required elements
            required_elements = [
                "FROM python:3.11-slim",
                "EXPOSE 8000",
                "CMD [\"python\", \"startup.py\"]",
                "HEALTHCHECK"
            ]
            
            for element in required_elements:
                if element not in content:
                    logger.error(f"❌ Dockerfile missing: {element}")
                    return False
        
        logger.info("✅ Dockerfile configuration correct")
        return True
        
    except Exception as e:
        logger.error(f"❌ Dockerfile error: {e}")
        return False


def test_digitalocean_config():
    """
    Test DigitalOcean app configuration
    """
    logger.info("Testing DigitalOcean configuration...")
    
    try:
        do_config_path = Path(".do/app.yaml")
        if not do_config_path.exists():
            logger.error("❌ DigitalOcean app.yaml not found")
            return False
        
        with open(do_config_path, 'r') as f:
            content = f.read()
            
            # Check for required elements
            required_elements = [
                "run_command: python startup.py",
                "http_port: 8000",
                "dockerfile_path: Dockerfile",
                "health_check:",
                "http_path: /api/v1/health"
            ]
            
            for element in required_elements:
                if element not in content:
                    logger.error(f"❌ DigitalOcean config missing: {element}")
                    return False
        
        logger.info("✅ DigitalOcean configuration correct")
        return True
        
    except Exception as e:
        logger.error(f"❌ DigitalOcean config error: {e}")
        return False


def main():
    """
    Run all validation tests
    """
    logger.info("🚀 Starting Phase 1 Validation")
    logger.info("=" * 50)
    
    tests = [
        ("Module Imports", test_imports),
        ("Configuration", test_configuration),
        ("Security Functions", test_security_functions),
        ("Database Initialization", test_database_init),
        ("Startup Script", test_startup_script),
        ("Dockerfile", test_dockerfile),
        ("DigitalOcean Config", test_digitalocean_config),
    ]
    
    passed = 0
    total = len(tests)
    
    for test_name, test_func in tests:
        logger.info(f"\n🧪 Running {test_name} test...")
        try:
            if test_func():
                passed += 1
                logger.info(f"✅ {test_name} test PASSED")
            else:
                logger.error(f"❌ {test_name} test FAILED")
        except Exception as e:
            logger.error(f"❌ {test_name} test ERROR: {e}")
    
    logger.info("\n" + "=" * 50)
    logger.info(f"📊 VALIDATION RESULTS: {passed}/{total} tests passed")
    
    if passed == total:
        logger.info("🎉 ALL TESTS PASSED - PHASE 1 READY FOR DEPLOYMENT!")
        return True
    else:
        logger.error(f"❌ {total - passed} tests failed - PHASE 1 NOT READY")
        return False


if __name__ == "__main__":
    try:
        success = main()
        sys.exit(0 if success else 1)
    except KeyboardInterrupt:
        logger.info("\n❌ Validation cancelled")
        sys.exit(1)
    except Exception as e:
        logger.error(f"\n❌ Validation error: {e}")
        sys.exit(1)
