import sys
import os

# Append project root directory to sys.path so 'main.py' is found
root_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if root_dir not in sys.path:
    sys.path.insert(0, root_dir)

from mangum import Mangum
from main import app  # Correctly import 'app' from root main.py

# Expose top-level app and handler for Vercel Serverless runtime
app = app
handler = Mangum(app)
