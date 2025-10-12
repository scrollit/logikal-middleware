# Scheduled Sync - Architecture Comparison

## 📐 Visual Architecture Comparison

---

## Current Production Architecture (DigitalOcean)

```
┌─────────────────────────────────────────────────────────────┐
│  DigitalOcean App Platform                                  │
│                                                             │
│  ┌───────────────────────────────────────────────────────┐ │
│  │  logikal-middleware (basic-xxs: 512MB RAM, 1 vCPU)   │ │
│  │                                                       │ │
│  │  ┌─────────────────────────────────────────────┐    │ │
│  │  │  FastAPI Web Server (uvicorn)              │    │ │
│  │  │  - Serves HTTP requests                     │    │ │
│  │  │  - Manual sync endpoints                    │    │ │
│  │  │  - Admin UI                                 │    │ │
│  │  │  - API documentation                        │    │ │
│  │  └─────────────────────────────────────────────┘    │ │
│  │                                                       │ │
│  │  ❌ Celery Worker (NOT STARTED)                      │ │
│  │  ❌ Celery Beat (NOT STARTED)                        │ │
│  │                                                       │ │
│  │  Environment:                                         │ │
│  │    BACKGROUND_SYNC_ENABLED=false  ❌                 │ │
│  └───────────────────────────────────────────────────────┘ │
│                                                             │
│  ┌───────────────────────────────────────────────────────┐ │
│  │  PostgreSQL Database (logikal-db)                    │ │
│  │  - Project data                                       │ │
│  │  - Sync configurations                                │ │
│  │  - Object sync intervals                              │ │
│  └───────────────────────────────────────────────────────┘ │
│                                                             │
│  ❌ Redis (NOT DEPLOYED - commented out)                   │
│                                                             │
└─────────────────────────────────────────────────────────────┘

┌─────────────────────────────────────────────────────────────┐
│  External Systems                                           │
│                                                             │
│  ┌─────────────────────┐      ┌──────────────────────────┐ │
│  │  Logikal API        │      │  Odoo (Users)           │ │
│  │  128.199.57.77      │      │  - Manual Force Sync    │ │
│  └─────────────────────┘      └──────────────────────────┘ │
└─────────────────────────────────────────────────────────────┘

RESULT: ❌ No scheduled sync. Only manual sync works.
```

---

## Local Development Architecture (Working)

```
┌─────────────────────────────────────────────────────────────┐
│  Docker Compose (Local Development)                         │
│                                                             │
│  ┌───────────────────────────────────────────────────────┐ │
│  │  logikal-middleware (web)                            │ │
│  │  ┌─────────────────────────────────────────────┐    │ │
│  │  │  FastAPI Web Server (uvicorn)              │    │ │
│  │  │  Port: 8001                                 │    │ │
│  │  └─────────────────────────────────────────────┘    │ │
│  │  Environment: BACKGROUND_SYNC_ENABLED=true  ✅       │ │
│  └───────────────────────────────────────────────────────┘ │
│                          │                                  │
│                          │ HTTP                             │
│                          ▼                                  │
│  ┌───────────────────────────────────────────────────────┐ │
│  │  logikal-celery-worker                               │ │
│  │  ┌─────────────────────────────────────────────┐    │ │
│  │  │  Celery Worker                              │    │ │
│  │  │  - Executes sync tasks                      │    │ │
│  │  │  - Queues: sync, scheduler, sqlite_parser   │    │ │
│  │  └─────────────────────────────────────────────┘    │ │
│  │  Environment: BACKGROUND_SYNC_ENABLED=true  ✅       │ │
│  └───────────────────────────────────────────────────────┘ │
│                          ▲                                  │
│                          │ Task Queue (Redis)               │
│                          │                                  │
│  ┌───────────────────────────────────────────────────────┐ │
│  │  logikal-celery-beat                                 │ │
│  │  ┌─────────────────────────────────────────────┐    │ │
│  │  │  Celery Beat Scheduler                      │    │ │
│  │  │  - Triggers tasks every 5 minutes           │    │ │
│  │  │  - Schedule: smart_sync_scheduler           │    │ │
│  │  └─────────────────────────────────────────────┘    │ │
│  │  Environment: BACKGROUND_SYNC_ENABLED=true  ✅       │ │
│  └───────────────────────────────────────────────────────┘ │
│                          │                                  │
│                          ▼                                  │
│  ┌───────────────────────────────────────────────────────┐ │
│  │  Redis (logikal-redis)                               │ │
│  │  - Task broker                                        │ │
│  │  - Result backend                                     │ │
│  │  - Beat schedule state                                │ │
│  │  Port: 6379  ✅                                       │ │
│  └───────────────────────────────────────────────────────┘ │
│                          │                                  │
│                          ▼                                  │
│  ┌───────────────────────────────────────────────────────┐ │
│  │  PostgreSQL (logikal-db)                             │ │
│  │  - Project data                                       │ │
│  │  - Sync configurations                                │ │
│  │  Port: 5432  ✅                                       │ │
│  └───────────────────────────────────────────────────────┘ │
│                                                             │
└─────────────────────────────────────────────────────────────┘

RESULT: ✅ Scheduled sync works perfectly.
         Tasks execute every 5 minutes automatically.
```

