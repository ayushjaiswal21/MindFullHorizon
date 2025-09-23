#!/usr/bin/env python3
"""
Worker Class Compatibility Test for MindFull Horizon
Test different Gunicorn worker classes with Python 3.13
"""

import sys
import subprocess
import importlib.util

def test_worker_class(worker_class):
    """Test if a specific worker class works with current Python version"""
    try:
        if worker_class == 'eventlet':
            import eventlet
            print(f"✅ {worker_class}: Available (version {eventlet.__version__})")
            return True
        elif worker_class == 'gevent':
            import gevent
            print(f"✅ {worker_class}: Available (version {gevent.__version__})")
            return True
        elif worker_class == 'tornado':
            import tornado
            print(f"✅ {worker_class}: Available (version {tornado.version})")
            return True
        else:
            print(f"✅ {worker_class}: Available (default sync worker)")
            return True
    except ImportError as e:
        print(f"❌ {worker_class}: Not available - {e}")
        return False
    except Exception as e:
        print(f"⚠️  {worker_class}: Error - {e}")
        return False

def test_gunicorn_import():
    """Test if gunicorn can import the app with different workers"""
    worker_classes = ['sync', 'eventlet', 'gevent', 'tornado']

    print("🔧 Testing Gunicorn Worker Class Compatibility")
    print("=" * 50)

    available_workers = []

    for worker in worker_classes:
        if test_worker_class(worker):
            available_workers.append(worker)

    print("\n" + "=" * 50)
    if available_workers:
        print("✅ Available worker classes:")
        for worker in available_workers:
            print(f"   - {worker}")

        print("\n📋 Recommended deployment commands:")
        for worker in available_workers:
            if worker == 'sync':
                print(f"   gunicorn --workers 1 --bind 0.0.0.0:$PORT app:app")
            else:
                print(f"   gunicorn --worker-class {worker} --workers 1 --bind 0.0.0.0:$PORT app:app")
    else:
        print("❌ No compatible worker classes found")

    return len(available_workers) > 0

def main():
    """Run compatibility tests"""
    print("🧪 MindFull Horizon - Worker Class Compatibility Test")
    print(f"Python version: {sys.version}")

    success = test_gunicorn_import()

    if success:
        print("\n🎉 Your application has compatible worker classes!")
        print("Try deploying with one of the recommended commands above.")
    else:
        print("\n⚠️  No compatible worker classes found.")
        print("Consider using a different Python version or installing missing packages.")

    return success

if __name__ == "__main__":
    success = main()
    sys.exit(0 if success else 1)
