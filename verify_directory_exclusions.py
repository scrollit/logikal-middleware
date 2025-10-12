#!/usr/bin/env python3
"""
Verify Directory Exclusions in DigitalOcean Database

This script connects to the production database and shows:
1. All directories with their exclusion status
2. Count of projects in excluded vs non-excluded directories
3. Which projects would be synced to Odoo
"""

import sys
import os
from sqlalchemy import create_engine, text
from sqlalchemy.orm import sessionmaker
from tabulate import tabulate


def get_database_url():
    """Get database URL from environment or prompt user"""
    database_url = os.environ.get('DATABASE_URL')
    
    if not database_url:
        print("\n⚠️  DATABASE_URL not found in environment variables")
        print("\nPlease provide the DATABASE_URL from DigitalOcean:")
        print("   (Go to DigitalOcean App Platform → logikal-middleware → Settings → App-Level Environment Variables)")
        print("   Look for: DATABASE_URL")
        database_url = input("\nEnter DATABASE_URL: ").strip()
    
    # Fix postgres:// to postgresql:// for SQLAlchemy compatibility
    if database_url.startswith("postgres://"):
        database_url = database_url.replace("postgres://", "postgresql://", 1)
    
    return database_url


def main():
    """Main verification function"""
    print("=" * 80)
    print("🔍 DIRECTORY EXCLUSION VERIFICATION - DigitalOcean Production Database")
    print("=" * 80)
    print()
    
    try:
        # Get database connection
        database_url = get_database_url()
        print(f"✅ Connecting to database...")
        
        engine = create_engine(database_url, echo=False)
        Session = sessionmaker(bind=engine)
        session = Session()
        
        print(f"✅ Connected successfully!\n")
        
        # Query 1: Get all directories with exclusion status
        print("=" * 80)
        print("📁 ALL DIRECTORIES IN DATABASE")
        print("=" * 80)
        print()
        
        query = text("""
            SELECT 
                id,
                name,
                full_path,
                level,
                exclude_from_sync,
                parent_id,
                (SELECT COUNT(*) FROM projects WHERE directory_id = directories.id) as project_count
            FROM directories
            ORDER BY full_path NULLS FIRST, name
        """)
        
        result = session.execute(query)
        directories = result.fetchall()
        
        if not directories:
            print("⚠️  No directories found in database!")
            return
        
        # Format directory data for display
        dir_data = []
        excluded_count = 0
        syncable_count = 0
        
        for row in directories:
            status = "❌ EXCLUDED" if row.exclude_from_sync else "✅ SYNCABLE"
            if row.exclude_from_sync:
                excluded_count += 1
            else:
                syncable_count += 1
            
            dir_data.append([
                row.id,
                row.name[:40] if row.name else "N/A",
                row.full_path[:50] if row.full_path else "N/A",
                row.level,
                status,
                row.project_count
            ])
        
        headers = ["ID", "Name", "Full Path", "Level", "Status", "Projects"]
        print(tabulate(dir_data, headers=headers, tablefmt="grid"))
        
        print()
        print(f"📊 Directory Summary:")
        print(f"   • Total directories: {len(directories)}")
        print(f"   • Syncable directories: {syncable_count}")
        print(f"   • Excluded directories: {excluded_count}")
        print()
        
        # Query 2: Get project counts by exclusion status
        print("=" * 80)
        print("📦 PROJECT DISTRIBUTION")
        print("=" * 80)
        print()
        
        query = text("""
            SELECT 
                d.exclude_from_sync,
                COUNT(p.id) as project_count
            FROM projects p
            INNER JOIN directories d ON p.directory_id = d.id
            GROUP BY d.exclude_from_sync
        """)
        
        result = session.execute(query)
        project_counts = result.fetchall()
        
        syncable_projects = 0
        excluded_projects = 0
        
        for row in project_counts:
            if row.exclude_from_sync:
                excluded_projects = row.project_count
            else:
                syncable_projects = row.project_count
        
        print(f"   ✅ Projects in SYNCABLE directories: {syncable_projects}")
        print(f"   ❌ Projects in EXCLUDED directories: {excluded_projects}")
        print(f"   📊 Total projects: {syncable_projects + excluded_projects}")
        print()
        
        # Query 3: Show which projects would be synced to Odoo
        if syncable_projects > 0:
            print("=" * 80)
            print("📋 PROJECTS THAT WOULD BE SYNCED TO ODOO")
            print("=" * 80)
            print()
            
            query = text("""
                SELECT 
                    p.id,
                    p.logikal_id,
                    p.name,
                    d.name as directory_name,
                    d.full_path
                FROM projects p
                INNER JOIN directories d ON p.directory_id = d.id
                WHERE d.exclude_from_sync = FALSE
                ORDER BY d.full_path NULLS FIRST, p.name
                LIMIT 50
            """)
            
            result = session.execute(query)
            syncable_projects_list = result.fetchall()
            
            project_data = []
            for row in syncable_projects_list:
                project_data.append([
                    row.logikal_id[:30] if row.logikal_id else "N/A",
                    row.name[:40] if row.name else "N/A",
                    row.directory_name[:30] if row.directory_name else "N/A",
                    row.full_path[:50] if row.full_path else "N/A"
                ])
            
            headers = ["Logikal ID", "Project Name", "Directory", "Full Path"]
            print(tabulate(project_data, headers=headers, tablefmt="grid"))
            
            if len(syncable_projects_list) == 50:
                print(f"\n(Showing first 50 of {syncable_projects} syncable projects)")
            else:
                print(f"\n(Showing all {len(syncable_projects_list)} syncable projects)")
        
        print()
        
        # Query 4: Show excluded projects (if any)
        if excluded_projects > 0:
            print("=" * 80)
            print("🚫 PROJECTS EXCLUDED FROM ODOO SYNC")
            print("=" * 80)
            print()
            
            query = text("""
                SELECT 
                    p.id,
                    p.logikal_id,
                    p.name,
                    d.name as directory_name,
                    d.full_path
                FROM projects p
                INNER JOIN directories d ON p.directory_id = d.id
                WHERE d.exclude_from_sync = TRUE
                ORDER BY d.full_path NULLS FIRST, p.name
                LIMIT 50
            """)
            
            result = session.execute(query)
            excluded_projects_list = result.fetchall()
            
            project_data = []
            for row in excluded_projects_list:
                project_data.append([
                    row.logikal_id[:30] if row.logikal_id else "N/A",
                    row.name[:40] if row.name else "N/A",
                    row.directory_name[:30] if row.directory_name else "N/A",
                    row.full_path[:50] if row.full_path else "N/A"
                ])
            
            headers = ["Logikal ID", "Project Name", "Directory", "Full Path"]
            print(tabulate(project_data, headers=headers, tablefmt="grid"))
            
            if len(excluded_projects_list) == 50:
                print(f"\n(Showing first 50 of {excluded_projects} excluded projects)")
            else:
                print(f"\n(Showing all {len(excluded_projects_list)} excluded projects)")
        
        print()
        print("=" * 80)
        print("✅ VERIFICATION COMPLETE")
        print("=" * 80)
        print()
        print(f"🎯 SUMMARY:")
        print(f"   When you run 'Sync All Projects' in Odoo, it will sync:")
        print(f"   → {syncable_projects} projects from {syncable_count} syncable directories")
        print(f"   → {excluded_projects} projects from {excluded_count} excluded directories will be IGNORED")
        print()
        
        session.close()
        
    except Exception as e:
        print(f"\n❌ Error: {str(e)}")
        print(f"\nFull error details:")
        import traceback
        traceback.print_exc()
        sys.exit(1)


if __name__ == "__main__":
    main()

