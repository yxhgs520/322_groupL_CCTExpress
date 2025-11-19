#!/usr/bin/env python
"""
Setup script for the Restaurant Management System Django project.
This script helps initialize the Django project with proper configuration.
"""

import os
import sys
import subprocess
from pathlib import Path

def run_command(command, description):
    """Run a command and handle errors"""
    print(f"🔄 {description}...")
    try:
        result = subprocess.run(command, shell=True, check=True, capture_output=True, text=True)
        print(f"✅ {description} completed successfully")
        return True
    except subprocess.CalledProcessError as e:
        print(f"❌ {description} failed: {e}")
        print(f"Error output: {e.stderr}")
        return False

def main():
    """Main setup function"""
    print("🍽️  Restaurant Management System Setup")
    print("=" * 50)
    
    # Check if we're in the right directory
    if not os.path.exists('models.py') or not os.path.exists('admin.py'):
        print("❌ Error: Please run this script from the project root directory")
        print("   Make sure models.py and admin.py are in the current directory")
        sys.exit(1)
    
    # Create necessary directories
    directories = ['logs', 'media', 'media/dishes', 'staticfiles']
    for directory in directories:
        Path(directory).mkdir(exist_ok=True)
        print(f"📁 Created directory: {directory}")
    
    # Install Django if not already installed
    print("\n📦 Installing Django and dependencies...")
    if not run_command("pip install -r requirements.txt", "Installing dependencies"):
        print("❌ Failed to install dependencies. Please check your Python environment.")
        sys.exit(1)
    
    # Create Django project structure
    print("\n🏗️  Setting up Django project structure...")
    
    # Make migrations
    if not run_command("python manage.py makemigrations", "Creating migrations"):
        print("❌ Failed to create migrations")
        sys.exit(1)
    
    # Apply migrations
    if not run_command("python manage.py migrate", "Applying migrations"):
        print("❌ Failed to apply migrations")
        sys.exit(1)
    
    # Create superuser
    print("\n👤 Creating superuser (Manager account)...")
    print("   You will be prompted to enter username, email, and password")
    if not run_command("python manage.py createsuperuser", "Creating superuser"):
        print("⚠️  Superuser creation failed or was cancelled")
        print("   You can create a superuser later with: python manage.py createsuperuser")
    
    # Collect static files
    if not run_command("python manage.py collectstatic --noinput", "Collecting static files"):
        print("⚠️  Static files collection failed")
    
    print("\n🎉 Setup completed successfully!")
    print("\n📋 Next steps:")
    print("1. Start the development server: python manage.py runserver")
    print("2. Open http://127.0.0.1:8000/admin/ in your browser")
    print("3. Login with your superuser credentials")
    print("4. Start managing your restaurant!")
    
    print("\n🔧 Available management functions:")
    print("   • Customer registration and blacklist management")
    print("   • Complaint and compliment handling")
    print("   • Chef and delivery person HR management")
    print("   • Order and delivery management")
    print("   • Knowledge base for AI customer service")

if __name__ == "__main__":
    main()
