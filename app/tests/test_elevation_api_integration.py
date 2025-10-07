"""
Integration test for Elevation UI API endpoints
This test verifies the API endpoints work correctly with the database
"""

import sys
import os
import asyncio
from pathlib import Path

# Add the app directory to Python path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

async def test_elevation_tree_api():
    """Test the elevation tree API endpoint"""
    
    print("🧪 Testing Elevation Tree API...")
    
    try:
        from routers.elevation_ui import get_elevations_tree
        from core.database import get_db
        
        # Get database session
        db = next(get_db())
        
        # Test the API function
        result = await get_elevations_tree(db=db)
        
        if result.get("success"):
            print("✅ Elevation tree API call successful")
            print(f"   - Found {result.get('total_elevations', 0)} elevations")
            print(f"   - Returned {len(result.get('data', []))} directories")
            return True
        else:
            print(f"❌ Elevation tree API failed: {result}")
            return False
            
    except Exception as e:
        print(f"❌ Elevation tree API test failed: {e}")
        return False
    finally:
        if 'db' in locals():
            db.close()


async def test_elevation_search_api():
    """Test the elevation search API endpoint"""
    
    print("\n🧪 Testing Elevation Search API...")
    
    try:
        from routers.elevation_ui import search_elevations
        from core.database import get_db
        
        # Get database session
        db = next(get_db())
        
        # Test the API function with a common search term
        result = await search_elevations(q="test", limit=10, db=db)
        
        if result.get("success"):
            print("✅ Elevation search API call successful")
            print(f"   - Found {result.get('total_found', 0)} results")
            return True
        else:
            print(f"❌ Elevation search API failed: {result}")
            return False
            
    except Exception as e:
        print(f"❌ Elevation search API test failed: {e}")
        return False
    finally:
        if 'db' in locals():
            db.close()


async def test_elevation_ui_template_serving():
    """Test that the elevation UI template can be served"""
    
    print("\n🧪 Testing Elevation UI Template Serving...")
    
    try:
        from routers.elevation_ui import get_elevation_ui
        
        # Test the template serving function
        result = await get_elevation_ui()
        
        if hasattr(result, 'body'):
            content = result.body.decode('utf-8')
            if "Elevation Manager" in content and "file-tree" in content:
                print("✅ Elevation UI template serving successful")
                print(f"   - Template size: {len(content)} characters")
                return True
            else:
                print("❌ Elevation UI template missing required content")
                return False
        else:
            print("❌ Elevation UI template serving failed")
            return False
            
    except Exception as e:
        print(f"❌ Elevation UI template serving test failed: {e}")
        return False


async def test_elevation_detail_api():
    """Test the elevation detail API endpoint"""
    
    print("\n🧪 Testing Elevation Detail API...")
    
    try:
        from routers.elevation_ui import get_elevation_detail
        from core.database import get_db
        from models.elevation import Elevation
        
        # Get database session
        db = next(get_db())
        
        # Find the first elevation in the database
        first_elevation = db.query(Elevation).first()
        
        if not first_elevation:
            print("⚠️  No elevations found in database - skipping detail test")
            return True
        
        # Test the API function
        result = await get_elevation_detail(elevation_id=first_elevation.id, db=db)
        
        if result.get("success"):
            elevation_data = result.get("data", {}).get("elevation", {})
            print("✅ Elevation detail API call successful")
            print(f"   - Elevation: {elevation_data.get('name', 'Unknown')}")
            print(f"   - Parse status: {elevation_data.get('parse_status', 'Unknown')}")
            return True
        else:
            print(f"❌ Elevation detail API failed: {result}")
            return False
            
    except Exception as e:
        print(f"❌ Elevation detail API test failed: {e}")
        return False
    finally:
        if 'db' in locals():
            db.close()


async def main():
    """Run all integration tests"""
    
    print("🚀 Starting Elevation UI API Integration Tests")
    print("=" * 60)
    
    tests = [
        test_elevation_tree_api,
        test_elevation_search_api,
        test_elevation_detail_api,
        test_elevation_ui_template_serving
    ]
    
    passed = 0
    total = len(tests)
    
    for test in tests:
        if asyncio.iscoroutinefunction(test):
            if await test():
                passed += 1
        else:
            if test():
                passed += 1
        print()
    
    print("=" * 60)
    print(f"📊 Integration Test Results: {passed}/{total} tests passed")
    
    if passed == total:
        print("🎉 All integration tests passed! API endpoints are working correctly.")
        print("\n📋 Ready for Manual Testing:")
        print("1. Start the middleware server: uvicorn app.main:app --reload")
        print("2. Navigate to: http://localhost:8000/admin")
        print("3. Click 'Browse Elevations' to access the new UI")
        print("4. Test file tree navigation and elevation detail views")
        return True
    else:
        print("❌ Some integration tests failed. Please check the implementation.")
        return False


if __name__ == "__main__":
    success = asyncio.run(main())
    sys.exit(0 if success else 1)
