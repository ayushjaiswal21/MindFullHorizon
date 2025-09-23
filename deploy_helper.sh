#!/bin/bash
"""
Deployment Helper Script for MindFull Horizon
This script helps deploy the application with proper Python 3.13 compatibility
"""

set -e  # Exit on any error

echo "🚀 MindFull Horizon Deployment Helper"
echo "====================================="

# Check Python version
echo "📋 Checking Python version..."
python3 --version

# Install dependencies with compatibility flags
echo "📦 Installing dependencies..."
pip install --no-cache-dir --upgrade pip setuptools wheel

# Install requirements with specific flags for Python 3.13 compatibility
echo "🔧 Installing project requirements..."
pip install --no-cache-dir --only-binary=all -r requirements.txt

# Verify installation
echo "✅ Verifying installation..."
python -c "import flask, eventlet, sqlalchemy; print('Core packages installed successfully')"

# Run compatibility check
echo "🧪 Running compatibility check..."
python check_compatibility.py

# Test application startup
echo "🧪 Testing application startup..."
python -c "from app import create_app; app = create_app(); print('✅ Application starts successfully')"

echo ""
echo "🎉 Deployment preparation completed successfully!"
echo "Your MindFull Horizon application is ready for deployment."
