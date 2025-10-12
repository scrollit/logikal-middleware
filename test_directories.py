#!/usr/bin/env python3
"""
Quick test to check directories endpoint without authentication
"""

import requests

MIDDLEWARE_URL = "https://logikal-middleware-avwpu.ondigitalocean.app"

def test_cached_directories():
    """Test the cached directories endpoint"""
    print("Testing cached directories endpoint...")
    url = f"{MIDDLEWARE_URL}/api/v1/directories/cached"
    
    try:
        response = requests.get(url, timeout=10)
        print(f"Status: {response.status_code}")
        if response.status_code == 200:
            data = response.json()
            directories = data.get('data', [])
            print(f"Found {len(directories)} directories")
            
            # Count exclusions
            excluded = sum(1 for d in directories if d.get('exclude_from_sync', False))
            included = len(directories) - excluded
            
            print(f"Included: {included}")
            print(f"Excluded: {excluded}")
            print(f"Total: {len(directories)}")
            
            # Show first few directories
            print("\nFirst 5 directories:")
            for i, d in enumerate(directories[:5]):
                status = "❌ EXCLUDED" if d.get('exclude_from_sync', False) else "✅ SYNCABLE"
                name = d.get('name', d.get('logikal_id', 'Unknown'))
                print(f"  {i+1}. {name} - {status}")
            
            return directories
        else:
            print(f"Error: {response.text}")
            return []
    except Exception as e:
        print(f"Exception: {str(e)}")
        return []

if __name__ == "__main__":
    test_cached_directories()
