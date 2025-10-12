-- SQL Script to Verify Directory Exclusions in DigitalOcean Database
-- Run this with: psql "YOUR_DATABASE_URL" -f verify_directories.sql

\echo '================================================================================'
\echo 'DIRECTORY EXCLUSION VERIFICATION - DigitalOcean Production Database'
\echo '================================================================================'
\echo ''

-- Show all directories with exclusion status
\echo '================================================================================'
\echo 'ALL DIRECTORIES IN DATABASE'
\echo '================================================================================'
\echo ''

SELECT 
    id,
    LEFT(name, 40) as name,
    LEFT(full_path, 50) as full_path,
    level,
    CASE 
        WHEN exclude_from_sync = TRUE THEN '❌ EXCLUDED'
        ELSE '✅ SYNCABLE'
    END as status,
    (SELECT COUNT(*) FROM projects WHERE directory_id = directories.id) as project_count
FROM directories
ORDER BY full_path NULLS FIRST, name;

\echo ''
\echo '================================================================================'
\echo 'DIRECTORY SUMMARY'
\echo '================================================================================'
\echo ''

SELECT 
    COUNT(*) as total_directories,
    COUNT(*) FILTER (WHERE exclude_from_sync = FALSE) as syncable_directories,
    COUNT(*) FILTER (WHERE exclude_from_sync = TRUE) as excluded_directories
FROM directories;

\echo ''
\echo '================================================================================'
\echo 'PROJECT DISTRIBUTION'
\echo '================================================================================'
\echo ''

SELECT 
    CASE 
        WHEN d.exclude_from_sync = TRUE THEN '❌ EXCLUDED from sync'
        ELSE '✅ SYNCABLE to Odoo'
    END as status,
    COUNT(p.id) as project_count
FROM projects p
INNER JOIN directories d ON p.directory_id = d.id
GROUP BY d.exclude_from_sync
ORDER BY d.exclude_from_sync;

\echo ''
\echo '================================================================================'
\echo 'PROJECTS THAT WOULD BE SYNCED TO ODOO (first 50)'
\echo '================================================================================'
\echo ''

SELECT 
    LEFT(p.logikal_id, 30) as logikal_id,
    LEFT(p.name, 40) as project_name,
    LEFT(d.name, 30) as directory_name,
    LEFT(d.full_path, 50) as full_path
FROM projects p
INNER JOIN directories d ON p.directory_id = d.id
WHERE d.exclude_from_sync = FALSE
ORDER BY d.full_path NULLS FIRST, p.name
LIMIT 50;

\echo ''
\echo '================================================================================'
\echo 'PROJECTS EXCLUDED FROM ODOO SYNC (first 50)'
\echo '================================================================================'
\echo ''

SELECT 
    LEFT(p.logikal_id, 30) as logikal_id,
    LEFT(p.name, 40) as project_name,
    LEFT(d.name, 30) as directory_name,
    LEFT(d.full_path, 50) as full_path
FROM projects p
INNER JOIN directories d ON p.directory_id = d.id
WHERE d.exclude_from_sync = TRUE
ORDER BY d.full_path NULLS FIRST, p.name
LIMIT 50;

\echo ''
\echo '================================================================================'
\echo 'VERIFICATION COMPLETE'
\echo '================================================================================'
\echo ''