---

## Proposed Production Architecture (Option 1: Single Container)

```
┌─────────────────────────────────────────────────────────────┐
│  DigitalOcean App Platform                                  │
│                                                             │
│  ┌───────────────────────────────────────────────────────┐ │
│  │  logikal-middleware (basic-xs: 1GB RAM, 1 vCPU)      │ │
│  │  ⚠️  Upgraded from 512MB to handle Celery processes  │ │
│  │                                                       │ │
│  │  ┌─────────────────────────────────────────────┐    │ │
│  │  │  FastAPI Web Server (Process 1)            │    │ │
│  │  │  - Serves HTTP requests                     │    │ │
│  │  │  - Manual sync endpoints                    │    │ │
│  │  └─────────────────────────────────────────────┘    │ │
│  │                                                       │ │
│  │  ┌─────────────────────────────────────────────┐    │ │
│  │  │  Celery Worker (Process 2)                  │    │ │
│  │  │  - Executes sync tasks in background        │    │ │
│  │  └─────────────────────────────────────────────┘    │ │
│  │                                                       │ │
│  │  ┌─────────────────────────────────────────────┐    │ │
│  │  │  Celery Beat (Process 3)                    │    │ │
│  │  │  - Schedules tasks every 5 minutes          │    │ │
│  │  └─────────────────────────────────────────────┘    │ │
│  │                                                       │ │
│  │  Environment:                                         │ │
│  │    BACKGROUND_SYNC_ENABLED=true  ✅                  │ │
│  │    REDIS_URL=${logikal-redis.REDIS_URL}  ✅          │ │
│  └───────────────────────────────────────────────────────┘ │
│                          │                                  │
│                          │                                  │
│  ┌───────────────────────┴───────────────────────────────┐ │
│  │  Redis (logikal-redis) - NEW                         │ │
│  │  - Managed Redis instance                             │ │
│  │  - Task queue and result storage                      │ │
│  │  - Cost: ~$15/month  💰                               │ │
│  └───────────────────────────────────────────────────────┘ │
│                          │                                  │
│                          ▼                                  │
│  ┌───────────────────────────────────────────────────────┐ │
│  │  PostgreSQL Database (logikal-db)                    │ │
│  │  - Project data                                       │ │
│  │  - Sync configurations                                │ │
│  └───────────────────────────────────────────────────────┘ │
│                                                             │
└─────────────────────────────────────────────────────────────┘

PROS: ✅ Simple deployment (minimal config changes)
      ✅ Lower cost (~$22/month total extra)

CONS: ⚠️  All processes share 1GB RAM
      ⚠️  Single point of failure
      ⚠️  Less scalable

COST: $5 → $12/month (instance) + $15/month (Redis) = +$22/month
```

---

## Proposed Production Architecture (Option 2: Multi-Container) **RECOMMENDED**

