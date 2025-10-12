#!/usr/bin/env python3
"""
Test script to make raw API calls to Logikal and see exactly what data is returned
for project DOS22309 in Demo Odoo directory.
"""

import asyncio
import aiohttp
import json
import os
from typing import Dict, Any

# Load environment variables
from dotenv import load_dotenv
load_dotenv()

LOGIKAL_BASE_URL = "https://api.logikal.nl"
LOGIKAL_USERNAME = os.getenv("LOGIKAL_AUTH_USERNAME")
LOGIKAL_PASSWORD = os.getenv("LOGIKAL_AUTH_PASSWORD")

async def authenticate():
    """Authenticate with Logikal API"""
    print("🔐 Authenticating with Logikal API...")
    
    auth_data = {
        "username": LOGIKAL_USERNAME,
        "password": LOGIKAL_PASSWORD
    }
    
    async with aiohttp.ClientSession() as session:
        async with session.post(f"{LOGIKAL_BASE_URL}/auth/login", json=auth_data) as response:
            if response.status == 200:
                data = await response.json()
                token = data.get('token')
                print(f"✅ Authentication successful, token: {token[:20]}...")
                return token
            else:
                text = await response.text()
                print(f"❌ Authentication failed: {response.status} - {text}")
                return None

async def navigate_to_directory(token: str, directory_name: str):
    """Navigate to a specific directory"""
    print(f"📁 Navigating to directory: {directory_name}")
    
    async with aiohttp.ClientSession() as session:
        headers = {"Authorization": f"Bearer {token}"}
        
        # First get all directories to find the right one
        async with session.get(f"{LOGIKAL_BASE_URL}/directories", headers=headers) as response:
            if response.status == 200:
                directories_data = await response.json()
                print(f"📋 Found {len(directories_data)} directories")
                
                # Find the target directory
                target_directory = None
                for directory in directories_data:
                    if directory.get('name') == directory_name:
                        target_directory = directory
                        break
                
                if target_directory:
                    directory_id = target_directory.get('id')
                    print(f"🎯 Found directory '{directory_name}' with ID: {directory_id}")
                    
                    # Navigate to the directory
                    async with session.post(f"{LOGIKAL_BASE_URL}/directories/{directory_id}/navigate", headers=headers) as nav_response:
                        if nav_response.status == 200:
                            print(f"✅ Successfully navigated to directory: {directory_name}")
                            return True
                        else:
                            nav_text = await nav_response.text()
                            print(f"❌ Failed to navigate to directory: {nav_response.status} - {nav_text}")
                            return False
                else:
                    print(f"❌ Directory '{directory_name}' not found")
                    return False
            else:
                text = await response.text()
                print(f"❌ Failed to get directories: {response.status} - {text}")
                return False

async def get_projects(token: str):
    """Get all projects in current directory"""
    print("📦 Getting projects in current directory...")
    
    async with aiohttp.ClientSession() as session:
        headers = {"Authorization": f"Bearer {token}"}
        
        async with session.get(f"{LOGIKAL_BASE_URL}/projects", headers=headers) as response:
            if response.status == 200:
                projects_data = await response.json()
                print(f"📋 Found {len(projects_data)} projects")
                
                for project in projects_data:
                    print(f"  - {project.get('name', 'Unnamed')} (ID: {project.get('id', 'No ID')})")
                
                return projects_data
            else:
                text = await response.text()
                print(f"❌ Failed to get projects: {response.status} - {text}")
                return []

async def select_project(token: str, project_id: str):
    """Select a specific project"""
    print(f"🎯 Selecting project: {project_id}")
    
    async with aiohttp.ClientSession() as session:
        headers = {"Authorization": f"Bearer {token}"}
        
        async with session.post(f"{LOGIKAL_BASE_URL}/projects/{project_id}/select", headers=headers) as response:
            if response.status == 200:
                print(f"✅ Successfully selected project: {project_id}")
                return True
            else:
                text = await response.text()
                print(f"❌ Failed to select project: {response.status} - {text}")
                return False

async def get_phases(token: str):
    """Get all phases in current project"""
    print("📋 Getting phases in current project...")
    
    async with aiohttp.ClientSession() as session:
        headers = {"Authorization": f"Bearer {token}"}
        
        async with session.get(f"{LOGIKAL_BASE_URL}/phases", headers=headers) as response:
            if response.status == 200:
                phases_data = await response.json()
                print(f"📋 Found {len(phases_data)} phases")
                
                for i, phase in enumerate(phases_data):
                    print(f"  Phase {i+1}:")
                    print(f"    Name: {phase.get('name', 'Unnamed')}")
                    print(f"    ID: {phase.get('id', 'No ID')}")
                    print(f"    Description: {phase.get('description', 'No description')}")
                    print(f"    Raw data: {json.dumps(phase, indent=2)}")
                    print()
                
                return phases_data
            else:
                text = await response.text()
                print(f"❌ Failed to get phases: {response.status} - {text}")
                return []

async def get_elevations(token: str):
    """Get all elevations in current project"""
    print("🏗️ Getting elevations in current project...")
    
    async with aiohttp.ClientSession() as session:
        headers = {"Authorization": f"Bearer {token}"}
        
        async with session.get(f"{LOGIKAL_BASE_URL}/elevations", headers=headers) as response:
            if response.status == 200:
                elevations_data = await response.json()
                print(f"📋 Found {len(elevations_data)} elevations")
                
                for i, elevation in enumerate(elevations_data):
                    print(f"  Elevation {i+1}:")
                    print(f"    Name: {elevation.get('name', 'Unnamed')}")
                    print(f"    ID: {elevation.get('id', 'No ID')}")
                    print(f"    Description: {elevation.get('description', 'No description')}")
                    print(f"    Phase ID: {elevation.get('phaseId', 'No Phase ID')}")
                    print()
                
                return elevations_data
            else:
                text = await response.text()
                print(f"❌ Failed to get elevations: {response.status} - {text}")
                return []

async def main():
    """Main test function"""
    print("🚀 Starting raw Logikal API test for DOS22309 in Demo Odoo directory")
    print("=" * 70)
    
    # Step 1: Authenticate
    token = await authenticate()
    if not token:
        return
    
    # Step 2: Navigate to Demo Odoo directory
    if not await navigate_to_directory(token, "Demo Odoo"):
        return
    
    # Step 3: Get projects to find DOS22309
    projects = await get_projects(token)
    if not projects:
        return
    
    # Find DOS22309 project
    dos_project = None
    for project in projects:
        if project.get('name') == 'DOS22309':
            dos_project = project
            break
    
    if not dos_project:
        print("❌ Project DOS22309 not found in Demo Odoo directory")
        return
    
    print(f"🎯 Found project DOS22309 with ID: {dos_project.get('id')}")
    
    # Step 4: Select the project
    if not await select_project(token, dos_project.get('id')):
        return
    
    # Step 5: Get phases
    print("\n" + "=" * 50)
    phases = await get_phases(token)
    
    # Step 6: Get elevations
    print("\n" + "=" * 50)
    elevations = await get_elevations(token)
    
    print("\n" + "=" * 70)
    print("🎯 SUMMARY:")
    print(f"  Projects found: {len(projects)}")
    print(f"  Phases found: {len(phases)}")
    print(f"  Elevations found: {len(elevations)}")
    print("=" * 70)

if __name__ == "__main__":
    asyncio.run(main())
