# Scheduled Sync - Quick Summary

## ❌ Current Status: NOT ACTIVE

The scheduled sync mechanism is **fully implemented but deliberately disabled** in production.

---

## 🔴 Two Primary Reasons

### 1. Explicitly Disabled via Configuration

**File**: `.do/app.yaml` (Line 47-48)
```yaml
- key: BACKGROUND_SYNC_ENABLED
  value: "false"  # ❌ DISABLED
```

**Impact**: Even if infrastructure exists, all scheduled tasks exit immediately without doing work.

### 2. Missing Redis Infrastructure

**Current Production Setup:**
- ✅ PostgreSQL Database
- ❌ Redis (required for Celery)

**Redis Status**: Commented out in deployment config

```yaml
# Optional: Redis for Celery (if needed)
# databases:
# - name: logikal-redis  # ❌ NOT DEPLOYED
```

**Why Critical**: Celery requires Redis as a message broker and result backend. Without it, scheduled tasks cannot function.

---

## 🏗️ What's Already Built

### Sophisticated Scheduled Sync System

✅ **Celery Beat Scheduler**: Runs every 5 minutes  
✅ **Smart Sync Service**: Incremental, dependency-aware syncing  
✅ **Per-Object Configuration**: Individual sync intervals for directories, projects, phases, elevations  
✅ **Admin UI**: Full configuration interface at `/ui/sync-intervals`  
✅ **Staleness Detection**: Automatically identifies outdated data  
✅ **Task Queues**: Separate queues for sync, scheduler, and parser tasks  
✅ **Monitoring**: Comprehensive logging and metrics  

**Status**: Fully coded, tested in local development, waiting for production infrastructure.

---

## 🚀 Quick Enable Checklist

### Minimum Requirements

1. **Deploy Redis to DigitalOcean**
   - Managed Redis instance
   - Cost: ~$15/month
   - Size: `db-s-dev-database`

2. **Update Environment Variable**
   ```yaml
   BACKGROUND_SYNC_ENABLED: "true"  # Change from "false"
   ```

3. **Configure Redis URL**
   ```yaml
   REDIS_URL: ${logikal-redis.REDIS_URL}
   ```

4. **Consider Instance Upgrade**
   - Current: basic-xxs (512MB RAM, 1 vCPU) - $5/month
   - Recommended: basic-xs (1GB RAM, 1 vCPU) - $12/month
   - Reason: Running Celery + Web server needs more RAM

**Total Additional Cost**: ~$22/month

---

## ⚙️ How It Would Work

### Current Flow (Manual)
```
User → Clicks Force Sync → Waits 30-60s → Data Updated
```

**Problems**:
- Must manually sync every project
- Data becomes stale between syncs
- User must remember to sync

### With Scheduled Sync Enabled
```
Background: Every 5 minutes → Check what needs sync → Auto-update
User: Sees fresh data immediately, no action needed
```

**Benefits**:
- Always up-to-date data
- No user intervention required
- Predictable, distributed load
- Better monitoring

---

## 📊 Default Sync Intervals (Configurable)

| Object Type | Interval  | Staleness | Priority |
|------------|-----------|-----------|----------|
| Directories | 60 min   | 120 min   | Highest  |
| Projects   | 30 min   | 60 min    | High     |
| Phases     | 15 min   | 30 min    | Medium   |
| Elevations | 15 min   | 30 min    | Medium   |

**Note**: These can be adjusted per object type via Admin UI.

---

## ⚠️ Why Currently Disabled

Likely reasons:

1. **Infrastructure Not Ready**
   - Redis not deployed yet
   - Single instance model → resource constraints

2. **Cautious Rollout**
   - Core functionality prioritized first
   - Manual sync provides better debugging visibility
   - Background sync adds complexity

3. **Active Development**
   - Parts list sync not yet integrated
   - Session management being refined
   - Want stable sync before automating

4. **Resource Constraints**
   - Current instance: 512MB RAM, 1 vCPU
   - Running Web + Worker + Beat on 512MB is tight

---

## 🎯 Recommended Path Forward

### Phase 1: Infrastructure (Week 1)
- Deploy managed Redis
- Test Celery connectivity
- Validate no regression

### Phase 2: Testing (Week 2)
- Enable in development
- Monitor resource usage
- Test with long intervals (4 hours)

### Phase 3: Production (Week 3)
- Enable with conservative intervals
- Monitor for 48 hours
- Gradually reduce intervals if stable

### Phase 4: Optimization (Ongoing)
- Collect metrics
- Tune intervals per object type
- Consider multi-container if needed

---

## 📁 Key Files

**Configuration:**
- `.do/app.yaml` - Production deployment config (has the BACKGROUND_SYNC_ENABLED flag)
- `docker-compose.yml` - Local dev config (working reference)

**Code:**
- `app/tasks/scheduler_tasks.py` - Scheduled task implementations
- `app/celery_app.py` - Celery configuration and beat schedule
- `app/services/smart_sync_service.py` - Sync logic
- `app/startup.py` - Startup script (checks BACKGROUND_SYNC_ENABLED)

**Models:**
- `app/models/object_sync_config.py` - Sync configuration table

---

## 🔍 How to Verify Status

### In Production (Currently)

**Check logs for:**
```
"Background sync is disabled, skipping Celery services"
```

**This confirms:**
- Background sync is disabled
- Celery worker not started
- Celery beat not started

### After Enabling

**Look for:**
```
"Starting Celery worker process (PID: xxxxx)"
"Starting Celery beat process (PID: xxxxx)"
"Starting smart sync scheduler task"
"Background sync is enabled"
```

**Check Admin UI:**
- Navigate to `/ui/sync-intervals`
- Watch `last_sync` timestamps update automatically every 5-60 minutes

---

## 📈 Expected Results After Enabling

### Positive Outcomes
- ✅ Data auto-refreshes every 30-60 minutes
- ✅ No manual sync needed (except for immediate updates)
- ✅ Better data freshness
- ✅ More predictable system load

### Potential Issues (Monitor For)
- ⚠️ Higher memory usage (Celery processes)
- ⚠️ Redis connection issues
- ⚠️ Sync conflicts with manual force sync
- ⚠️ Higher monthly costs (~$22)

---

## 💡 Quick Decision Guide

### Should you enable scheduled sync?

**Enable if:**
- Users complain about stale data
- Manual syncing is burden on users
- Want better user experience
- Can afford ~$22/month extra cost
- Have time to monitor initially

**Wait if:**
- Current manual sync is working well
- Budget is tight
- Need to fix other issues first (parts list, session management)
- Don't have monitoring capacity

**Middle ground:**
- Deploy Redis but keep sync disabled
- Test in development thoroughly
- Enable with very long intervals (4+ hours) initially
- Gradually reduce as confidence grows

---

## 📞 Next Steps

**To enable:**
1. Read full analysis: `SCHEDULED_SYNC_ANALYSIS.md`
2. Deploy Redis to DigitalOcean
3. Update `BACKGROUND_SYNC_ENABLED` to `"true"`
4. Monitor logs and Admin UI
5. Tune intervals based on needs

**Questions?**
- See detailed analysis for architecture deep-dive
- Check `docker-compose.yml` for working local reference
- Review Celery logs for troubleshooting

---

**Last Updated**: October 12, 2025  
**Status**: Infrastructure ready, awaiting production deployment decision