```
┌─────────────────────────────────────────────────────────────┐
│  DigitalOcean App Platform                                  │
│                                                             │
│  ┌───────────────────────────────────────────────────────┐ │
│  │  logikal-middleware (web)                            │ │
│  │  (basic-xxs: 512MB RAM, 1 vCPU)                      │ │
│  │                                                       │ │
│  │  ┌─────────────────────────────────────────────┐    │ │
│  │  │  FastAPI Web Server ONLY                    │    │ │
│  │  │  - Serves HTTP requests                     │    │ │
│  │  │  - Manual sync endpoints                    │    │ │
│  │  │  - Admin UI                                 │    │ │
│  │  └─────────────────────────────────────────────┘    │ │
│  │                                                       │ │
│  │  Environment:                                         │ │
│  │    BACKGROUND_SYNC_ENABLED=false                     │ │
│  │    (Web server doesn't start Celery)                 │ │
│  └───────────────────────────────────────────────────────┘ │
│                          │                                  │
│                          │ HTTP API calls                   │
│                          ▼                                  │
│  ┌───────────────────────────────────────────────────────┐ │
│  │  logikal-middleware-worker - NEW                     │ │
│  │  (basic-xxs: 512MB RAM, 1 vCPU)                      │ │
│  │                                                       │ │
│  │  ┌─────────────────────────────────────────────┐    │ │
│  │  │  Celery Worker                              │    │ │
│  │  │  - Executes sync tasks                      │    │ │
│  │  │  - Queues: sync, scheduler, sqlite_parser   │    │ │
│  │  │  - Can scale independently                  │    │ │
│  │  └─────────────────────────────────────────────┘    │ │
│  │                                                       │ │
│  │  Environment:                                         │ │
│  │    BACKGROUND_SYNC_ENABLED=true  ✅                  │ │
│  └───────────────────────────────────────────────────────┘ │
│                          ▲                                  │
│                          │ Task Queue                       │
│                          │                                  │
│  ┌───────────────────────────────────────────────────────┐ │
│  │  logikal-middleware-beat - NEW                       │ │
│  │  (basic-xxs: 512MB RAM, 1 vCPU)                      │ │
│  │                                                       │ │
│  │  ┌─────────────────────────────────────────────┐    │ │
│  │  │  Celery Beat Scheduler                      │    │ │
│  │  │  - Triggers tasks every 5 minutes           │    │ │
│  │  │  - Schedule: smart_sync_scheduler           │    │ │
│  │  └─────────────────────────────────────────────┘    │ │
│  │                                                       │ │
│  │  Environment:                                         │ │
│  │    BACKGROUND_SYNC_ENABLED=true  ✅                  │ │
│  └───────────────────────────────────────────────────────┘ │
│                          │                                  │
│                          ▼                                  │
│  ┌───────────────────────────────────────────────────────┐ │
│  │  Redis (logikal-redis) - NEW                         │ │
│  │  - Managed Redis instance                             │ │
│  │  - Task broker and result backend                     │ │
│  │  - Cost: ~$15/month  💰                               │ │
│  └───────────────────────────────────────────────────────┘ │
│                          │                                  │
│                          ▼                                  │
│  ┌───────────────────────────────────────────────────────┐ │
│  │  PostgreSQL Database (logikal-db)                    │ │
│  │  - Project data                                       │ │
│  │  - Sync configurations                                │ │
│  └───────────────────────────────────────────────────────┘ │
│                                                             │
└─────────────────────────────────────────────────────────────┘

PROS: ✅ Clear separation of concerns
      ✅ Independent scaling (can add more workers)
      ✅ Better resource isolation
      ✅ If web crashes, workers keep running
      ✅ Production-grade architecture

CONS: ⚠️  More complex configuration
      ⚠️  More services to manage
      ⚠️  Slightly higher cost

COST: $5 (web) + $5 (worker) + $5 (beat) + $15 (Redis) = +$25/month
```

---

## Task Flow Diagram (When Scheduled Sync is Enabled)

