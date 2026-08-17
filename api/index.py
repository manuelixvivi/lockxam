import sys
import os

# Append project root directory to sys.path
root_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if root_dir not in sys.path:
    sys.path.insert(0, root_dir)

try:
    from main import app as fastapi_app
    app = fastapi_app
except Exception as _import_err:
    from fastapi import FastAPI
    app = FastAPI(title="Equigrade Vercel Fallback")
    
    @app.get("/api/import-error")
    def import_error():
        return {"error": str(_import_err)}

try:
    from mangum import Mangum
    handler = Mangum(app)
except Exception:
    handler = app

# Guarantee top-level exports for Vercel Serverless static analyzer
application = app
