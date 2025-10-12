# Enable Scheduled Sync - Step-by-Step Checklist

## 📋 Prerequisites

Before starting, ensure you have:

- [ ] Access to DigitalOcean App Platform dashboard
- [ ] Access to GitHub repository: `scrollit/logikal-middleware`
- [ ] Admin access to middleware admin UI
- [ ] Budget approval for ~$22-25/month additional cost
- [ ] Time to monitor for 48-72 hours after deployment

---

## 🚀 Option 1: Single Container (Recommended for Testing)

### Phase 1: Deploy Redis Infrastructure

#### Step 1.1: Add Redis to DigitalOcean App Platform

**Location**: DigitalOcean Dashboard → Apps → logikal-middleware → Settings → Resources

- [ ] Click "Add Resource" → "Database"
- [ ] Select "Redis" as engine
- [ ] Choose version "7"
- [ ] Select size: "db-s-dev-database" (~$15/month)
- [ ] Name: `logikal-redis`
- [ ] Click "Add Resource"
- [ ] Wait for Redis to deploy (5-10 minutes)

**Expected result**: New Redis database visible in Resources tab

#### Step 1.2: Get Redis Connection URL

**Location**: DigitalOcean Dashboard → Apps → logikal-middleware → Resources → logikal-redis

- [ ] Click on "logikal-redis"
- [ ] Copy the connection string (format: `rediss://...`)
- [ ] Save this securely (you'll need it in next step)

**Expected format**: `rediss://default:password@host:port`

---

### Phase 2: Update Environment Variables

#### Step 2.1: Update REDIS_URL

**Location**: DigitalOcean Dashboard → Apps → logikal-middleware → Settings → Environment Variables

- [ ] Find variable `REDIS_URL`
- [ ] If exists: Click "Edit"
- [ ] If not exists: Click "Add Variable"
- [ ] Set value to Redis connection string from Step 1.2
- [ ] Type: SECRET
- [ ] Click "Save"

#### Step 2.2: Update BACKGROUND_SYNC_ENABLED

**Location**: Same as above (Environment Variables)

- [ ] Find variable `BACKGROUND_SYNC_ENABLED`
- [ ] Click "Edit"
- [ ] Change value from `"false"` to `"true"`
- [ ] Type: Public
- [ ] Click "Save"

#### Step 2.3: Optional - Adjust Sync Interval

**Location**: Same as above (Environment Variables)

- [ ] Find variable `SYNC_INTERVAL_SECONDS`
- [ ] Current value: `"300"` (5 minutes)
- [ ] Recommended for testing: `"3600"` (1 hour)
- [ ] Click "Edit" and update if desired
- [ ] Click "Save"

---

### Phase 3: Upgrade Instance Size (Recommended)

**Location**: DigitalOcean Dashboard → Apps → logikal-middleware → Settings → Resources

#### Current: basic-xxs (512MB RAM, 1 vCPU, $5/month)
#### Recommended: basic-xs (1GB RAM, 1 vCPU, $12/month)

- [ ] Click on "logikal-middleware" service
- [ ] Click "Edit Plan"
- [ ] Select "basic-xs"
- [ ] Click "Save"

**Why?**: Running web server + Celery worker + Celery beat on 512MB is very tight.

**Alternative**: Skip this step initially and monitor RAM usage. Upgrade if needed.

---

### Phase 4: Update .do/app.yaml (Optional but Recommended)

**Location**: GitHub repository → `.do/app.yaml`

This ensures configuration persists across deployments.

```yaml
# Find this section (around line 47-48):
- key: BACKGROUND_SYNC_ENABLED
  value: "false"  # ❌ OLD

# Change to:
- key: BACKGROUND_SYNC_ENABLED
  value: "true"  # ✅ NEW

# Also update REDIS_URL (around line 23-24):
- key: REDIS_URL
  type: SECRET
  # Will be auto-filled by DigitalOcean if Redis is named logikal-redis
  value: ${logikal-redis.REDIS_URL}  # Add this line
```

- [ ] Clone repository locally
- [ ] Edit `.do/app.yaml`
- [ ] Update `BACKGROUND_SYNC_ENABLED` to `"true"`
- [ ] Update `REDIS_URL` to reference Redis database
- [ ] Commit changes
- [ ] Push to GitHub
- [ ] DigitalOcean will auto-deploy

**Note**: If you updated environment variables via dashboard (Steps 2.1-2.2), they override the YAML file.

---

### Phase 5: Trigger Deployment

**Location**: DigitalOcean Dashboard → Apps → logikal-middleware

- [ ] Click "Deploy" button (if not auto-deploying)
- [ ] Or push a commit to trigger auto-deployment
- [ ] Wait for deployment to complete (5-10 minutes)
- [ ] Watch build logs for errors

**Expected logs to see**:
```
"Starting Logikal Middleware with Celery services..."
"Background sync is enabled, starting Celery services..."
"Started Celery worker process (PID: xxxxx)"
"Started Celery beat process (PID: xxxxx)"
"Starting FastAPI application..."
```

---

### Phase 6: Verify Deployment

#### Step 6.1: Check Application Health

- [ ] Navigate to: `https://logikal-middleware-xxxxx.ondigitalocean.app/api/v1/health`
- [ ] Expected response: `{"status": "healthy"}`

#### Step 6.2: Check Runtime Logs

**Location**: DigitalOcean Dashboard → Apps → logikal-middleware → Runtime Logs

**Look for these log entries:**

- [ ] ✅ "Background sync is enabled"
- [ ] ✅ "Starting Celery worker process"
- [ ] ✅ "Starting Celery beat process"
- [ ] ✅ "Starting smart sync scheduler task"
- [ ] ✅ "Found X enabled sync configurations"

**Red flags (should NOT see):**

- [ ] ❌ "Background sync is disabled"
- [ ] ❌ "Redis connection failed"
- [ ] ❌ "Celery worker failed"

#### Step 6.3: Check Admin UI

**Location**: `https://logikal-middleware-xxxxx.ondigitalocean.app/ui`

- [ ] Login with admin credentials
- [ ] Navigate to "Sync Intervals" section
- [ ] Verify sync configurations are visible
- [ ] Check "Last Sync" column (should update within 5-60 minutes)

**Expected**: Table showing directories, projects, phases, elevations with their sync intervals.

#### Step 6.4: Monitor First Sync Execution

**Wait 5-60 minutes (depending on your SYNC_INTERVAL_SECONDS)**

**Then check:**

- [ ] Runtime logs show: "Starting smart sync scheduler task"
- [ ] Admin UI shows updated "Last Sync" timestamps
- [ ] No errors in logs
- [ ] Database shows updated records

---

### Phase 7: Monitor and Tune (First 48 Hours)

#### Hour 1-4: Initial Monitoring

**Check every hour:**

- [ ] Runtime logs for errors
- [ ] CPU usage (DigitalOcean → Insights)
- [ ] Memory usage (should stay under 800MB on 1GB instance)
- [ ] Redis connection stable

**Red flags:**

- Memory usage > 90% → Upgrade instance size
- CPU usage constantly > 80% → Consider multi-container
- Redis connection errors → Check Redis status
- Sync task failures → Review logs

#### Day 1-2: Stability Check

**Check twice daily:**

- [ ] Sync tasks executing on schedule
- [ ] No memory leaks (RAM stays stable)
- [ ] No error patterns in logs
- [ ] Data freshness in Odoo

**If stable:**
- [ ] Consider reducing sync interval (e.g., 3600s → 1800s)

**If unstable:**
- [ ] Increase sync interval (e.g., 300s → 3600s)
- [ ] Review logs for specific errors
- [ ] Consider disabling temporarily

#### Week 1: Optimization

- [ ] Review sync durations per object type
- [ ] Adjust intervals via Admin UI
- [ ] Enable/disable sync for specific object types if needed
- [ ] Verify no conflicts with manual force sync

---

### Phase 8: Configuration Tuning

#### Recommended Starting Intervals (Conservative)

**Location**: Admin UI → Sync Intervals

```
Directories:
  - [ ] sync_interval_minutes: 240 (4 hours)
  - [ ] is_sync_enabled: true
  
Projects:
  - [ ] sync_interval_minutes: 120 (2 hours)
  - [ ] is_sync_enabled: true
  
Phases:
  - [ ] sync_interval_minutes: 60 (1 hour)
  - [ ] is_sync_enabled: true
  
Elevations:
  - [ ] sync_interval_minutes: 30 (30 minutes)
  - [ ] is_sync_enabled: true
```

**After 1 week of stability:**
- [ ] Consider reducing intervals by 50%
- [ ] Monitor impact on system load
- [ ] Adjust based on data freshness needs

---

## 🚀 Option 2: Multi-Container (Recommended for Production)

### Phase 1: Update .do/app.yaml

**Location**: GitHub repository → `.do/app.yaml`

#### Step 1.1: Add Redis Database

```yaml
databases:
- name: logikal-db
  engine: PG
  version: "15"
  size: db-s-dev-database
  num_nodes: 1

# Add this:
- name: logikal-redis
  engine: REDIS
  version: "7"
  size: db-s-dev-database
  num_nodes: 1
```

- [ ] Add Redis database configuration
- [ ] Save file

#### Step 1.2: Add Celery Worker Service

```yaml
services:
- name: logikal-middleware
  # ... existing config ...
  envs:
    - key: BACKGROUND_SYNC_ENABLED
      value: "false"  # Keep false for web service

# Add this new service:
- name: logikal-middleware-worker
  github:
    repo: scrollit/logikal-middleware
    branch: main
  run_command: celery -A celery_app worker --loglevel=info --queues=sync,scheduler,sqlite_parser
  instance_count: 1
  instance_size_slug: basic-xxs
  http_port: 8000
  dockerfile_path: Dockerfile
  envs:
    - key: ENVIRONMENT
      value: production
    - key: DEBUG
      value: "false"
    - key: BACKGROUND_SYNC_ENABLED
      value: "true"  # Enable for worker
    - key: REDIS_URL
      value: ${logikal-redis.REDIS_URL}
    - key: DATABASE_URL
      value: ${logikal-db.DATABASE_URL}
    - key: SECRET_KEY
      type: SECRET
    - key: JWT_SECRET_KEY
      type: SECRET
    - key: LOGIKAL_API_BASE_URL
      value: "http://128.199.57.77/MbioeService.svc/api/v3/"
    - key: LOGIKAL_AUTH_USERNAME
      type: SECRET
    - key: LOGIKAL_AUTH_PASSWORD
      type: SECRET
```

- [ ] Add worker service configuration
- [ ] Copy necessary environment variables from main service
- [ ] Save file

#### Step 1.3: Add Celery Beat Service

```yaml
# Add this new service:
- name: logikal-middleware-beat
  github:
    repo: scrollit/logikal-middleware
    branch: main
  run_command: celery -A celery_app beat --loglevel=info
  instance_count: 1
  instance_size_slug: basic-xxs
  http_port: 8000
  dockerfile_path: Dockerfile
  envs:
    - key: ENVIRONMENT
      value: production
    - key: DEBUG
      value: "false"
    - key: BACKGROUND_SYNC_ENABLED
      value: "true"  # Enable for beat
    - key: REDIS_URL
      value: ${logikal-redis.REDIS_URL}
    - key: DATABASE_URL
      value: ${logikal-db.DATABASE_URL}
    - key: SECRET_KEY
      type: SECRET
    - key: JWT_SECRET_KEY
      type: SECRET
```

- [ ] Add beat service configuration
- [ ] Copy necessary environment variables
- [ ] Save file

#### Step 1.4: Update Main Service

```yaml
- name: logikal-middleware
  envs:
    - key: BACKGROUND_SYNC_ENABLED
      value: "false"  # Keep disabled for web service
    - key: REDIS_URL
      value: ${logikal-redis.REDIS_URL}  # Add Redis URL
```

- [ ] Ensure BACKGROUND_SYNC_ENABLED is "false" for main service
- [ ] Add REDIS_URL reference
- [ ] Save file

### Phase 2: Commit and Deploy

- [ ] Commit changes to `.do/app.yaml`
- [ ] Push to GitHub: `git push origin main`
- [ ] DigitalOcean will detect changes and prompt for deployment
- [ ] Click "Deploy" in DigitalOcean dashboard
- [ ] Wait for deployment (may take 10-15 minutes for multiple services)

### Phase 3: Verify Multi-Container Deployment

**Location**: DigitalOcean Dashboard → Apps → logikal-middleware → Resources

#### Check Services Are Running

- [ ] ✅ logikal-middleware (web) - Status: Running
- [ ] ✅ logikal-middleware-worker - Status: Running
- [ ] ✅ logikal-middleware-beat - Status: Running
- [ ] ✅ logikal-db (PostgreSQL) - Status: Running
- [ ] ✅ logikal-redis - Status: Running

#### Check Runtime Logs Per Service

**logikal-middleware (web):**
- [ ] "Background sync is disabled, skipping Celery services"
- [ ] "Starting FastAPI application"
- [ ] No Celery-related logs (expected)

**logikal-middleware-worker:**
- [ ] "Background sync is enabled"
- [ ] "Starting Celery worker"
- [ ] "[INFO/MainProcess] Connected to redis://..."
- [ ] "celery@... ready"

**logikal-middleware-beat:**
- [ ] "Background sync is enabled"
- [ ] "Starting Celery beat"
- [ ] "Scheduler: Sending due task..."
- [ ] "smart-sync-scheduler"

### Phase 4: Continue with Phases 6-8 from Option 1

- [ ] Follow "Phase 6: Verify Deployment" from Option 1
- [ ] Follow "Phase 7: Monitor and Tune" from Option 1
- [ ] Follow "Phase 8: Configuration Tuning" from Option 1

---

## ⚠️ Rollback Plan (If Things Go Wrong)

### Quick Rollback (Disable Scheduled Sync)

**Location**: DigitalOcean Dashboard → Apps → logikal-middleware → Settings → Environment Variables

1. [ ] Find `BACKGROUND_SYNC_ENABLED`
2. [ ] Click "Edit"
3. [ ] Change value to `"false"`
4. [ ] Click "Save"
5. [ ] Redeploy application
6. [ ] Verify logs show "Background sync is disabled"

**Result**: System returns to manual sync only, no scheduled tasks run.

### Full Rollback (Remove Redis)

**Only if Redis is causing issues:**

1. [ ] Disable background sync (above)
2. [ ] Remove Redis database from Resources
3. [ ] Remove `REDIS_URL` environment variable
4. [ ] Redeploy application

**Result**: System returns to pre-scheduled-sync state.

---

## 🎯 Success Criteria

### Short Term (24 hours)

- [ ] ✅ Application deployed successfully
- [ ] ✅ No deployment errors
- [ ] ✅ Redis connection stable
- [ ] ✅ Celery worker and beat processes running
- [ ] ✅ First scheduled sync executes successfully
- [ ] ✅ Memory usage under 80%
- [ ] ✅ No critical errors in logs

### Medium Term (1 week)

- [ ] ✅ Scheduled syncs running consistently
- [ ] ✅ Data freshness improved in Odoo
- [ ] ✅ No memory leaks
- [ ] ✅ System stable and performant
- [ ] ✅ Users notice fresher data
- [ ] ✅ Reduced manual force sync usage

### Long Term (1 month)

- [ ] ✅ Sync intervals optimized per object type
- [ ] ✅ Minimal manual intervention needed
- [ ] ✅ Clear monitoring and alerting in place
- [ ] ✅ User satisfaction improved
- [ ] ✅ System architecture proven stable

---

## 📊 Monitoring Checklist

### Daily Checks (First Week)

- [ ] Check runtime logs for errors
- [ ] Verify scheduled tasks executing
- [ ] Check memory usage trends
- [ ] Review sync durations
- [ ] Verify data freshness in Odoo

### Weekly Checks (Ongoing)

- [ ] Review sync success/failure rates
- [ ] Check Redis memory usage
- [ ] Review sync intervals - optimize if needed
- [ ] Collect user feedback on data freshness
- [ ] Check system costs vs budget

### Monthly Checks

- [ ] Review overall system health
- [ ] Analyze sync patterns and trends
- [ ] Consider infrastructure optimizations
- [ ] Update documentation as needed
- [ ] Plan capacity for growth

---

## 📞 Troubleshooting Guide

### Issue: Celery Worker Not Starting

**Symptoms:**
- Logs show: "Background sync is disabled"
- No worker process in logs

**Solution:**
1. [ ] Check `BACKGROUND_SYNC_ENABLED` is set to `"true"`
2. [ ] Verify Redis is deployed and accessible
3. [ ] Check `REDIS_URL` is correctly set
4. [ ] Redeploy application

### Issue: Redis Connection Failed

**Symptoms:**
- Logs show: "Error connecting to Redis"
- Worker crashes on startup

**Solution:**
1. [ ] Check Redis status in DigitalOcean
2. [ ] Verify `REDIS_URL` environment variable
3. [ ] Check Redis is in same region as app
4. [ ] Test Redis connectivity from app

### Issue: High Memory Usage

**Symptoms:**
- Memory usage > 90%
- Application becomes slow
- Potential OOM errors

**Solution:**
1. [ ] Upgrade instance size (basic-xxs → basic-xs)
2. [ ] Increase sync intervals (reduce frequency)
3. [ ] Consider multi-container setup
4. [ ] Review Celery worker settings (max_tasks_per_child)

### Issue: Sync Tasks Not Executing

**Symptoms:**
- Celery beat running but no tasks execute
- Last sync timestamps not updating

**Solution:**
1. [ ] Check per-object sync configurations in Admin UI
2. [ ] Verify `is_sync_enabled=true` for object types
3. [ ] Check sync intervals haven't elapsed yet
4. [ ] Review logs for task failures
5. [ ] Test manual sync to isolate issue

### Issue: Conflicts with Manual Sync

**Symptoms:**
- Manual force sync fails
- "Resource locked" errors

**Solution:**
1. [ ] Increase sync intervals to reduce conflicts
2. [ ] Review database locking strategy
3. [ ] Consider queueing manual sync requests
4. [ ] Check for long-running sync tasks

---

## 📚 Additional Resources

### Documentation
- [ ] Full analysis: `SCHEDULED_SYNC_ANALYSIS.md`
- [ ] Quick summary: `SCHEDULED_SYNC_QUICK_SUMMARY.md`
- [ ] Architecture: `SCHEDULED_SYNC_ARCHITECTURE_COMPARISON.md`

### Configuration Files
- [ ] DigitalOcean config: `.do/app.yaml`
- [ ] Local reference: `docker-compose.yml`
- [ ] Environment template: `env.production.template`

### Code References
- [ ] Scheduler tasks: `app/tasks/scheduler_tasks.py`
- [ ] Celery config: `app/celery_app.py`
- [ ] Startup script: `app/startup.py`
- [ ] Sync service: `app/services/smart_sync_service.py`

---

## ✅ Final Checklist

Before considering scheduled sync "enabled":

- [ ] Redis deployed and operational
- [ ] `BACKGROUND_SYNC_ENABLED` set to `"true"`
- [ ] `REDIS_URL` correctly configured
- [ ] Celery worker process running
- [ ] Celery beat process running
- [ ] First scheduled sync executed successfully
- [ ] No critical errors in logs
- [ ] Memory usage acceptable
- [ ] Admin UI shows updated sync times
- [ ] Monitoring in place for 48 hours
- [ ] Rollback plan documented and understood
- [ ] Team notified of change
- [ ] Documentation updated

---

## 🎉 Success!

Once all checklist items are complete, your scheduled sync is fully operational!

**Expected behavior:**
- Data automatically refreshes every 5-60 minutes (configurable)
- No manual intervention required
- Users see fresh data immediately
- System runs autonomously

**Ongoing:**
- Monitor daily for first week
- Tune sync intervals based on needs
- Optimize resource usage
- Collect user feedback

**Cost**: ~$22-25/month additional for automated data freshness

**Benefit**: Always up-to-date data without user intervention!

---

**Last Updated**: October 12, 2025  
**Created By**: AI Analysis of Middleware Architecture  
**Status**: Ready for implementation

