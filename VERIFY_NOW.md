# ✅ Verify Directory Exclusions NOW - Quick Guide

## 🎯 What This Does

This script connects to your **live production middleware** at:
**https://logikal-middleware-avwpu.ondigitalocean.app**

It will show you:
- ✅ Which directories are syncable
- ❌ Which directories are excluded
- 📋 The EXACT list of projects that Odoo receives when you click "Sync All Projects"

---

## 🚀 Run the Verification (2 minutes)

### Step 1: Get Your Credentials

You need the **client credentials** that are configured in Odoo:

1. Open Odoo
2. Go to **Settings** → **General Settings**
3. Scroll to **Logikal Middleware Configuration**
4. Note down:
   - **Client ID** (e.g., `odoo_uat`)
   - **Client Secret** (the password)

### Step 2: Run the Script

```bash
cd ~/clients/logikal-middleware-dev
python3 verify_exclusions_via_api.py
```

The script will prompt you for:
- Client ID
- Client Secret

### Step 3: Review the Results

The script will show you:

```
================================================================================
🔍 DIRECTORY EXCLUSION VERIFICATION
================================================================================
Middleware URL: https://logikal-middleware-avwpu.ondigitalocean.app

Please provide middleware API credentials:
Client ID (e.g., odoo_uat): [YOUR_CLIENT_ID]
Client Secret: [YOUR_CLIENT_SECRET]

🔐 Authenticating with middleware...
✅ Authentication successful!

================================================================================
📁 FETCHING DIRECTORIES...
================================================================================

✅ Found 25 directories
   • Syncable: 20
   • Excluded: 5

================================================================================
✅ SYNCABLE DIRECTORIES (will sync to Odoo)
================================================================================

  ✅ /Production/Active Projects                                (45 projects)
  ✅ /Production/Current                                        (32 projects)
  ...

================================================================================
❌ EXCLUDED DIRECTORIES (will NOT sync to Odoo)
================================================================================

  ❌ /Test/Archive                                              (12 projects)
  ❌ /Demo/Samples                                              (8 projects)
  ...

================================================================================
📦 FETCHING PROJECTS THAT WOULD BE SYNCED TO ODOO...
================================================================================

✅ The /api/v1/odoo/projects endpoint returned: 77 projects

This is the EXACT list that Odoo receives when you click 'Sync All Projects'

================================================================================
📋 PROJECTS THAT WILL BE SYNCED (first 50)
================================================================================

    1. Project Alpha                                           (ID: abc123...)
    2. Project Beta                                            (ID: def456...)
    ...

================================================================================
✅ VERIFICATION COMPLETE
================================================================================

🎯 SUMMARY:
   When you click 'Sync All Projects' in Odoo:
   → Odoo will receive 77 projects
   → These projects are from 20 syncable directories
   → Projects from 5 excluded directories are NOT included

✅ Directory exclusions are working correctly!
```

---

## 🔍 What This Proves

The script calls the **SAME API endpoint** that Odoo uses:
- URL: `https://logikal-middleware-avwpu.ondigitalocean.app/api/v1/odoo/projects`
- This endpoint filters out projects from excluded directories
- The returned list is **exactly** what Odoo receives

**Result**: You can verify that directory exclusions are working in production! ✅

---

## 📊 Understanding the Output

### Syncable Directories
- Directories with `exclude_from_sync = FALSE`
- Projects in these directories **WILL** be synced to Odoo

### Excluded Directories
- Directories with `exclude_from_sync = TRUE`
- Projects in these directories **WILL NOT** be synced to Odoo

### Projects List
- This is the filtered list from `/api/v1/odoo/projects`
- Only includes projects from syncable directories
- Projects from excluded directories are not in this list

---

## 🔧 Optional: Test the API Directly

You can also test the API using curl:

```bash
# Step 1: Get access token
ACCESS_TOKEN=$(curl -s -X POST https://logikal-middleware-avwpu.ondigitalocean.app/api/v1/client-auth/login \
  -H "Content-Type: application/json" \
  -d '{"client_id":"YOUR_CLIENT_ID","client_secret":"YOUR_CLIENT_SECRET"}' \
  | grep -o '"access_token":"[^"]*' | cut -d'"' -f4)

# Step 2: Get directories
curl -H "Authorization: Bearer $ACCESS_TOKEN" \
  https://logikal-middleware-avwpu.ondigitalocean.app/api/v1/directories | jq .

# Step 3: Get projects for Odoo (filtered by exclusions)
curl -H "Authorization: Bearer $ACCESS_TOKEN" \
  https://logikal-middleware-avwpu.ondigitalocean.app/api/v1/odoo/projects | jq .
```

---

## ✅ Conclusion

After running the verification, you'll have definitive proof that:

1. ✅ Directory exclusions are properly configured
2. ✅ The middleware is filtering projects correctly
3. ✅ Odoo only receives projects from non-excluded directories
4. ✅ The `/api/v1/odoo/projects` endpoint respects exclusions

**The directory exclusion mechanism is working as designed!** 🎉

