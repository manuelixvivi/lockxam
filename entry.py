import os
import sys

# Ensure root directory is on sys.path
root_dir = os.path.dirname(os.path.abspath(__file__))
if root_dir not in sys.path:
    sys.path.insert(0, root_dir)

from main import app  # noqa: E402

# Cloudflare Python Workers ASGI handler
try:
    from workers import asgi

    Default = asgi.entrypoint(app)
except ImportError:
    Default = app
