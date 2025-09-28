**Functional Architecture: Middleware-Based Integration Between Odoo and Logikal**

---

## Overview

This document describes the architecture and functional scope for integrating Odoo 18 with Logikal via a **middleware layer** instead of direct API calls. The middleware acts as a **proxy and synchronizer**, allowing Odoo to retrieve preprocessed, simplified data instead of interacting with Logikal's complex API structure.

This architecture is especially beneficial when multiple customer environments must connect to Logikal, or when performance, caching, or data consistency concerns arise.

---

## Benefits of Middleware Layer

- ✅ Decouples Odoo from Logikal's API complexity
- ✅ Enables **preprocessing** of complex data (e.g., base64-encoded SQLite parts list)
- ✅ Facilitates **central monitoring** and error handling
- ✅ Improves performance by **caching elevations, thumbnails, and parts lists**
- ✅ Enables future expansion for Manufacturing and Inventory sync

---

## High-Level Architecture

```plaintext
  +-------------+         HTTPS         +------------------+         HTTPS         +-----------+
  |   Odoo 18   |  <----------------->  |   Middleware     |  <----------------->  |  Logikal  |
  |             |  REST API (JSON)     |   (FastAPI app)  |  Logikal Web API     |           |
  +-------------+                      +------------------+                       +-----------+
```

---

## Component Stack (Local Development)

- **Middleware**: FastAPI app (Python 3.11+)
- **Data Cache/Session Store**: Redis (in-memory)
- **Persistent Storage**: **PostgreSQL** (preferred) or SQLite for extracted data
- **Odoo**: Running locally or on Odoo.sh

### PostgreSQL Justification

PostgreSQL is the recommended database for the middleware due to:

- ✅ Alignment with Odoo (native PostgreSQL)
- ✅ Excellent relational capabilities (projects → phases → elevations → parts)
- ✅ Support for complex data (JSON, UUIDs, full-text search)
- ✅ Robust performance and scalability for large Logikal datasets
- ✅ Easy integration with Docker, async frameworks, and ORMs (SQLAlchemy)

#### Deployment (Docker Example)
```yaml
services:
  postgres:
    image: postgres:15
    ports:
      - "5432:5432"
    environment:
      POSTGRES_DB: logikal_middleware
      POSTGRES_USER: admin
      POSTGRES_PASSWORD: admin
    volumes:
      - ./pgdata:/var/lib/postgresql/data
```

Then connect with:
```python
DATABASE_URL = "postgresql://admin:admin@localhost:5432/logikal_middleware"
```

---

## Middleware Responsibilities

### 1. Authentication
- Exposes `POST /login` endpoint for Odoo.
- Internally maps to Logikal `/auth` call.
- Stores token and session info in Redis (with expiration).

### 2. Directory, Project, and Phase Cache
- Calls `/directories`, `/projects/select`, `/phases` at regular intervals (or lazily on Odoo request).
- Stores human-friendly values for dropdowns.

### 3. Elevation & Thumbnail Proxy
- Periodically pulls elevation data from Logikal.
- Stores metadata (name, shape, dimensions, etc) in PostgreSQL.
- Downloads thumbnails as image files and exposes them as static URLs (e.g., `/thumbnails/<elevation_id>.jpg`).

### 4. Parts List Handling (NEW)
- Calls the **base64 parts list endpoint** per position from Logikal.
- Decodes and saves as `.sqlite` files.
- Parses the SQLite content and extracts structured data:
  - Article number, type (glass/frame), description, dimensions, price, etc.
- Stores parsed parts in **PostgreSQL**.
- Middleware exposes simplified endpoints like:

```http
GET /projects/<project_id>/phases/<phase_id>/positions/<position_id>/parts
```
Returns:
```json
[
  {
    "code": "1234G",
    "type": "glass",
    "description": "6mm Clear Laminated",
    "length": 1600,
    "width": 900,
    "price": 47.50
  },
  ...
]
```

This allows Odoo to consume parts information without decoding base64 or working with binary databases.

---

## Odoo-Side Integration

Odoo communicates exclusively with the middleware:

### Wizard Flow (from Odoo Sales Order)
1. **GET /directories** → Populate directory dropdown.
2. **POST /projects/select** → Select project by identifier.
3. **GET /phases** → Phase selection dropdown.
4. **GET /elevations** → Retrieve elevation metadata.
5. **GET /thumbnails/<id>** → Assign to product image.
6. **GET /parts** (optional, NEW) → Display or compute BoM lines.

---

## Performance Improvements

- Cached authentication avoids re-authenticating on every request.
- Background jobs can preload and preprocess Logikal data.
- Middleware can throttle/queue expensive thumbnail or parts list calls.

---

## Next Steps (Technical)
- Define SQLAlchemy data models for PostgreSQL (projects, elevations, parts)
- Create SQLite-to-Postgres parser for parts list
- Add Alembic for migrations
- Define cron job strategy for polling Logikal updates
- Add job queue (e.g., Celery) for heavy async tasks (thumbnails, parts)
- Expose middleware via secure HTTPS reverse proxy for production

---

## Summary

The middleware-based approach introduces scalability, extensibility, and developer ergonomics for handling Logikal's deep technical complexity. It’s particularly powerful for exposing complex binary data (like SQLite parts lists) in a clean and readable JSON API that Odoo can safely and efficiently consume.

Using PostgreSQL as the central database ensures long-term compatibility with Odoo, performance under large-scale use, and simplicity of developer tooling.

