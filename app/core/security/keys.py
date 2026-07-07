import os

from dotenv import load_dotenv

load_dotenv()

SECRET_KEY = os.getenv("SECRET_KEY", "")
ALGORITHM = os.getenv("ALGORITHM", "HS256")
ACCESS_TOKEN_EXPIRE_MINUTES = int(os.getenv("ACCESS_TOKEN_EXPIRE_MINUTES", 60))
REFRESH_TOKEN_EXPIRE_DAYS = int(os.getenv("REFRESH_TOKEN_EXPIRE_DAYS", 30))

# JWT Key ID (kid) Rotation settings
ACTIVE_KEY_ID = os.getenv("JWT_ACTIVE_KEY_ID", "v1")
SECRETS = {"v1": SECRET_KEY}

# Load extra secrets for keys if defined in env (e.g. JWT_SECRET_v2=...)
for key, value in os.environ.items():
    if key.startswith("JWT_SECRET_"):
        kid = key.replace("JWT_SECRET_", "")
        SECRETS[kid] = value
