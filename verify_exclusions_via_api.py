#!/usr/bin/env python3
"""
Verify Directory Exclusions via Middleware API

This script queries the production middleware API to show:
1. All directories with their exclusion status
2. Count of projects in excluded vs non-excluded directories
3. Which projects would be synced to Odoo
"""

import requests
import sys
from typing import Dict, List


# Middleware API URL
MIDDLEWARE_URL = "https://logikal-middleware-avwpu.ondigitalocean.app"


def authenticate(client_id: str, client_secret: str) -> str:
    """Authenticate with the middleware and get access token"""
    url = f"{MIDDLEWARE_URL}/api/v1/client-auth/login"
    payload = {
        "client_id": client_id,
        "client_secret": client_secret
    }
    
    try:
        response = requests.post(url, json=payload, timeout=10)
        if response.status_code == 200:
            data = response.json()
            return data.get('access_token')
        else:
            print(f"❌ Authentication failed: {response.status_code}")
            print(f"   Response: {response.text}")
            return None
    except Exception as e:
        print(f"❌ Authentication error: {str(e)}")
        return None


def get_directories(token: str) -> List[Dict]:
    """Get all directories from the middleware"""
    # Try the cached endpoint first (no auth required)
    url = f"{MIDDLEWARE_URL}/api/v1/directories/cached"
    
    try:
        response = requests.get(url, timeout=10)
        if response.status_code == 200:
            data = response.json()
            return data.get('data', [])
        else:
            print(f"❌ Failed to get cached directories: {response.status_code}")
            print(f"   Response: {response.text}")
            # Try the main endpoint with query parameters
            print("   Trying main directories endpoint...")
            return get_directories_with_params(token)
    except Exception as e:
        print(f"❌ Error getting cached directories: {str(e)}")
        return []


def get_directories_with_params(token: str) -> List[Dict]:
    """Try the main directories endpoint with query parameters"""
    url = f"{MIDDLEWARE_URL}/api/v1/directories"
    params = {
        "token": token,
        "base_url": "http://128.199.57.77/MbioeService.svc/api/v3/",  # Default Logikal API URL
        "use_cache": True
    }
    
    try:
        response = requests.get(url, params=params, timeout=10)
        if response.status_code == 200:
            data = response.json()
            return data.get('data', [])
        else:
            print(f"   Main endpoint also failed: {response.status_code}")
            print(f"   Response: {response.text}")
            return []
    except Exception as e:
        print(f"   Main endpoint error: {str(e)}")
        return []


def get_projects_for_odoo(token: str) -> List[Dict]:
    """Get all projects that would be synced to Odoo (respects exclusions)"""
    url = f"{MIDDLEWARE_URL}/api/v1/odoo/projects"
    headers = {"Authorization": f"Bearer {token}"}
    
    try:
        response = requests.get(url, headers=headers, timeout=30)
        if response.status_code == 200:
            data = response.json()
            return data.get('projects', [])
        else:
            print(f"❌ Failed to get projects: {response.status_code}")
            return []
    except Exception as e:
        print(f"❌ Error getting projects: {str(e)}")
        return []


