# Guide: Verify Directory Exclusions in Production

This guide helps you verify which directories are excluded from sync and which projects would be synced to Odoo when running `action_sync_all_projects`.

## 🎯 What This Verifies

When you click "Sync All Projects" in Odoo's Logikal Operations screen, the middleware filters projects based on directory exclusion settings. This verification shows:

- ✅ All directories with their exclusion status
- ✅ How many projects are in excluded vs. syncable directories
- ✅ Exactly which projects would be synced to Odoo
- ✅ Which projects are excluded from sync

---

## 📋 Prerequisites

You need the **DATABASE_URL** from your DigitalOcean App Platform deployment.

### How to Get DATABASE_URL

1. **Login to DigitalOcean**:
   - Go to [https://cloud.digitalocean.com](https://cloud.digitalocean.com)

2. **Navigate to Your App**:
   - Click "Apps" in the left sidebar
   - Click on your app: `logikal-middleware`

3. **Get Database URL**:
   - Click on "Settings" tab
   - Scroll to "App-Level Environment Variables"
   - Find `DATABASE_URL` (it's marked as SECRET)
   - Click the "eye" icon to reveal the value
   - Copy the entire connection string

   It will look like:
   ```
   postgresql://username:password@host:25060/dbname?sslmode=require
   ```

---

## 🐍 Method 1: Python Script (Recommended)

This method provides a formatted, easy-to-read output.

### Installation

Install required dependencies:

```bash
cd ~/clients/logikal-middleware-dev
pip install sqlalchemy psycopg2-binary tabulate
```

### Run the Script

**Option A: With DATABASE_URL in environment:**

```bash
export DATABASE_URL="postgresql://username:password@host:25060/dbname?sslmode=require"
python3 verify_directory_exclusions.py
```

**Option B: Script will prompt you for DATABASE_URL:**

```bash
python3 verify_directory_exclusions.py
```

Then paste the DATABASE_URL when prompted.

### Expected Output

```
================================================================================
🔍 DIRECTORY EXCLUSION VERIFICATION - DigitalOcean Production Database
================================================================================

✅ Connecting to database...
✅ Connected successfully!

================================================================================
📁 ALL DIRECTORIES IN DATABASE
================================================================================

╔════╤══════════════════════════════════════════╤════════════════════════════════════════════════╤═══════╤═══════════════╤══════════╗
║ ID │ Name                                     │ Full Path                                      │ Level │ Status        │ Projects ║
╠════╪══════════════════════════════════════════╪════════════════════════════════════════════════╪═══════╪═══════════════╪══════════╣
║  1 │ Root Directory                           │ /                                              │     0 │ ✅ SYNCABLE   │       25 ║
║  2 │ Test Projects                            │ /Test Projects                                 │     1 │ ❌ EXCLUDED   │       12 ║
║  3 │ Production                               │ /Production                                    │     1 │ ✅ SYNCABLE   │       45 ║
╚════╧══════════════════════════════════════════╧════════════════════════════════════════════════╧═══════╧═══════════════╧══════════╝

📊 Directory Summary:
   • Total directories: 3
   • Syncable directories: 2
   • Excluded directories: 1

================================================================================
📦 PROJECT DISTRIBUTION
================================================================================

   ✅ Projects in SYNCABLE directories: 70
   ❌ Projects in EXCLUDED directories: 12
   📊 Total projects: 82

================================================================================
📋 PROJECTS THAT WOULD BE SYNCED TO ODOO
================================================================================

(Shows first 50 syncable projects in a table)

================================================================================
🚫 PROJECTS EXCLUDED FROM ODOO SYNC
================================================================================

(Shows first 50 excluded projects in a table)

================================================================================
✅ VERIFICATION COMPLETE
================================================================================

🎯 SUMMARY:
   When you run 'Sync All Projects' in Odoo, it will sync:
   → 70 projects from 2 syncable directories
   → 12 projects from 1 excluded directories will be IGNORED
```

---

## 🐘 Method 2: Direct SQL Query (Alternative)

If you prefer using PostgreSQL's `psql` command-line tool.

### Installation

Install PostgreSQL client:

```bash
# Ubuntu/Debian
sudo apt-get install postgresql-client

# macOS
brew install postgresql
```

### Run the SQL Script

```bash
cd ~/clients/logikal-middleware-dev
psql "postgresql://username:password@host:25060/dbname?sslmode=require" -f verify_directories.sql
```

Replace the connection string with your actual DATABASE_URL.

### Expected Output

The SQL script will display similar information in PostgreSQL's table format.

---

## 📊 Understanding the Results

### Directory Status

- **✅ SYNCABLE**: Projects in this directory **WILL BE** synced to Odoo
- **❌ EXCLUDED**: Projects in this directory **WILL NOT BE** synced to Odoo

### Key Metrics

1. **Syncable directories**: Directories where `exclude_from_sync = FALSE`
2. **Excluded directories**: Directories where `exclude_from_sync = TRUE`
3. **Syncable projects**: Projects that will be synced to Odoo
4. **Excluded projects**: Projects that will be ignored during sync

### Important Notes

- The exclusion filter is applied at the **middleware level**
- Odoo **never sees** projects from excluded directories
- The filtering happens via SQL JOIN on the `directories` table
- Parent directory exclusion cascades to child directories

---

## 🔧 How to Change Exclusion Settings

If you need to exclude or include directories:

### Option 1: Via Admin UI

1. Go to: `https://your-app-url.ondigitalocean.app/ui`
2. Login with admin credentials
3. Navigate to "Directories" section
4. Toggle the "Exclude from Sync" checkbox for each directory
5. Changes take effect immediately

### Option 2: Via API

```bash
# Exclude a directory
curl -X PATCH https://your-app-url.ondigitalocean.app/api/v1/directories/123/exclusion \
  -H "Authorization: Bearer YOUR_TOKEN" \
  -H "Content-Type: application/json" \
  -d '{"exclude": true}'

# Include a directory (un-exclude)
curl -X PATCH https://your-app-url.ondigitalocean.app/api/v1/directories/123/exclusion \
  -H "Authorization: Bearer YOUR_TOKEN" \
  -H "Content-Type: application/json" \
  -d '{"exclude": false}'
```

### Option 3: Direct SQL (Advanced)

```sql
-- Exclude a directory
UPDATE directories SET exclude_from_sync = TRUE WHERE id = 123;

-- Include a directory
UPDATE directories SET exclude_from_sync = FALSE WHERE id = 123;
```

---

## 🎯 Summary

The verification confirms:

1. ✅ Directory exclusions are properly stored in the database
2. ✅ The middleware filters projects based on `exclude_from_sync` flag
3. ✅ Only projects from syncable directories are returned to Odoo
4. ✅ The SQL JOIN ensures excluded projects never reach Odoo

**Result**: When you run `action_sync_all_projects` in Odoo, only projects from non-excluded directories will be synced. The filtering is enforced at the database level in the middleware.

---

## 🆘 Troubleshooting

### Connection Error

If you get a connection error:

1. Verify the DATABASE_URL is correct (copy from DigitalOcean)
2. Check that the database is running (DigitalOcean → Databases)
3. Verify SSL is enabled in the connection string (`?sslmode=require`)

### No Directories Found

If no directories are shown:

1. Verify that directories have been synced from Logikal
2. Run the directory sync first via Odoo or middleware UI
3. Check the middleware logs for sync errors

### Permission Denied

If you get permission errors:

1. Verify you're using the correct DATABASE_URL
2. Check that the database user has SELECT permissions
3. Contact DigitalOcean support if the issue persists

---

## 📞 Support

If you encounter issues:

1. Check the middleware logs in DigitalOcean App Platform
2. Review the deployment documentation
3. Verify environment variables are set correctly
4. Contact your system administrator

