#!/usr/bin/env python3
"""
File Upload Diagnostics for MindFull Horizon
Run this script to diagnose file upload issues
"""

import os
import sys
import subprocess
import importlib.util

def check_dependencies():
    """Check if required packages are installed"""
    print("🔍 Checking Dependencies...")
    
    required_packages = {
        'flask': 'Flask',
        'werkzeug': 'Werkzeug', 
        'PIL': 'Pillow',
        'magic': 'python-magic'
    }
    
    missing_packages = []
    
    for package, name in required_packages.items():
        try:
            importlib.import_module(package)
            print(f"✅ {name} - OK")
        except ImportError:
            print(f"❌ {name} - MISSING")
            missing_packages.append(name)
    
    if missing_packages:
        print(f"\n📦 Install missing packages:")
        print(f"pip install {' '.join(missing_packages.lower())}")
        return False
    
    return True

def check_directories():
    """Check upload directories and permissions"""
    print("\n📁 Checking Directories...")
    
    directories = [
        'static',
        'static/uploads',
        'instance',
        'logs'
    ]
    
    for directory in directories:
        if os.path.exists(directory):
            if os.access(directory, os.W_OK):
                print(f"✅ {directory} - EXISTS & WRITABLE")
            else:
                print(f"⚠️  {directory} - EXISTS but NOT WRITABLE")
        else:
            print(f"❌ {directory} - MISSING")
            try:
                os.makedirs(directory, exist_ok=True)
                print(f"✅ Created {directory}")
            except Exception as e:
                print(f"❌ Failed to create {directory}: {e}")

def check_file_limits():
    """Check system file size limits"""
    print("\n📏 Checking File Limits...")
    
    try:
        import resource
        
        # Check file size limit
        soft_limit, hard_limit = resource.getrlimit(resource.RLIMIT_FSIZE)
        if soft_limit == resource.RLIM_INFINITY:
            print("✅ File size limit - UNLIMITED")
        else:
            print(f"⚠️  File size limit - {soft_limit // (1024*1024)}MB")
        
        # Check number of open files
        soft_limit, hard_limit = resource.getrlimit(resource.RLIMIT_NOFILE)
        print(f"✅ Max open files - {soft_limit}")
        
    except ImportError:
        print("⚠️  Resource module not available (Windows)")

def check_flask_config():
    """Check Flask configuration"""
    print("\n⚙️  Checking Flask Configuration...")
    
    # Check if app.py exists
    if os.path.exists('app.py'):
        print("✅ app.py - EXISTS")
        
        # Read app.py and check for upload configuration
        with open('app.py', 'r') as f:
            content = f.read()
            
        checks = {
            'UPLOAD_FOLDER': 'app.config[\'UPLOAD_FOLDER\']' in content,
            'MAX_CONTENT_LENGTH': 'MAX_CONTENT_LENGTH' in content,
            'secure_filename': 'secure_filename' in content,
            'validate_file_security': 'validate_file_security' in content
        }
        
        for check, found in checks.items():
            if found:
                print(f"✅ {check} - CONFIGURED")
            else:
                print(f"❌ {check} - MISSING")
                
    else:
        print("❌ app.py - NOT FOUND")

def test_file_operations():
    """Test basic file operations"""
    print("\n🧪 Testing File Operations...")
    
    test_dir = 'test_uploads'
    test_file = os.path.join(test_dir, 'test.txt')
    
    try:
        # Create test directory
        os.makedirs(test_dir, exist_ok=True)
        print("✅ Directory creation - OK")
        
        # Create test file
        with open(test_file, 'w') as f:
            f.write("Test file content")
        print("✅ File creation - OK")
        
        # Read test file
        with open(test_file, 'r') as f:
            content = f.read()
        print("✅ File reading - OK")
        
        # Delete test file
        os.remove(test_file)
        os.rmdir(test_dir)
        print("✅ File deletion - OK")
        
    except Exception as e:
        print(f"❌ File operations failed: {e}")

def check_mime_detection():
    """Test MIME type detection"""
    print("\n🔍 Testing MIME Detection...")
    
    try:
        import magic
        
        # Test with a simple text file
        test_content = b"This is a test file"
        mime_type = magic.from_buffer(test_content, mime=True)
        print(f"✅ MIME detection - OK (detected: {mime_type})")
        
    except ImportError:
        print("❌ python-magic not installed")
        print("   Install with: pip install python-magic")
        
        # On Windows, you might also need:
        if sys.platform == 'win32':
            print("   For Windows, also install: pip install python-magic-bin")
    
    except Exception as e:
        print(f"❌ MIME detection failed: {e}")

def generate_fix_suggestions():
    """Generate specific fix suggestions based on findings"""
    print("\n🔧 Fix Suggestions:")
    
    suggestions = [
        "1. Add missing validate_file_security function to app.py",
        "2. Ensure upload directories exist and are writable", 
        "3. Install missing dependencies (especially python-magic)",
        "4. Check Flask configuration for file uploads",
        "5. Verify form has enctype='multipart/form-data'",
        "6. Check that input field name matches backend code",
        "7. Ensure CSRF token is included in forms",
        "8. Check browser console for JavaScript errors",
        "9. Verify file size is under the limit (16MB)",
        "10. Test with different file types and browsers"
    ]
    
    for suggestion in suggestions:
        print(f"   {suggestion}")

def main():
    """Run all diagnostic checks"""
    print("🧠 MindFull Horizon - File Upload Diagnostics")
    print("=" * 50)
    
    all_good = True
    
    # Run all checks
    if not check_dependencies():
        all_good = False
    
    check_directories()
    check_file_limits()
    check_flask_config()
    test_file_operations()
    check_mime_detection()
    
    print("\n" + "=" * 50)
    
    if all_good:
        print("✅ All basic checks passed!")
    else:
        print("⚠️  Some issues found - see suggestions below")
    
    generate_fix_suggestions()
    
    print("\n📋 Next Steps:")
    print("1. Fix any issues identified above")
    print("2. Add the missing functions from file_upload_fix.py")
    print("3. Test upload with test_upload.html")
    print("4. Check server logs for detailed error messages")

if __name__ == "__main__":
    main()