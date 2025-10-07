# DigitalOcean App Platform Deployment - Step by Step Guide

## 🎯 **Overview**

This guide will walk you through deploying the Logikal Middleware to DigitalOcean App Platform with all Phase 1 improvements. The deployment includes automated database initialization, production-grade security, and comprehensive monitoring.

---

## 📋 **Prerequisites**

- ✅ DigitalOcean account with App Platform access
- ✅ GitHub repository: `scrollit/logikal-middleware` (already configured)
- ✅ Production secrets generated (run `python3 generate_secrets.py` first)
- ✅ Access to Logikal API credentials

---

## 🚀 **Step 2: Deploy to DigitalOcean App Platform**

### **2.1 Access DigitalOcean App Platform**

1. **Login to DigitalOcean**:
   - Go to [https://cloud.digitalocean.com](https://cloud.digitalocean.com)
   - Sign in with your account credentials

2. **Navigate to App Platform**:
   - In the left sidebar, click **"Apps"**
   - Click **"Create App"** button (blue button in top right)

### **2.2 Create New App from GitHub**

1. **Select Source**:
   - Choose **"GitHub"** as the source
   - You may need to authorize DigitalOcean to access your GitHub account if this is the first time

2. **Select Repository**:
   - In the repository list, find and select **`scrollit/logikal-middleware`**
   - Verify the repository name and organization are correct

3. **Configure Source Settings**:
   - **Branch**: Select `main` (should be selected by default)
   - **Build Method**: Select **"Dockerfile"**
   - **Dockerfile Path**: Leave as `Dockerfile` (default)
   - Click **"Next"** to proceed

### **2.3 Configure App Settings**

1. **App Name**:
   - **App Name**: `logikal-middleware`
   - **Region**: Choose the region closest to your users (e.g., Amsterdam, Frankfurt, or New York)

2. **Service Configuration**:
   - **Instance Size**: Select **"Basic XXS"** (1 vCPU, 512MB RAM, $5/month)
   - **Instance Count**: Set to `1`
   - **HTTP Port**: Set to `8000` (this matches our Dockerfile configuration)

3. **Build and Run Commands**:
   - **Run Command**: `python startup.py` (this is our production startup script)
   - **Build Command**: Leave empty (Dockerfile handles this)

4. **Click "Next"** to proceed to the next step

### **2.4 Add Managed Database**

1. **Add Database Component**:
   - Click **"Add Component"** → **"Database"**

2. **Database Configuration**:
   - **Database Engine**: Select **PostgreSQL**
   - **Version**: Select **PostgreSQL 15**
   - **Database Size**: Select **"db-s-dev-database"** (1 vCPU, 1GB RAM, $15/month)
   - **Database Name**: `logikal-db`

3. **Database Settings**:
   - The database will be automatically connected to your app
   - DigitalOcean will provide the `DATABASE_URL` environment variable automatically

4. **Click "Next"** to proceed

### **2.5 Configure Routes (Optional)**

1. **Review Default Routes**:
   - DigitalOcean will automatically detect routes from your app
   - The following routes should be available:
     - `/` - Main application
     - `/ui` - Admin interface
     - `/api` - API endpoints
     - `/docs` - API documentation
     - `/metrics` - Prometheus metrics

2. **Custom Domain (Optional)**:
   - If you have a custom domain, you can add it here
   - For now, you can skip this and add it later

3. **Click "Next"** to proceed to environment variables

---

## 🔐 **Step 3: Configure Environment Variables**

### **3.1 Generate Production Secrets (If Not Done Already)**

1. **Run Secret Generation**:
   ```bash
   cd /home/jasperhendrickx/clients/logikal-middleware-dev
   python3 generate_secrets.py
   ```

2. **Save the Generated Secrets**:
   - Copy all the generated secrets from the output
   - You'll need these for the next step

### **3.2 Set Environment Variables in DigitalOcean**

1. **Navigate to Environment Variables Section**:
   - In the App Platform setup, you should now be at the "Environment Variables" step

2. **Add SECRET Variables** (Mark these as SECRET):
   
   **Click "Add Variable" for each of these:**

   - **Variable Name**: `SECRET_KEY`
     - **Value**: `[Generated secret key from step 3.1]`
     - **Type**: Select **"SECRET"**
     - **Click "Add"**

   - **Variable Name**: `JWT_SECRET_KEY`
     - **Value**: `[Generated JWT secret from step 3.1]`
     - **Type**: Select **"SECRET"**
     - **Click "Add"**

   - **Variable Name**: `ADMIN_USERNAME`
     - **Value**: `admin`
     - **Type**: Select **"SECRET"**
     - **Click "Add"**

   - **Variable Name**: `ADMIN_PASSWORD`
     - **Value**: `[Generated admin password from step 3.1]`
     - **Type**: Select **"SECRET"**
     - **Click "Add"**

   - **Variable Name**: `LOGIKAL_AUTH_USERNAME`
     - **Value**: `Jasper`
     - **Type**: Select **"SECRET"**
     - **Click "Add"**

   - **Variable Name**: `LOGIKAL_AUTH_PASSWORD`
     - **Value**: `OdooAPI`
     - **Type**: Select **"SECRET"**
     - **Click "Add"**

### **3.3 Add Public Environment Variables**

**Click "Add Variable" for each of these (Type: "Public"):**

   - **Variable Name**: `ENVIRONMENT`
     - **Value**: `production`
     - **Type**: **"Public"**
     - **Click "Add"**

   - **Variable Name**: `DEBUG`
     - **Value**: `false`
     - **Type**: **"Public"**
     - **Click "Add"**

   - **Variable Name**: `LOGIKAL_API_BASE_URL`
     - **Value**: `http://128.199.57.77/MbioeService.svc/api/v3/`
     - **Type**: **"Public"**
     - **Click "Add"**

   - **Variable Name**: `ADMIN_SESSION_EXPIRE_HOURS`
     - **Value**: `8`
     - **Type**: **"Public"**
     - **Click "Add"**

   - **Variable Name**: `LOG_LEVEL`
     - **Value**: `INFO`
     - **Type**: **"Public"**
     - **Click "Add"**

   - **Variable Name**: `LOG_FORMAT`
     - **Value**: `json`
     - **Type**: **"Public"**
     - **Click "Add"**

   - **Variable Name**: `PROMETHEUS_ENABLED`
     - **Value**: `true`
     - **Type**: **"Public"**
     - **Click "Add"**

   - **Variable Name**: `RATE_LIMIT_PER_MINUTE`
     - **Value**: `1000`
     - **Type**: **"Public"`
     - **Click "Add"**

   - **Variable Name**: `RATE_LIMIT_PER_HOUR`
     - **Value**: `10000`
     - **Type**: **"Public"**
     - **Click "Add"**

### **3.4 Configure CORS and Security (Production)**

   - **Variable Name**: `CORS_ORIGINS`
     - **Value**: `https://your-production-domain.com,https://app.your-production-domain.com`
     - **Type**: **"Public"**
     - **Note**: Replace with your actual production domains
     - **Click "Add"**

   - **Variable Name**: `TRUSTED_HOSTS`
     - **Value**: `your-production-domain.com,*.your-production-domain.com`
     - **Type**: **"Public"**
     - **Note**: Replace with your actual production domains
     - **Click "Add"**

### **3.5 Review Environment Variables**

1. **Verify All Variables**:
   - You should have **6 SECRET variables** and **10 PUBLIC variables**
   - Double-check that all SECRET variables are marked as "SECRET"
   - Verify the values are correct

2. **Important Notes**:
   - `DATABASE_URL` and `REDIS_URL` will be automatically provided by DigitalOcean
   - Don't add these manually - they're auto-generated
   - The database connection will be established automatically

---

## 🚀 **Step 4: Deploy and Validate**

### **4.1 Deploy the Application**

1. **Review Configuration**:
   - Review all your settings in the summary screen
   - Ensure repository, database, and environment variables are correct

2. **Deploy**:
   - Click **"Create Resources"** button
   - DigitalOcean will start building and deploying your application
   - This process typically takes 5-10 minutes

3. **Monitor Deployment**:
   - Watch the build logs for any errors
   - The deployment will go through several stages:
     - Building Docker image
     - Starting the application
     - Running database migrations
     - Health checks

### **4.2 Validate Deployment**

1. **Check Deployment Status**:
   - Wait for the deployment to complete
   - Look for "Deployment successful" message
   - Note the app URL (e.g., `https://logikal-middleware-xxxxx.ondigitalocean.app`)

2. **Test Health Check**:
   ```bash
   curl https://your-app-url.ondigitalocean.app/api/v1/health
   ```
   Expected response:
   ```json
   {
     "status": "healthy",
     "version": "1.0.0"
   }
   ```

3. **Test Root Endpoint**:
   ```bash
   curl https://your-app-url.ondigitalocean.app/
   ```
   Expected response:
   ```json
   {
     "message": "Logikal Middleware is running!",
     "version": "1.0.0"
   }
   ```

4. **Test Admin UI**:
   - Navigate to: `https://your-app-url.ondigitalocean.app/ui`
   - Login with the admin credentials you set in environment variables
   - Verify the admin interface loads correctly

5. **Test API Documentation**:
   - Navigate to: `https://your-app-url.ondigitalocean.app/docs`
   - Verify the API documentation loads
   - Test some API endpoints

### **4.3 Monitor Application Logs**

1. **View Logs**:
   - In DigitalOcean App Platform dashboard
   - Go to your app → **"Runtime Logs"** tab
   - Check for any errors or warnings

2. **Look for Success Messages**:
   - "Application startup completed"
   - "Database initialization completed"
   - "Security middleware setup completed"

---

## 🔧 **Troubleshooting Common Issues**

### **Issue 1: Application Won't Start**
**Symptoms**: Deployment fails or app doesn't respond
**Solutions**:
- Check environment variables are set correctly
- Verify all SECRET variables are marked as SECRET
- Check the build logs for errors
- Ensure the startup script has execute permissions

### **Issue 2: Database Connection Failed**
**Symptoms**: Database-related errors in logs
**Solutions**:
- Verify the managed database was created successfully
- Check that DATABASE_URL is automatically provided by DigitalOcean
- Ensure database migrations are running successfully

### **Issue 3: Health Check Failing**
**Symptoms**: Health endpoint returns errors
**Solutions**:
- Check application logs for startup errors
- Verify port 8000 is accessible
- Ensure the startup script completes successfully
- Check if database initialization is hanging

### **Issue 4: Authentication Issues**
**Symptoms**: Admin login fails or API authentication errors
**Solutions**:
- Verify SECRET_KEY and JWT_SECRET_KEY are set correctly
- Check admin credentials in environment variables
- Ensure all SECRET variables are marked as SECRET type

---

## 📊 **Post-Deployment Checklist**

- [ ] ✅ Application starts successfully
- [ ] ✅ Health check endpoint responds (`/api/v1/health`)
- [ ] ✅ Admin UI accessible (`/ui`)
- [ ] ✅ API documentation loads (`/docs`)
- [ ] ✅ Database connection established
- [ ] ✅ Admin login works with generated credentials
- [ ] ✅ No critical errors in application logs
- [ ] ✅ Prometheus metrics available (`/metrics`)
- [ ] ✅ All environment variables set correctly
- [ ] ✅ CORS configured for production domain (if applicable)

---

## 🎉 **Success!**

Once all checklist items are completed, your Logikal Middleware is successfully deployed to DigitalOcean App Platform with all Phase 1 improvements:

- ✅ **Production-ready security** with rate limiting and headers
- ✅ **Automated database initialization** on startup
- ✅ **Comprehensive monitoring** and health checks
- ✅ **Environment-based configuration** management
- ✅ **Secret management** for production security

Your middleware is now ready for UAT testing and production use!

---

## 📞 **Support**

If you encounter any issues during deployment:

1. Check the troubleshooting section above
2. Review the application logs in DigitalOcean dashboard
3. Verify all environment variables are set correctly
4. Ensure the GitHub repository is accessible to DigitalOcean
5. Check the build logs for any Docker or dependency issues

**Next Steps**: Proceed with Phase 2 (Infrastructure optimization) and Phase 3 (Performance testing) as outlined in the Phase 1 completion summary.
