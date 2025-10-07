#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
Secret generation script for production deployment
Generates cryptographically secure secrets for DigitalOcean App Platform
"""

import secrets
import string
import sys
import os
from pathlib import Path


def generate_secret_key(length=64):
    """
    Generate a cryptographically secure secret key
    """
    alphabet = string.ascii_letters + string.digits + "!@#$%^&*"
    return ''.join(secrets.choice(alphabet) for _ in range(length))


def generate_jwt_secret(length=64):
    """
    Generate a cryptographically secure JWT secret
    """
    return secrets.token_urlsafe(length)


def generate_admin_password(length=16):
    """
    Generate a secure admin password
    """
    # Ensure password has uppercase, lowercase, digits, and special chars
    uppercase = string.ascii_uppercase
    lowercase = string.ascii_lowercase
    digits = string.digits
    special = "!@#$%^&*"
    
    password = [
        secrets.choice(uppercase),
        secrets.choice(lowercase),
        secrets.choice(digits),
        secrets.choice(special)
    ]
    
    # Fill the rest with random characters
    all_chars = uppercase + lowercase + digits + special
    for _ in range(length - 4):
        password.append(secrets.choice(all_chars))
    
    # Shuffle the password
    secrets.SystemRandom().shuffle(password)
    return ''.join(password)


def generate_client_secret(length=32):
    """
    Generate a secure client secret
    """
    return secrets.token_urlsafe(length)


def main():
    """
    Generate all required secrets for production deployment
    """
    print("🔐 Generating Production Secrets for DigitalOcean App Platform")
    print("=" * 60)
    
    # Generate secrets
    secret_key = generate_secret_key()
    jwt_secret = generate_jwt_secret()
    admin_password = generate_admin_password()
    client_secret = generate_client_secret()
    
    print("\n📋 REQUIRED SECRETS FOR DIGITALOCEAN APP PLATFORM:")
    print("-" * 50)
    
    print(f"\n🔑 SECRET_KEY:")
    print(f"   {secret_key}")
    
    print(f"\n🔑 JWT_SECRET_KEY:")
    print(f"   {jwt_secret}")
    
    print(f"\n👤 ADMIN_USERNAME:")
    print(f"   admin")
    
    print(f"\n🔑 ADMIN_PASSWORD:")
    print(f"   {admin_password}")
    
    print(f"\n🔑 LOGIKAL_AUTH_USERNAME:")
    print(f"   Jasper")
    
    print(f"\n🔑 LOGIKAL_AUTH_PASSWORD:")
    print(f"   OdooAPI")
    
    print(f"\n🔑 CLIENT_SECRET (for Odoo integration):")
    print(f"   {client_secret}")
    
    print("\n" + "=" * 60)
    print("📝 DEPLOYMENT INSTRUCTIONS:")
    print("-" * 30)
    
    print("\n1. Go to DigitalOcean App Platform Dashboard")
    print("2. Select your 'logikal-middleware' app")
    print("3. Go to Settings > App-Level Environment Variables")
    print("4. Add the following variables as SECRETS:")
    
    secrets_to_add = [
        ("SECRET_KEY", secret_key),
        ("JWT_SECRET_KEY", jwt_secret),
        ("ADMIN_USERNAME", "admin"),
        ("ADMIN_PASSWORD", admin_password),
        ("LOGIKAL_AUTH_USERNAME", "Jasper"),
        ("LOGIKAL_AUTH_PASSWORD", "OdooAPI"),
    ]
    
    for var_name, var_value in secrets_to_add:
        print(f"   - {var_name}: {var_value}")
    
    print("\n5. The DATABASE_URL and REDIS_URL will be automatically provided by DigitalOcean")
    print("6. Deploy your application")
    
    print("\n" + "=" * 60)
    print("🔒 SECURITY NOTES:")
    print("-" * 20)
    print("• Store these secrets securely")
    print("• Never commit secrets to version control")
    print("• Rotate secrets regularly in production")
    print("• Use different secrets for different environments")
    
    # Save to file for reference (with warning)
    output_file = Path("production_secrets.txt")
    with open(output_file, "w") as f:
        f.write("PRODUCTION SECRETS - KEEP SECURE!\n")
        f.write("=" * 40 + "\n\n")
        for var_name, var_value in secrets_to_add:
            f.write(f"{var_name}={var_value}\n")
    
    print(f"\n💾 Secrets saved to: {output_file}")
    print("⚠️  DELETE THIS FILE AFTER DEPLOYMENT!")
    
    return True


if __name__ == "__main__":
    try:
        success = main()
        sys.exit(0 if success else 1)
    except KeyboardInterrupt:
        print("\n\n❌ Secret generation cancelled")
        sys.exit(1)
    except Exception as e:
        print(f"\n❌ Error generating secrets: {e}")
        sys.exit(1)
