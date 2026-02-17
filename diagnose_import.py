import sys
import os

# Add current directory to path
sys.path.append(os.getcwd())

try:
    print("Attempting to import question_banks.v2.routes...")
    from question_banks.v2 import routes
    print("Successfully imported question_banks.v2.routes")
except Exception as e:
    print(f"Failed to import: {e}")
    import traceback
    traceback.print_exc()
