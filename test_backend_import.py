import sys
import os
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

try:
    from backend import app
    print("SUCCESS: Backend imports successfully")
    print("SUCCESS: FastAPI app created")
    print("SUCCESS: Ready to start server")
    
except Exception as e:
    print(f"ERROR: {e}")
    import traceback
    traceback.print_exc()