#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
Direct Middleware Database Check

This script directly checks the middleware database for parser-related issues.
"""

import sys
import os
sys.path.append('.')

from collections import defaultdict
from sqlalchemy import create_engine, text
from sqlalchemy.orm import sessionmaker

def check_middleware_data():
    """Check middleware database for parser issues"""
    
    print("🔍 Checking middleware database for parser issues...")
    print("=" * 60)
    
    try:
        # Connect to middleware database
        database_url = "postgresql://admin:admin@localhost:5433/logikal_middleware"
        engine = create_engine(database_url)
        Session = sessionmaker(bind=engine)
        session = Session()
        
        # Get all elevations with their project and phase info
        query = text("""
            SELECT 
                e.id,
                e.logikal_id,
                e.name,
                e.system_name,
                e.parts_count,
                e.parse_status,
                p.name as project_name,
                ph.name as phase_name
            FROM elevations e
            LEFT JOIN projects p ON e.project_id = p.id
            LEFT JOIN phases ph ON e.phase_id = ph.id
            ORDER BY e.name, p.name
        """)
        
        result = session.execute(query)
        elevations = result.fetchall()
        
        print(f"✅ Fetched {len(elevations)} elevations from middleware database")
        
        # Analyze data for parser issues
        print("\n🔍 Analyzing data for parser issues...")
        
        # Group by elevation name
        by_name = defaultdict(list)
        for elev in elevations:
            by_name[elev.name].append(elev)
        
        parser_issues = []
        for name, elevs in by_name.items():
            if len(elevs) > 1:
                systems = set(e.system_name for e in elevs if e.system_name)
                parts_counts = set(e.parts_count for e in elevs if e.parts_count is not None)
                projects = set(e.project_name for e in elevs if e.project_name)
                
                if len(systems) == 1 and len(parts_counts) == 1 and len(projects) > 1:
                    parser_issues.append({
                        'name': name,
                        'system_name': list(systems)[0],
                        'parts_count': list(parts_counts)[0],
                        'projects': list(projects),
                        'count': len(elevs),
                        'elevations': elevs
                    })
        
        # Display results
        print(f"\n📊 MIDDLEWARE DATABASE ANALYSIS:")
        print(f"Total Elevations: {len(elevations)}")
        print(f"Unique Elevation Names: {len(by_name)}")
        print(f"Parser Issues Detected: {len(parser_issues)}")
        
        if parser_issues:
            print(f"\n🚨 PARSER ISSUES DETECTED:")
            print("The following elevation names have identical system names and parts counts across different projects:")
            print("This confirms the SQLite parser is applying the same data to different elevations.")
            print()
            
            for issue in parser_issues:
                print(f"📋 Elevation: '{issue['name']}'")
                print(f"   System: {issue['system_name']}")
                print(f"   Parts Count: {issue['parts_count']}")
                print(f"   Projects: {', '.join(issue['projects'])}")
                print(f"   Instances: {issue['count']}")
                print(f"   Logikal IDs: {[e.logikal_id for e in issue['elevations']]}")
                print()
        else:
            print("✅ No parser issues detected in middleware database")
        
        # Check for other patterns
        print("\n🔍 Checking for other data patterns...")
        
        # Group by system name
        by_system = defaultdict(list)
        for elev in elevations:
            if elev.system_name:
                by_system[elev.system_name].append(elev)
        
        print(f"Unique System Names: {len(by_system)}")
        
        # Show most common systems
        system_counts = [(system, len(elevs)) for system, elevs in by_system.items()]
        system_counts.sort(key=lambda x: x[1], reverse=True)
        
        print("\n📈 Most Common System Names:")
        for system, count in system_counts[:5]:
            print(f"   {system}: {count} elevations")
        
        # Group by parts count
        by_parts = defaultdict(list)
        for elev in elevations:
            if elev.parts_count is not None:
                by_parts[elev.parts_count].append(elev)
        
        print(f"\n📊 Parts Count Distribution:")
        parts_counts = [(count, len(elevs)) for count, elevs in by_parts.items()]
        parts_counts.sort(key=lambda x: x[1], reverse=True)
        
        for count, elev_count in parts_counts[:5]:
            print(f"   {count} parts: {elev_count} elevations")
        
        # Check parse status
        parse_statuses = defaultdict(int)
        for elev in elevations:
            parse_statuses[elev.parse_status or 'unknown'] += 1
        
        print(f"\n📋 Parse Status Distribution:")
        for status, count in parse_statuses.items():
            print(f"   {status}: {count} elevations")
        
        print("\n" + "=" * 60)
        
        if parser_issues:
            print("🚨 CONCLUSION: Parser issues confirmed in middleware database.")
            print("   The SQLite parser fix should resolve these issues.")
            print("   After applying the fix, re-parse the affected elevations.")
        else:
            print("✅ No parser issues detected in middleware database.")
        
        session.close()
        
        return {
            'total_elevations': len(elevations),
            'parser_issues': len(parser_issues),
            'parser_issues_details': parser_issues
        }
        
    except Exception as e:
        print(f"❌ Error: {str(e)}")
        return None

if __name__ == "__main__":
    check_middleware_data()