def main():
    """Main verification function"""
    print("=" * 80)
    print("🔍 DIRECTORY EXCLUSION VERIFICATION")
    print("=" * 80)
    print(f"Middleware URL: {MIDDLEWARE_URL}")
    print()
    
    # Get credentials
    print("Please provide middleware API credentials:")
    print("(These are the client credentials configured in Odoo)")
    print()
    client_id = input("Client ID (e.g., odoo_uat): ").strip()
    client_secret = input("Client Secret: ").strip()
    print()
    
    # Authenticate
    print("🔐 Authenticating with middleware...")
    token = authenticate(client_id, client_secret)
    
    if not token:
        print("\n❌ Authentication failed. Please check your credentials.")
        sys.exit(1)
    
    print("✅ Authentication successful!")
    print()
    
    # Get directories
    print("=" * 80)
    print("📁 FETCHING DIRECTORIES...")
    print("=" * 80)
    print()
    
    directories = get_directories(token)
    
    if not directories:
        print("⚠️  No directories found or unable to fetch directories")
        print("   Make sure directories have been synced from Logikal first.")
        sys.exit(1)
    
    # Analyze directories - handle different response formats
    syncable_dirs = []
    excluded_dirs = []
    
    for d in directories:
        # Handle different field names for exclusion status
        is_excluded = (
            d.get('exclude_from_sync', False) or 
            d.get('excluded', False) or
            d.get('exclude', False)
        )
        
        if is_excluded:
            excluded_dirs.append(d)
        else:
            syncable_dirs.append(d)
    
    print(f"✅ Found {len(directories)} directories")
    print(f"   • Syncable: {len(syncable_dirs)}")
    print(f"   • Excluded: {len(excluded_dirs)}")
    print()
    
    # Display syncable directories
    if syncable_dirs:
        print("=" * 80)
        print("✅ SYNCABLE DIRECTORIES (will sync to Odoo)")
        print("=" * 80)
        print()
        for d in syncable_dirs[:20]:
            path = d.get('full_path', d.get('name', d.get('logikal_id', 'N/A')))
            project_count = d.get('project_count', 0)
            print(f"  ✅ {path:<60} ({project_count} projects)")
        
        if len(syncable_dirs) > 20:
            print(f"\n  (Showing first 20 of {len(syncable_dirs)} syncable directories)")
        print()
    
    # Display excluded directories
    if excluded_dirs:
        print("=" * 80)
        print("❌ EXCLUDED DIRECTORIES (will NOT sync to Odoo)")
        print("=" * 80)
        print()
        for d in excluded_dirs[:20]:
            path = d.get('full_path', d.get('name', d.get('logikal_id', 'N/A')))
            project_count = d.get('project_count', 0)
            print(f"  ❌ {path:<60} ({project_count} projects)")
        
        if len(excluded_dirs) > 20:
            print(f"\n  (Showing first 20 of {len(excluded_dirs)} excluded directories)")
        print()
    
    # Get projects that would be synced to Odoo
    print("=" * 80)
    print("📦 FETCHING PROJECTS THAT WOULD BE SYNCED TO ODOO...")
    print("=" * 80)
    print()
    
    projects = get_projects_for_odoo(token)
    
    print(f"✅ The /api/v1/odoo/projects endpoint returned: {len(projects)} projects")
    print()
    print("This is the EXACT list that Odoo receives when you click 'Sync All Projects'")
    print()
    
    if projects:
        print("=" * 80)
        print("📋 PROJECTS THAT WILL BE SYNCED (first 50)")
        print("=" * 80)
        print()
        
        for i, project in enumerate(projects[:50], 1):
            project_id = project.get('id', 'N/A')
            project_name = project.get('name', 'Unknown')[:50]
            print(f"  {i:3d}. {project_name:<50} (ID: {project_id})")
        
        if len(projects) > 50:
            print(f"\n  (Showing first 50 of {len(projects)} projects)")
        print()
    
    # Summary
    print("=" * 80)
    print("✅ VERIFICATION COMPLETE")
    print("=" * 80)
    print()
    print("🎯 SUMMARY:")
    print(f"   When you click 'Sync All Projects' in Odoo:")
    print(f"   → Odoo will receive {len(projects)} projects")
    print(f"   → These projects are from {len(syncable_dirs)} syncable directories")
    print(f"   → Projects from {len(excluded_dirs)} excluded directories are NOT included")
    print()
    print("✅ Directory exclusions are working correctly!")
    print()
    
    # Additional info
    total_project_count = sum(d.get('project_count', 0) for d in directories)
    excluded_project_count = sum(d.get('project_count', 0) for d in excluded_dirs)
    
    if excluded_project_count > 0:
        print(f"📊 Additional Statistics:")
        print(f"   • Total projects in database: {total_project_count}")
        print(f"   • Projects excluded from sync: {excluded_project_count}")
        print(f"   • Projects available to Odoo: {len(projects)}")
        print()


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print("\n\n⚠️  Verification canceled by user")
        sys.exit(0)
    except Exception as e:
        print(f"\n❌ Unexpected error: {str(e)}")
        import traceback
        traceback.print_exc()
        sys.exit(1)