```
┌─────────────────────────────────────────────────────────────┐
│  Celery Beat Scheduler                                      │
│                                                             │
│  Every 5 minutes:                                           │
│  ┌─────────────────────────────────────────────┐           │
│  │  Trigger: smart_sync_scheduler task          │           │
│  └──────────────┬──────────────────────────────┘           │
│                 │                                           │
│                 ▼                                           │
│  ┌─────────────────────────────────────────────┐           │
│  │  Enqueue task to Redis                      │           │
│  │  Queue: "scheduler"                         │           │
│  └──────────────┬──────────────────────────────┘           │
└────────────────┼────────────────────────────────────────────┘
                 │
                 │ Task queued in Redis
                 │
                 ▼
┌─────────────────────────────────────────────────────────────┐
│  Celery Worker                                              │
│                                                             │
│  ┌─────────────────────────────────────────────┐           │
│  │  1. Receive task from Redis queue           │           │
│  └──────────────┬──────────────────────────────┘           │
│                 │                                           │
│                 ▼                                           │
│  ┌─────────────────────────────────────────────┐           │
│  │  2. Check: BACKGROUND_SYNC_ENABLED?         │           │
│  │     - If false: Exit (current behavior)      │           │
│  │     - If true: Continue                      │           │
│  └──────────────┬──────────────────────────────┘           │
│                 │                                           │
│                 ▼                                           │
│  ┌─────────────────────────────────────────────┐           │
│  │  3. Query ObjectSyncConfig table            │           │
│  │     - Get all enabled sync configurations   │           │
│  │     - Filter by: is_sync_enabled=true       │           │
│  └──────────────┬──────────────────────────────┘           │
│                 │                                           │
│                 ▼                                           │
│  ┌─────────────────────────────────────────────┐           │
│  │  4. For each object type:                   │           │
│  │     a. Check last_sync timestamp            │           │
│  │     b. Compare with sync_interval_minutes   │           │
│  │     c. If interval elapsed: needs sync      │           │
│  │     d. If not: skip                         │           │
│  └──────────────┬──────────────────────────────┘           │
│                 │                                           │
│                 ▼                                           │
│  ┌─────────────────────────────────────────────┐           │
│  │  5. For each object needing sync:           │           │
│  │     - Call SmartSyncService                 │           │
│  │     - Sync based on dependencies            │           │
│  │       (directories → projects → phases      │           │
│  │        → elevations)                        │           │
│  └──────────────┬──────────────────────────────┘           │
│                 │                                           │
│                 ▼                                           │
│  ┌─────────────────────────────────────────────┐           │
│  │  6. Call Logikal API                        │           │
│  │     - Fetch updated data                    │           │
│  │     - Store in PostgreSQL                   │           │
│  │     - Update last_sync timestamp            │           │
│  └──────────────┬──────────────────────────────┘           │
│                 │                                           │
│                 ▼                                           │
│  ┌─────────────────────────────────────────────┐           │
│  │  7. Return task result to Redis             │           │
│  │     - Success/failure status                │           │
│  │     - Objects synced count                  │           │
│  │     - Duration                              │           │
│  └──────────────┬──────────────────────────────┘           │
└────────────────┼────────────────────────────────────────────┘
                 │
                 ▼
┌─────────────────────────────────────────────────────────────┐
│  Admin UI / Monitoring                                      │
│                                                             │
│  ┌─────────────────────────────────────────────┐           │
│  │  View at /ui/sync-intervals:                │           │
│  │  - Last sync timestamps updated             │           │
│  │  - Sync status displayed                    │           │
│  │  - Next sync time calculated                │           │
│  └─────────────────────────────────────────────┘           │
└─────────────────────────────────────────────────────────────┘

RESULT: Data automatically stays fresh without user intervention.
```

---

## Configuration Hierarchy

