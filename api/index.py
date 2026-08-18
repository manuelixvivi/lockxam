import sys
import os

# Append project root directory to sys.path
root_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if root_dir not in sys.path:
    sys.path.insert(0, root_dir)

from main import app

# Top-level ASGI handler for Vercel Serverless Functions
app = app
