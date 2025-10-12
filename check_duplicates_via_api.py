#!/usr/bin/env python3
"""
Script to check for duplicate projects via middleware API
"""
import requests
import json
import logging

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Middleware configuration
MIDDLEWARE_BASE_URL = "https://logikal-middleware-avwpu.ondigitalocean.app"
CLIENT_ID = "odoo_uat_instance"
CLIENT_SECRET = "WZnOA4XMqqSKshPnmPXxq3ThSxKgWJ-i"

def authenticate():
    """Authenticate with middleware and get access token"""
    url = f"{MIDDLEWARE_BASE_URL}/api/v1/client-auth/login"
    payload = {
        "client_id": CLIENT_ID,
        "client_secret": CLIENT_SECRET
    }
    
    try:
        response = requests.post(url, json=payload, timeout=30)
        response.raise_for_status()
        data = response.json()
        return data.get('access_token')
    except Exception as e:
        logger.error(f"Authentication failed: {e}")
        return None

def get_all_projects(token):
    """Get all projects from middleware"""
    url = f"{MIDDLEWARE_BASE_URL}/api/v1/odoo/projects"
    headers = {"Authorization": f"Bearer {token}"}
    
    try:
        response = requests.get(url, headers=headers, timeout=30)
        response.raise_for_status()
        data = response.json()
        return data.get('projects', [])
    except Exception as e:
        logger.error(f"Failed to get projects: {e}")
        return []

def get_all_directories(token):
    """Get all directories from middleware"""
    url = f"{MIDDLEWARE_BASE_URL}/api/v1/odoo/directories"
    headers = {"Authorization": f"Bearer {token}"}
    
    try:
        response = requests.get(url, headers=headers, timeout=30)
        response.raise_for_status()
        data = response.json()
        return data.get('directories', [])
    except Exception as e:
        logger.error(f"Failed to get directories: {e}")
        return []

def analyze_duplicates():
    """Analyze projects for duplicates and directory context"""
    
    # Authenticate
    token = authenticate()
    if not token:
        logger.error("Failed to authenticate")
        return
    
    logger.info("✅ Authentication successful")
    
    # Get all projects
    projects = get_all_projects(token)
    if not projects:
        logger.error("No projects retrieved")
        return
    
    logger.info(f"✅ Retrieved {len(projects)} projects")
    
    # Get all directories
    directories = get_all_directories(token)
    logger.info(f"✅ Retrieved {len(directories)} directories")
    
    # Create directory lookup
    directory_lookup = {d['id']: d for d in directories}
    
    # Analyze projects for duplicates
    logger.info("\n=== Checking for duplicate project names ===")
    name_to_projects = {}
    
    for project in projects:
        name = project.get('name')
        if name not in name_to_projects:
            name_to_projects[name] = []
        name_to_projects[name].append(project)
    
    duplicates_found = False
    for name, project_list in name_to_projects.items():
        if len(project_list) > 1:
            duplicates_found = True
            logger.warning(f"🔴 DUPLICATE: {name} appears {len(project_list)} times:")
            for project in project_list:
                directory_id = project.get('directory_id')
                directory_name = directory_lookup.get(directory_id, {}).get('name', 'Unknown')
                directory_path = directory_lookup.get(directory_id, {}).get('full_path', 'Unknown')
                logger.warning(f"  - GUID: {project.get('id')}")
                logger.warning(f"    Directory: {directory_name} (ID: {directory_id})")
                logger.warning(f"    Path: {directory_path}")
    
    if not duplicates_found:
        logger.info("✅ No duplicate project names found")
    
    # Check DOS22309 specifically
    logger.info("\n=== Checking DOS22309 specifically ===")
    dos22309_projects = [p for p in projects if p.get('name') == 'DOS22309']
    
    if dos22309_projects:
        logger.info(f"Found {len(dos22309_projects)} instance(s) of DOS22309:")
        for project in dos22309_projects:
            directory_id = project.get('directory_id')
            directory_name = directory_lookup.get(directory_id, {}).get('name', 'Unknown')
            directory_path = directory_lookup.get(directory_id, {}).get('full_path', 'Unknown')
            logger.info(f"  - GUID: {project.get('id')}")
            logger.info(f"    Directory: {directory_name} (ID: {directory_id})")
            logger.info(f"    Path: {directory_path}")
    else:
        logger.warning("❌ DOS22309 not found in projects")
    
    # Analyze directory distribution
    logger.info("\n=== Directory distribution ===")
    directory_project_count = {}
    for project in projects:
        directory_id = project.get('directory_id')
        if directory_id:
            directory_name = directory_lookup.get(directory_id, {}).get('name', f'Directory_{directory_id}')
            directory_project_count[directory_name] = directory_project_count.get(directory_name, 0) + 1
    
    for directory_name, count in sorted(directory_project_count.items(), key=lambda x: x[1], reverse=True):
        logger.info(f"  - {directory_name}: {count} projects")
    
    # Check projects without directory context
    logger.info("\n=== Projects without directory context ===")
    no_directory = [p for p in projects if not p.get('directory_id')]
    
    if no_directory:
        logger.warning(f"Found {len(no_directory)} projects without directory context:")
        for project in no_directory:
            logger.warning(f"  - {project.get('name')} (GUID: {project.get('id')})")
    else:
        logger.info("✅ All projects have directory context")

if __name__ == "__main__":
    analyze_duplicates()