```
┌──────────────────────────────────────────────────────────┐
│  Global Configuration                                    │
│  (Environment Variables)                                 │
│                                                          │
│  BACKGROUND_SYNC_ENABLED: true/false  ← MASTER SWITCH   │
│  SYNC_INTERVAL_SECONDS: 300                             │
│                                                          │
│  If BACKGROUND_SYNC_ENABLED=false:                      │
│    → ALL scheduled sync disabled                        │
│    → Celery processes may not even start               │
│                                                          │
│  If BACKGROUND_SYNC_ENABLED=true:                       │
│    → Celery processes start                             │
│    → Check per-object configuration ↓                   │
└──────────────────────────────────────────────────────────┘
                        │
                        ▼
┌──────────────────────────────────────────────────────────┐
│  Per-Object Configuration                                │
│  (Database: ObjectSyncConfig table)                      │
│                                                          │
│  ┌────────────────────────────────────────────────────┐ │
│  │  Directories                                       │ │
│  │  - is_sync_enabled: true/false  ← Per-object toggle│ │
│  │  - sync_interval_minutes: 60                       │ │
│  │  - staleness_threshold_minutes: 120                │ │
│  │  - priority: 1 (highest)                           │ │
│  └────────────────────────────────────────────────────┘ │
│                                                          │
│  ┌────────────────────────────────────────────────────┐ │
│  │  Projects                                          │ │
│  │  - is_sync_enabled: true/false                     │ │
│  │  - sync_interval_minutes: 30                       │ │
│  │  - depends_on: "directory"  ← Dependency aware     │ │
│  │  - cascade_sync: true                              │ │
│  └────────────────────────────────────────────────────┘ │
│                                                          │
│  ┌────────────────────────────────────────────────────┐ │
│  │  Phases                                            │ │
│  │  - is_sync_enabled: true/false                     │ │
│  │  - sync_interval_minutes: 15                       │ │
│  │  - depends_on: "project"                           │ │
│  └────────────────────────────────────────────────────┘ │
│                                                          │
│  ┌────────────────────────────────────────────────────┐ │
│  │  Elevations                                        │ │
│  │  - is_sync_enabled: true/false                     │ │
│  │  - sync_interval_minutes: 15                       │ │
│  │  - depends_on: "phase"                             │ │
│  └────────────────────────────────────────────────────┘ │
│                                                          │
│  Configurable via Admin UI at /ui/sync-intervals        │
└──────────────────────────────────────────────────────────┘

FLEXIBILITY: 
- Can disable all sync with one environment variable
- Can disable specific object types via admin UI
- Can adjust intervals without code changes
- Can enable/disable cascade syncing
```

---

## Decision Matrix

### When to Use Each Option

| Scenario | Recommended Architecture | Reason |
|----------|-------------------------|---------|
| **Testing/Validation** | Option 1 (Single Container) | Simplest to deploy, lowest cost |
| **Low-volume production** | Option 1 (Single Container) | Sufficient resources, easier management |
| **High-volume production** | Option 2 (Multi-Container) | Better scaling, isolation |
| **Mission-critical uptime** | Option 2 (Multi-Container) | Fault tolerance, independent scaling |
| **Budget constrained** | Stay manual (current) | No additional infrastructure cost |
| **Development/Staging** | Use docker-compose | Full control, easy debugging |

---

## Resource Comparison

### Current (Manual Sync Only)

```
Monthly Cost: $20
  - Web server (basic-xxs): $5
  - PostgreSQL: $15

Resources:
  - RAM: 512MB (web) + 1GB (db) = 1.5GB
  - CPU: 1 vCPU (web) + 1 vCPU (db) = 2 vCPUs
  - Processes: 1 (uvicorn web server)

Limitations:
  - No automatic sync
  - Manual intervention required
  - Data can become stale
```

### Option 1: Single Container with Scheduled Sync

```
Monthly Cost: $42 (+$22)
  - Web server (basic-xs): $12
  - PostgreSQL: $15
  - Redis: $15

Resources:
  - RAM: 1GB (web) + 1GB (db) + 256MB (redis) = 2.25GB
  - CPU: 1 vCPU (web) + 1 vCPU (db) = 2 vCPUs
  - Processes: 3 (uvicorn + celery worker + celery beat)

Benefits:
  - Automatic sync every 5-60 minutes
  - Data stays fresh
  - Configurable per object type
```

