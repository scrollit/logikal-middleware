# Logikal Middleware

A comprehensive middleware solution that provides seamless integration between Logikal API and Odoo ERP, with advanced sync capabilities and admin management interface.

## 🚀 Quick Start

### Prerequisites
- Docker and Docker Compose
- Access to Logikal API credentials

### Installation

1. **Clone the repository**
   ```bash
   git clone <repository-url>
   cd logikal-middleware-dev
   ```

2. **Configure environment variables**
   Update `docker-compose.yml` with your Logikal API credentials:
   ```yaml
   environment:
     - LOGIKAL_API_BASE_URL=http://your-logikal-api-url
     - LOGIKAL_AUTH_USERNAME=your_username
     - LOGIKAL_AUTH_PASSWORD=your_password
   ```

3. **Start the application**
   ```bash
   docker-compose up -d
   ```

4. **Access the admin interface**
   Open your browser and navigate to: `http://localhost:8001/ui`

## 📚 Documentation

### Core Documentation
- **[API Architecture Documentation](API_Architecture_Documentation.md)** - Complete API reference and architecture overview
- **[API Quick Reference Guide](API_Quick_Reference.md)** - Quick start guide for developers
- **[UI Development Analysis](UI_Development_Analysis.md)** - UI development roadmap and analysis

### Additional Resources
- **Postman Collections**: Available in project root for API testing
- **Docker Configuration**: `docker-compose.yml` for environment setup

## 🏗️ Architecture Overview

The Logikal Middleware serves three distinct client types:

```
┌─────────────────────────────────────────────────────────────────┐
│                    LOGIKAL MIDDLEWARE                          │
│                                                                 │
│  ┌─────────────┐  ┌─────────────┐  ┌─────────────┐             │
│  │   Admin     │  │   Odoo      │  │   Sync      │             │
│  │   APIs      │  │   APIs      │  │   Engine    │             │
│  │             │  │             │  │             │             │
│  │ • Cached    │  │ • Projects  │  │ • Directories│            │
│  │   Data      │  │ • Phases    │  │ • Projects  │            │
│  │ • Sync      │  │ • Elevations│  │ • Phases    │            │
│  │   Control   │  │ • Search    │  │ • Elevations│            │
│  │ • Monitoring│  │ • Stats     │  │ • Smart     │            │
│  └─────────────┘  └─────────────┘  │   Logic     │            │
│                                    └─────────────┘             │
└─────────────────────────────────────────────────────────────────┘
```

### Key Components

- **Admin UI**: Management dashboard for sync operations and monitoring
- **Odoo Integration**: RESTful APIs optimized for ERP integration
- **Sync Engine**: Intelligent synchronization with Logikal API
- **Database**: PostgreSQL for caching and data persistence

## 🔧 Features

### ✅ Implemented Features

#### Phase 1: Dashboard & Basic Sync
- [x] Admin dashboard with real-time metrics
- [x] Directory, Project, Phase, and Elevation management
- [x] Basic sync operations
- [x] Cached data display

#### Phase 2: Advanced Sync Management
- [x] Smart sync logic with staleness detection
- [x] Cascading sync operations
- [x] Selective sync capabilities
- [x] Sync dependency management

#### Phase 6: Production Features
- [x] Advanced monitoring and observability
- [x] Error handling and recovery
- [x] Performance optimization
- [x] Data consistency validation

### 🚧 Future Development

#### Phase 3: Data Consistency Monitoring
- [ ] Real-time data quality monitoring
- [ ] Integrity validation and reporting
- [ ] Automated data repair mechanisms

#### Phase 4: Analytics & Metrics Visualization
- [ ] Advanced analytics dashboard
- [ ] Performance trend analysis
- [ ] Data quality metrics visualization

#### Phase 5: Alert Management System
- [ ] Intelligent alerting system
- [ ] Notification management
- [ ] Escalation procedures

## 🛠️ Development

### Local Development Setup

1. **Start development environment**
   ```bash
   docker-compose up -d
   ```

2. **View logs**
   ```bash
   docker-compose logs web -f
   ```

3. **Test API endpoints**
   ```bash
   curl http://localhost:8001/api/v1/directories/cached
   ```

### Project Structure

```
logikal-middleware-dev/
├── app/
│   ├── main.py                 # FastAPI application
│   ├── routers/               # API route definitions
│   ├── models/                # Database models
│   ├── schemas/               # Pydantic schemas
│   ├── services/              # Business logic
│   └── core/                  # Core configuration
├── docker-compose.yml         # Docker configuration
├── requirements.txt           # Python dependencies
└── docs/                     # Documentation files
```

### API Testing

Use the provided Postman collections for comprehensive API testing:
- Import the collection files from the project root
- Configure environment variables
- Run test suites for different API endpoints

## 🔐 Security

### Authentication
- **Admin UI**: Internal interface, no authentication required
- **Odoo Integration**: JWT-based client authentication
- **Logikal API**: Username/password authentication

### Data Protection
- All data encrypted in transit (HTTPS)
- Secure credential management
- Rate limiting and access controls

## 📊 Monitoring

### Health Monitoring
- Real-time system health checks
- Performance metrics collection
- Error tracking and alerting

### Available Endpoints
- **Health Check**: `GET /health`
- **Metrics**: `GET /metrics` (Prometheus format)
- **Celery Monitoring**: `http://localhost:5555` (Flower)

## 🚀 Deployment

### Production Deployment
1. Update environment variables for production
2. Configure SSL certificates
3. Set up monitoring and alerting
4. Configure backup procedures

### Environment Variables
See `docker-compose.yml` for complete configuration options.

## 🤝 Contributing

1. Fork the repository
2. Create a feature branch
3. Make your changes
4. Add tests if applicable
5. Submit a pull request

## 📄 License

[Add your license information here]

## 🆘 Support

For support and questions:
- Check the documentation files
- Review the troubleshooting section in the Quick Reference Guide
- Create an issue in the repository

---

*Last Updated: September 28, 2025*
*Version: 1.0.0*
