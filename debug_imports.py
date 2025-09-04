import sys
import traceback

def test_import(module_name):
    try:
        print(f"--- Testing import: {module_name} ---")
        __import__(module_name)
        print(f"[SUCCESS] Imported {module_name} successfully.")
        return True
    except Exception as e:
        print(f"[ERROR] Failed to import {module_name}. Error: {e}")
        print(traceback.format_exc())
        return False

if __name__ == '__main__':
    modules_to_test = [
        'database',
        'models',
        'ai_service',
        'app' # This will be the last one as it imports everything else
    ]

    for module in modules_to_test:
        if not test_import(module):
            print(f"\n!!! Import failed at module: {module}. The error above is the likely cause. !!!")
            sys.exit(1)

    print("\nAll modules imported successfully!")