### Option 2: Multi-Container with Scheduled Sync

```
Monthly Cost: $50 (+$30)
  - Web server (basic-xxs): $5
  - Worker (basic-xxs): $5
  - Beat (basic-xxs): $5
  - PostgreSQL: $15
  - Redis: $15

Resources:
  - RAM: 512MB (web) + 512MB (worker) + 512MB (beat) 
         + 1GB (db) + 256MB (redis) = 2.75GB
  - CPU: 3 vCPUs (web + worker + beat) + 1 vCPU (db) = 4 vCPUs
  - Processes: 3 (separate containers)

Benefits:
  - Same as Option 1, plus:
  - Independent scaling
  - Better fault tolerance
  - Cleaner architecture
  - Production-grade
```

---

## Key Architectural Insights

### 1. Why Redis is Non-Negotiable

```
Celery WITHOUT Redis:
  ❌ Cannot queue tasks
  ❌ Cannot store results
  ❌ Cannot maintain beat schedule state
  ❌ Workers have nothing to process
  ❌ Complete system failure

Celery WITH Redis:
  ✅ Task queue operational
  ✅ Results stored and retrievable
  ✅ Beat schedule persists across restarts
  ✅ Workers process tasks reliably
  ✅ System fully functional
```

### 2. Why BACKGROUND_SYNC_ENABLED is the Master Switch

```python
# This check is in EVERY scheduled task
if not _is_background_sync_enabled():
    return {"skipped": True, "reason": "Background sync is disabled"}

# Even if you have:
# - Redis running ✅
# - Celery worker running ✅
# - Celery beat running ✅
# - Per-object config enabled ✅
#
# If BACKGROUND_SYNC_ENABLED=false:
#   → All tasks exit immediately
#   → No sync happens
#   → System appears "broken" but is intentionally disabled
```

### 3. Why startup.py Checks the Flag

```python
# In startup.py:
if background_sync_enabled:
    # Start Celery processes
else:
    logger.info("Background sync is disabled, skipping Celery services")
    # Don't even start Celery → saves resources

# This means:
# - If flag is false, Celery never starts
# - No wasted resources on unused processes
# - Clean separation of concerns
# - One flag controls everything
```

---

## Timeline Estimate

### Option 1: Single Container

**Week 1: Infrastructure**
- Day 1: Deploy Redis to DigitalOcean (1 hour)
- Day 2: Update environment variables (1 hour)
- Day 3: Test connectivity (2 hours)
- Day 4-5: Monitor for issues (ongoing)

**Week 2: Enable and Test**
- Day 1: Set BACKGROUND_SYNC_ENABLED=true (5 minutes)
- Day 2-7: Monitor logs, tune intervals, verify functionality

**Total**: 2 weeks, ~5-10 hours of work

### Option 2: Multi-Container

**Week 1: Infrastructure**
- Day 1-2: Update .do/app.yaml with new services (4 hours)
- Day 3: Deploy Redis (1 hour)
- Day 4-5: Deploy and test all services (4 hours)

**Week 2: Integration**
- Day 1-3: Verify inter-service communication (4 hours)
- Day 4-7: Monitor, tune, optimize

**Total**: 2 weeks, ~15-20 hours of work

---

## Summary

| Aspect | Current | Option 1 | Option 2 |
|--------|---------|----------|----------|
| **Deployment** | ✅ Live | ❌ Not deployed | ❌ Not deployed |
| **Redis** | ❌ None | ✅ Managed Redis | ✅ Managed Redis |
| **Sync** | Manual only | Automatic | Automatic |
| **Cost** | $20/month | $42/month | $50/month |
| **Complexity** | Simple | Medium | Higher |
| **Scalability** | Limited | Limited | High |
| **Fault Tolerance** | Low | Low | High |
| **Resource Isolation** | N/A | Low | High |
| **Time to Deploy** | - | 2 weeks | 2-3 weeks |
| **Recommended For** | Current state | Testing/low-volume | Production |

---

**Next**: See `SCHEDULED_SYNC_ANALYSIS.md` for detailed implementation guide.

