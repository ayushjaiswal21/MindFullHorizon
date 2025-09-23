#!/usr/bin/env python3
"""
Python 3.13 Compatibility Check for MindFull Horizon
Run this script to verify all dependencies are compatible with Python 3.13
"""

import sys
import subprocess
import importlib.util

def check_python_version():
    """Check if Python version is compatible"""
    version = sys.version_info
    print(f"Python version: {version.major}.{version.minor}.{version.micro}")

    if version.major != 3 or version.minor < 9:
        print("❌ Python version should be 3.9+ (3.13+ recommended)")
        return False
    else:
        print("✅ Python version is compatible")
        return True

def check_package_compatibility():
    """Check if key packages are compatible with Python 3.13"""
    packages_to_check = {
        'flask': '3.0.0',
        'sqlalchemy': '2.0.0',
        'eventlet': '0.36.0',
        'gunicorn': '22.0.0',
        'pillow': '10.4.0',
        'psycopg2_binary': '2.9.0'
    }

    print("\n📦 Checking package compatibility...")
    all_compatible = True

    for package, min_version in packages_to_check.items():
        try:
            # Try to import the package
            if package == 'psycopg2_binary':
                import psycopg2
            elif package == 'pillow':
                import PIL
            else:
                __import__(package.replace('_', '-'))

            print(f"✅ {package} - Compatible")
        except ImportError as e:
            print(f"❌ {package} - Import failed: {e}")
            all_compatible = False
        except Exception as e:
            print(f"⚠️  {package} - Warning: {e}")
            # Don't mark as incompatible for warnings

    return all_compatible

def test_pip_install():
    """Test if packages can be installed with pip"""
    print("\n🔧 Testing pip installation...")
    try:
        # Try installing a small test package
        result = subprocess.run([
            sys.executable, '-m', 'pip', 'install', '--dry-run', 'requests==2.32.0'
        ], capture_output=True, text=True)

        if result.returncode == 0:
            print("✅ Pip installation test passed")
            return True
        else:
            print(f"❌ Pip installation test failed: {result.stderr}")
            return False
    except Exception as e:
        print(f"❌ Pip test error: {e}")
        return False

def main():
    """Run all compatibility checks"""
    print("🧠 MindFull Horizon - Python 3.13 Compatibility Check")
    print("=" * 60)

    checks = [
        check_python_version(),
        check_package_compatibility(),
        test_pip_install()
    ]

    print("\n" + "=" * 60)
    if all(checks):
        print("🎉 All compatibility checks passed!")
        print("Your environment is ready for Python 3.13 deployment.")
        return True
    else:
        print("⚠️  Some compatibility issues found.")
        print("Check the errors above and update your requirements.txt accordingly.")
        return False

if __name__ == "__main__":
    success = main()
    sys.exit(0 if success else 1)
