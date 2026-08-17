import sys
import os

# Append project root directory to sys.path
root_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if root_dir not in sys.path:
    sys.path.insert(0, root_dir)

from app.main import app

# Expose top-level app and handler for Vercel Serverless runtime
app = app
handler = app
