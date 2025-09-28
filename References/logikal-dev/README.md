# Logikal Development Environment

This is a development environment for experimenting with the Logikal API, duplicated from the allivan-dev container.

## Quick Start

1. **Start the environment:**
   ```bash
   ./start.sh
   ```

2. **Access Odoo:**
   - Web Interface: http://localhost:8071
   - Default credentials: admin/admin

## Container Details

- **Odoo Container:** `odoo-logikal-dev`
- **Database Container:** `odoo-logikal-db`
- **Port:** 8071 (different from allivan-dev which uses 8070)
- **Database:** PostgreSQL 15

## Key Differences from allivan-dev

- **Port:** Uses 8071 instead of 8070
- **Container Names:** Prefixed with `logikal-` instead of `allivan-`
- **Volume Names:** Uses `logikal-` prefix for data persistence
- **Purpose:** Dedicated for Logikal API experimentation

## Useful Commands

```bash
# Start containers
docker-compose up -d

# View logs
docker-compose logs -f

# Stop containers
docker-compose down

# Restart containers
docker-compose restart

# Access Odoo shell
docker exec -it odoo-logikal-dev bash

# Access database
docker exec -it odoo-logikal-db psql -U odoo -d postgres
```

## Directory Structure

```
logikal-dev/
├── addons/              # Custom Odoo addons
├── oca_addons/          # OCA community addons
├── config/              # Odoo configuration
├── data/                # Data directory
├── logs/                # Log files
├── docker-compose.yml   # Docker Compose configuration
├── odoo.conf           # Odoo configuration file
├── start.sh            # Startup script
└── README.md           # This file
```

## Development Workflow

1. Make changes to addons in the `addons/` directory
2. Restart the Odoo container to apply changes:
   ```bash
   docker-compose restart odoo
   ```
3. Update modules in Odoo's Apps menu if needed

## Notes

- This environment is completely separate from allivan-dev
- Each environment has its own database and data volumes
- Changes in one environment do not affect the other
- Both environments can run simultaneously on different ports
