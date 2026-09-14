import os
import sys

# Append project root directory to sys.path
root_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if root_dir not in sys.path:
    sys.path.insert(0, root_dir)

from main import app  # noqa: E402

# Top-level FastAPI ASGI handler for Vercel Serverless
app = app
